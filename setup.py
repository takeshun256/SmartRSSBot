from setuptools import setup, find_packages

setup(
    name="smartrssbot",
    version="0.1.0",
    description="SmartRSSBotは、Discord上でRSSフィードを定期的に取得し、AIを用いて記事の関連度を評価するボットです。ユーザーは新しい記事の通知を受け取り、AIによる評価結果を確認することができます。",
    author="takeshun256",
    author_email="takeshun1619@gmail.com",
    packages=find_packages(),
    install_requires=[
        'python-dotenv==1.0.1',
        'discord.py==2.4.0',
        'feedparser==6.0.11',
        'langchain-community==0.2.17',
        'langchain==0.2.16',
        'langchain-openai==0.1.25',
        'unstructured==0.11.8',
    ],
    python_requires='>=3.8',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
