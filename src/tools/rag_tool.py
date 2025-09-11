# src/tools/rag_tool.py
import config
import os
import sys

from agentscope.tool import TextBlock, ToolResponse

# 动态添加src目录到sys.path，以便能够导入config
# 在实际运行时，根据启动方式，可能需要更优雅的路径管理方案
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# 检查并安装缺失的库
try:
    from langchain.embeddings import DashScopeEmbeddings, OpenAIEmbeddings
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain.vectorstores import Chroma
    from langchain_community.document_loaders import (DirectoryLoader,
                                                      UnstructuredFileLoader)
except ImportError:
    print("检测到缺失的LangChain相关库，请确保已根据requirements.txt安装依赖。")
    sys.exit(1)


# 全局变量，用于在运行时持有向量数据库实例
global_vector_store = None


def initialize_vector_db():
    """
    初始化向量数据库。
    - 加载 `config.RAG_DOCS_PATH` 目录下的所有文档。
    - 对文档进行切分。
    - 使用 `config.EMBEDDING_MODEL_NAME` 进行向量化。
    - 将向量存入 `config.VECTOR_DB_PATH` 指定的 ChromaDB 路径。
    - 返回一个可供查询的 vector_store 实例。
    """
    print("正在初始化向量数据库...")

    # 1. 选择 Embedding 模型
    # 优先使用 DashScope (Qwen) 的 embedding，如果未配置，则使用 OpenAI
    if "your_" not in config.DASHSCOPE_API_KEY:
        print(f"使用 DashScope Embedding 模型: {config.EMBEDDING_MODEL_NAME}")
        embeddings = DashScopeEmbeddings(
            model=config.EMBEDDING_MODEL_NAME,
            dashscope_api_key=config.DASHSCOPE_API_KEY
        )
    elif "your_" not in config.OPENAI_API_KEY:
        print(f"使用 OpenAI Embedding 模型: {config.EMBEDDING_MODEL_NAME}")
        embeddings = OpenAIEmbeddings(
            model=config.EMBEDDING_MODEL_NAME,
            api_key=config.OPENAI_API_KEY
        )
    else:
        print("错误：未在 .env 或 config.py 中配置有效的 DASHSCOPE_API_KEY 或 OPENAI_API_KEY。")
        return None

    # 2. 加载文档
    # 使用 DirectoryLoader 加载所有支持的文件类型
    print(f"从 '{config.RAG_DOCS_PATH}' 加载文档...")
    loader = DirectoryLoader(config.RAG_DOCS_PATH,
                             silent_errors=True, recursive=True)
    documents = loader.load()

    if not documents:
        print("警告：在 `rag_docs` 目录中未找到可加载的文档。")
        # 即使没有文档，也加载持久化的数据库（如果存在）
        vector_store = Chroma(
            persist_directory=config.VECTOR_DB_PATH,
            embedding_function=embeddings
        )
        print("向量数据库初始化完成（从现有数据加载）。")
        return vector_store

    # 3. 文本切分
    print(f"加载了 {len(documents)} 篇文档，正在进行切分...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=200)
    texts = text_splitter.split_documents(documents)
    print(f"文档被切分为 {len(texts)} 个片段。")

    # 4. 向量化与存储
    # 使用 from_documents 会创建或加载数据库，并添加新的文本
    # 注意：这是一种简化的实现，每次启动都会重新处理所有文档。
    # 生产环境中，需要实现更复杂的增量更新逻辑。
    print("正在进行向量化并存入 ChromaDB...")
    vector_store = Chroma.from_documents(
        documents=texts,
        embedding=embeddings,
        persist_directory=config.VECTOR_DB_PATH
    )

    print("向量数据库初始化完成。")
    return vector_store


def set_vector_store(vector_store):
    """
    设置全局的 vector_store 实例，以便检索工具可以访问。
    """
    global global_vector_store
    global_vector_store = vector_store


def retrieve_knowledge(query: str, k: int = 3) -> ToolResponse:
    """
    从向量知识库中检索与查询相关的知识。

    Args:
        query (str): 用于检索的查询文本。
        k (int): 返回的相关文档数量。
    """
    if global_vector_store is None:
        error_msg = "错误：向量数据库未初始化。请确保在应用启动时调用了 initialize_vector_db。"
        print(error_msg)
        return ToolResponse(content=[TextBlock(text=error_msg)])

    try:
        print(f"正在从知识库中检索 '{query}'...")
        docs = global_vector_store.similarity_search(query, k=k)

        if not docs:
            retrieved_content = "未找到相关信息。"
        else:
            retrieved_content = "\n---\n".join(
                [doc.page_content for doc in docs])

        response_text = f"从知识库中检索到以下内容：\n{retrieved_content}"

        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=response_text
                )
            ]
        )
    except Exception as e:
        error_msg = f"知识库检索时发生错误: {e}"
        print(error_msg)
        return ToolResponse(content=[TextBlock(text=error_msg)])
