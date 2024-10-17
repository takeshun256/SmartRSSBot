from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.indexes import VectorstoreIndexCreator
from langchain.text_splitter import CharacterTextSplitter
from langchain_community.vectorstores.inmemory import InMemoryVectorStore
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.document_loaders import UnstructuredURLLoader


class ArticleRagRetriever:

    def __init__(self, desired_article_string, urls=None):
        """記事を取得するためのクラス

        Args:
            urls (リスト): 記事を取得するためのURLのリスト
            desired_article_string (文字列): 希望する記事の内容を示す文字列
        """
        self.urls = urls or []
        self.desired_article_string = desired_article_string
        if urls:
            self._initialize_from_urls(urls)

    def _initialize_from_urls(self, urls):
        """URLから初期化を行うメソッド"""
        if not urls:
            raise ValueError("URLが指定されていません。")
        self.text_splitter = CharacterTextSplitter(
            separator="\n",
            chunk_size=600,
            chunk_overlap=0,
            length_function=len,
        )
        self.loader = UnstructuredURLLoader(urls=urls)
        self.index = VectorstoreIndexCreator(
            vectorstore_cls=InMemoryVectorStore,
            embedding=OpenAIEmbeddings(),
            text_splitter=self.text_splitter,
        ).from_loaders([self.loader])
        self.retriever = self.index.vectorstore.as_retriever()
        self.llm = ChatOpenAI(model="gpt-4o")

    def retrieve_article(self, input_text, answer_type="eval"):
        """URLの記事に基づいて回答する
        Args:
            input_text (str): 入力テキスト。
            answer_type (str, オプション): 回答の形式を指定する。デフォルトは"eval"。
        """
        if not input_text:
            raise ValueError("input_textが指定されていません。")
        if answer_type not in ["eval", "question"]:
            raise ValueError("answer_typeは'eval'または'question'のみ受け取ります。")
        if answer_type == "eval":
            system_message = """以下の記事が欲しい内容（希望する記事内容）にどの程度マッチしているかを評価してください。評価は3段階（High⏫/Medium🔼/Low⏩）で行ってください。:

### 希望する記事内容
{desired_article_string}

### 回答形式
関連度: High⏫
概要: ～に関する内容。～が関係しているかも。

### 記事内容
<context>
{context}
</context>
"""
        elif answer_type == "question":
            system_message = """以下のドキュメント内容について質問に回答してください。:

### ドキュメント内容
<context>
{context}
</context>

### 回答形式
回答: {input}ついて、～と記載があります。
"""

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    system_message,
                ),
                ("human", "{input}"),
            ],
        )
        chain = create_retrieval_chain(
            self.retriever, create_stuff_documents_chain(self.llm, prompt)
        )
        response = chain.invoke(
            {
                "input": input_text,
                "desired_article_string": self.desired_article_string,
            }
        )
        return response

    def retrieve_new_url_article(self, urls, input_text, answer_type="eval"):
        """新しいURLの記事に基づいて回答する
        Args:
            urls (リスト): 記事を取得するためのURLのリスト。
            input_text (str): 入力テキスト。
            answer_type (str, オプション): 回答の形式を指定する。デフォルトは"eval"。
        """
        self._initialize_from_urls(urls)
        return self.retrieve_article(input_text, answer_type)


if __name__ == "__main__":

    import sys

    input_text = sys.argv[1]  # ユーザーメッセージを引数として受け取る
    urls = ["https://python.langchain.com/docs/tutorials/"]
    desired_article_string = "Pythonの特にLangChainについての記事"
    retriever = ArticleRagRetriever(urls, desired_article_string)
    response = retriever.retrieve_article(input_text, answer_type="eval")
    for key, value in response.items():
        print(f"{key}: {value}")
