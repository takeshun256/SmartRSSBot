from discord.ext import commands
import discord
import traceback
import os
from dotenv import load_dotenv

# 読み込むCogの名前を格納
INITIAL_EXTENSIONS = [
    "cogs.feedalert",
]

load_dotenv()
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
GUILD_ID = os.getenv("DISCORD_GUILD_ID", None)


class MyBot(commands.Bot):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def on_ready(self):
        print("Logged in as")
        print(self.user.name)
        print(self.user.id)
        print("------")
        await self.change_presence(activity=discord.Game("SmartRSS"))

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.errors.CommandNotFound):
            await ctx.send("そのコマンドは存在しません。")
        elif isinstance(error, commands.errors.MissingRequiredArgument):
            await ctx.send("引数が不足しています。")
        else:
            await ctx.send("エラーが発生しました。")
            await ctx.send(f"```{traceback.fomrmat_exc()}```")

    async def setup_hook(self) -> None:
        for cog in INITIAL_EXTENSIONS:
            await self.load_extension(cog)

        await self.tree.sync(guild=discord.Object(id=GUILD_ID))
        return (
            await super().setup_hook()
        )


if __name__ == "__main__":
    intents = discord.Intents.default()
    intents.members = True  # (メンバー管理の権限)
    intents.message_content = True  # message.contentを取得するために必要
    bot = MyBot(command_prefix="$", case_insensitive=True, intents=intents)

    bot.run(BOT_TOKEN)
