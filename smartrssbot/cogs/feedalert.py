import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import sqlite3
from dotenv import load_dotenv
import feedparser
import datetime
from smartrssbot.modules.article_rag_retriever import ArticleRagRetriever
import nltk

# 辞書
nltk.download("punkt")
nltk.download("averaged_perceptron_tagger_eng")

# 環境変数のロード
load_dotenv()
GUILD_ID = os.getenv("DISCORD_GUILD_ID", None)
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", None))
FEED_URL = os.getenv("RSS_FEED_URL", None)
DESIRED_ARTICLE_STRING = os.getenv("DESIRED_ARTICLE_STRING", None)

# データベースの初期化
DB_PATH = os.path.join(os.path.dirname(__file__), "rss_feed.db")


def init_db():
    execute_db_query(
        """CREATE TABLE IF NOT EXISTS entries (id TEXT PRIMARY KEY, feed_url TEXT, url TEXT)"""
    )


def execute_db_query(query, params=(), fetch=False):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        if params and isinstance(params[0], tuple):
            c.executemany(query, params)
        else:
            c.execute(query, params)
        result = c.fetchall() if fetch else None
        conn.commit()
    return result


def load_archived_entry_ids():
    try:
        rows = execute_db_query("SELECT id FROM entries", fetch=True)
        print(f"Loaded {len(rows)} RSS archived entries")
        return {row[0] for row in rows}
    except sqlite3.OperationalError as e:
        print(f"Error loading archived entries: {e}")
        return set()


def save_archived_entry_ids(entry_ids, feed_url):
    query = "INSERT OR IGNORE INTO entries (id, feed_url, url) VALUES (?, ?, ?)"
    params = [(entry_id, feed_url, entry_url) for entry_id, entry_url in entry_ids]
    execute_db_query(query, params)
    print(f"Saved {len(entry_ids)} RSS archived entries")


def get_rss_feed(feed_url):
    feed = feedparser.parse(feed_url)

    # 新しいエントリを取得
    new_entries = get_new_entries(feed, feed_url)

    print(f"Fetched {len(new_entries)} new entries from RSS feed.")
    return (feed, new_entries, feed_url)


def get_new_entries(feed, feed_url):
    new_entries = []
    for entry in feed.entries:
        # エントリがデータベースに存在するか確認
        result = execute_db_query(
            "SELECT * FROM entries WHERE id=?", (entry.id,), fetch=True
        )
        if not result:
            new_entries.append(entry)
            save_entry(entry, feed_url)
    return new_entries


def save_entry(entry, feed_url):
    query = "INSERT OR IGNORE INTO entries (id, feed_url, url) VALUES (?, ?, ?)"
    params = (entry.id, feed_url, entry.link)
    execute_db_query(query, [params])
    print(f"Entry {entry.id} saved.")


def get_new_archives(new_entries, archived_entry_ids):
    new_entry_ids = {entry.id for entry in new_entries}
    new_archives = new_entry_ids - archived_entry_ids
    return new_archives


class FeedAlertRagCog(commands.Cog):
    """RSSフィードの更新情報をリマインドするDiscordボット"""

    def __init__(self, bot):
        self.bot = bot
        self.archived_entry_ids = load_archived_entry_ids()
        self.check_rss_feed_task.start()
        if not DESIRED_ARTICLE_STRING:
            raise ValueError(
                "DESIRED_ARTICLE_STRING is not set. Please set it in .env."
            )
        self.retriever = ArticleRagRetriever(
            urls=[], desired_article_string=DESIRED_ARTICLE_STRING
        )
        if not FEED_URL:
            raise ValueError("RSS_FEED_URL is not set. Please set it in .env.")
        self.feed_url = FEED_URL
        print("FeedAlertRagCog initialized.")

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"Logged in as {self.bot.user} with FeedAlertRagCog")

    @tasks.loop(minutes=5)
    async def check_rss_feed_task(self):
        channel = self.bot.get_channel(CHANNEL_ID)
        if channel is None:
            print("Channel not found.")
            return

        feed_url = self.feed_url
        _, new_entries, _ = get_rss_feed(feed_url)

        new_archives = get_new_archives(new_entries, self.archived_entry_ids)

        if new_archives:
            await self.send_new_entries(channel, new_entries, new_archives, feed_url)
            self.archived_entry_ids.update(new_archives)

    async def send_new_entries(self, channel, new_entries, new_archives, feed_url):
        print(f"Sending new entries to channel: {channel.id}")
        save_archived_entry_ids(
            [
                (entry.id, entry.link)
                for entry in new_entries
                if entry.id in new_archives
            ],
            feed_url,
        )
        if len(new_archives) > 5:
            await channel.send(
                f"{len(new_archives)}件取得しました。最新1件を表示します。"
            )
            print(f"New entries: {len(new_archives)=}")
            new_archives = list(new_archives)[:1]

        for entry in new_entries:
            if entry.id in new_archives:
                print(f"New entry: {entry.title} - {entry.link}")
                await channel.send(
                    f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} {entry.title} - {entry.link}"
                )
                await self.send_rss_link(channel, entry.title, entry.link)

    async def send_rss_link(self, channel, title, link):
        """RSSフィードのリンクを含むメッセージを送信する"""
        print(f"Sending RSS link for entry: {title}")

        async def button_callback(interaction):
            await interaction.response.defer()
            print(f"Button clicked: {link=}, Evaluating article by AIRetriever")
            try:
                response = self.retriever.retrieve_new_url_article(
                    urls=[link], input_text="評価してください。", answer_type="eval"
                )
                answer = response.get("answer", "評価が取得できませんでした。")
                formatted_answer = answer.replace("\\n", "\n")
                await interaction.followup.send(f"**{title}**: \n{formatted_answer}")
            except Exception as e:
                print(f"Error: {e}")
                await interaction.followup.send("評価が取得できませんでした。")

        button = discord.ui.Button(
            label="AIによる関連度評価", style=discord.ButtonStyle.primary
        )
        button.callback = button_callback

        view = discord.ui.View()
        view.add_item(button)

        await channel.send(
            view=view,
        )
        print(f"RSS link sent for entry: {title}")

    @check_rss_feed_task.before_loop
    async def before_check_rss_feed_task(self):
        await self.bot.wait_until_ready()
        print("Bot is ready.")

    @app_commands.command(
        name="rss", description="RSSフィードに新しいエントリがあるか確認します"
    )
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def rss(self, interaction: discord.Interaction):
        """ユーザーが手動でRSSリンクを表示するためのコマンド"""
        await interaction.response.defer()
        channel = interaction.channel

        feed_url = self.feed_url
        _, new_entries, _ = get_rss_feed(feed_url)

        new_archives = get_new_archives(new_entries, self.archived_entry_ids)

        if new_archives:
            print(f"New RSS entries found: {new_archives}")
            await self.send_new_entries(channel, new_entries, new_archives, feed_url)
            self.archived_entry_ids.update(new_archives)
            await interaction.followup.send("新しいRSSエントリを送信しました！")
        else:
            print("No new RSS entries found.")
            await interaction.followup.send("新しいRSSエントリはありません。")

    @app_commands.command(
        name="eval", description="AIによる記事の関連度評価を取得します"
    )
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def eval(self, interaction: discord.Interaction, url: str):
        """ユーザーが手動でAIによる関連度評価を取得するためのコマンド"""
        print(f"Eval command invoked for URL: {url}")
        await interaction.response.defer()
        # channel = interaction.channel

        try:
            response = self.retriever.retrieve_new_url_article(
                urls=[url], input_text="評価してください。", answer_type="eval"
            )
            answer = response.get("answer", "評価が取得できませんでした。")
            formatted_answer = answer.replace("\\n", "\n")
            await interaction.followup.send(f"**{url}**: \n{formatted_answer}")
        except Exception as e:
            print(f"Error: {e}")
            await interaction.followup.send("評価が取得できませんでした。")

    @app_commands.command(name="question", description="AIによる記事の質問を取得します")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def question(self, interaction: discord.Interaction, url: str, question: str):
        """ユーザーが手動でAIによる質問応答を取得するためのコマンド"""
        print(f"Question command invoked for URL: {url} with question: {question}")
        await interaction.response.defer()
        # channel = interaction.channel

        try:
            response = self.retriever.retrieve_new_url_article(
                urls=[url], input_text=question, answer_type="question"
            )
            answer = response.get("answer", "回答が取得できませんでした。")
            formatted_answer = answer.replace("\\n", "\n")
            await interaction.followup.send(f"**{url}**: \n{formatted_answer}")
            print(f"Question response sent for URL: {url}")
        except Exception as e:
            print(f"Error: {e}")
            await interaction.followup.send("回答が取得できませんでした。")


async def setup(bot):
    init_db()
    await bot.add_cog(
        FeedAlertRagCog(bot),
        guild=discord.Object(id=GUILD_ID),
    )
