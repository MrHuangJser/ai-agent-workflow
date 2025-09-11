# src/tools/rag_tool.py
from agentscope.embedding import EmbeddingModelBase, DashScopeTextEmbedding, OpenAITextEmbedding
import config
from agentscope.tool import ToolResponse, TextBlock
import os
import sys
import glob
from typing import List, Dict, Any

# 添加 src 目录到 sys.path 以便导入兄弟模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


# 导入 agentscope 原生的 embedding 类

# 检查并安装 chromadb
try:
    import chromadb
except ImportError:
    print("错误: 检测到缺失的 chromadb 库，请确保已根据 requirements.txt 安装依赖。")
    sys.exit(1)

# --- 全局变量，用于在运行时持有数据库客户端、嵌入模型等 ---
global_chroma_collection = None
global_embedder = None

# --- [新] 自定义文档处理函数 ---


def _load_markdown_docs(path: str) -> List[Dict[str, Any]]:
    """遍历目录，加载所有 markdown 文件的内容。"""
    all_md_files = glob.glob(os.path.join(path, "**/*.md"), recursive=True)
    documents = []
    for file_path in all_md_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            documents.append(
                {"content": content, "metadata": {"source": file_path}})
    return documents


def _split_text(documents: List[Dict[str, Any]], chunk_size: int = 1000, chunk_overlap: int = 200) -> List[Dict[str, Any]]:
    """一个简单的文本切片器，基于段落和字符数。"""
    chunks = []
    for doc in documents:
        content = doc["content"]
        metadata = doc["metadata"]
        paragraphs = content.split('\n\n')

        current_chunk_content = ""
        for p in paragraphs:
            if len(current_chunk_content) + len(p) + 1 <= chunk_size:
                current_chunk_content += p + "\n\n"
            else:
                if current_chunk_content:
                    chunks.append(
                        {"content": current_chunk_content.strip(), "metadata": metadata})
                current_chunk_content = p + "\n\n"

        if current_chunk_content:
            chunks.append(
                {"content": current_chunk_content.strip(), "metadata": metadata})

    # 此处可以添加更复杂的重叠逻辑，但为简化，暂不实现
    return chunks

# --- 导出的核心函数 ---


async def initialize_vector_db() -> None:
    """
    初始化向量数据库，完全不依赖 LangChain。
    在应用启动时由 main.py 调用。
    """
    global global_chroma_collection, global_embedder
    print("正在初始化向量数据库 (纯 AgentScope 实现)... ")

    # 1. 创建 AgentScope 原生 Embedding 模型
    if "your_" not in config.DASHSCOPE_API_KEY:
        print(
            f"使用 AgentScope DashScope Embedding 模型: {config.EMBEDDING_MODEL_NAME}")
        global_embedder = DashScopeTextEmbedding(
            model=config.EMBEDDING_MODEL_NAME, api_key=config.DASHSCOPE_API_KEY)
    elif "your_" not in config.OPENAI_API_KEY:
        print(
            f"使用 AgentScope OpenAI Embedding 模型: {config.EMBEDDING_MODEL_NAME}")
        global_embedder = OpenAITextEmbedding(
            model=config.EMBEDDING_MODEL_NAME, api_key=config.OPENAI_API_KEY)
    else:
        print("错误：未在 .env 或 config.py 中配置有效的 API 密钥。")
        return

    # 2. 加载并切分文档
    documents = _load_markdown_docs(config.RAG_DOCS_PATH)
    if not documents:
        print(f"警告：在 '{config.RAG_DOCS_PATH}' 目录中未找到 .md 文档。")

    chunks = _split_text(documents)
    if not chunks:
        print("未生成任何文本片段，将只加载现有数据库。")
    else:
        print(f"文档被切分为 {len(chunks)} 个片段。")

    # 3. 初始化 ChromaDB 客户端并获取/创建集合
    client = chromadb.PersistentClient(path=config.VECTOR_DB_PATH)
    collection_name = "agentscope_rag_collection"
    global_chroma_collection = client.get_or_create_collection(
        name=collection_name)

    # 4. 向量化并存储 (简化实现，每次都重新添加)
    if chunks:
        print("正在进行向量化并存入 ChromaDB...")
        # 注意：生产环境应做增量更新，此处为简化实现
        chunk_contents = [c['content'] for c in chunks]
        embedding_response = await global_embedder(chunk_contents)
        embeddings = embedding_response.embeddings
        metadatas = [c['metadata'] for c in chunks]
        ids = [f"chunk_{i}" for i in range(len(chunks))]

        # 清空旧集合以避免重复
        global_chroma_collection.delete(
            ids=global_chroma_collection.get()['ids'])
        global_chroma_collection.add(
            embeddings=embeddings,
            documents=chunk_contents,
            metadatas=metadatas,
            ids=ids
        )
        print(f"{len(chunks)} 个片段已存入数据库。")

    print("向量数据库初始化完成。")


async def retrieve_knowledge(query: str, k: int = 3) -> ToolResponse:
    """
    从向量知识库中检索与查询相关的知识。
    """
    if global_chroma_collection is None or global_embedder is None:
        error_msg = "错误：向量数据库或嵌入模型未初始化。"
        print(error_msg)
        return ToolResponse(content=[TextBlock(text=error_msg)])

    try:
        print(f"正在从知识库中异步检索 '{query}'...")
        query_embedding_response = await global_embedder([query])
        query_vector = query_embedding_response.embeddings

        results = global_chroma_collection.query(
            query_embeddings=query_vector,
            n_results=k
        )

        docs = results['documents'][0]
        if not docs:
            retrieved_content = "在知识库中未找到与查询直接相关的信息。"
        else:
            retrieved_content = "\n---\n".join(docs)

        response_text = f"从知识库中检索到以下内容：\n{retrieved_content}"

        return ToolResponse(content=[TextBlock(text=response_text)])
    except Exception as e:
        error_msg = f"知识库检索时发生错误: {e}"
        print(error_msg)
        return ToolResponse(content=[TextBlock(text=error_msg)])
