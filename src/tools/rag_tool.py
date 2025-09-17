# src/tools/rag_tool.py
import os
import sys
import glob
from typing import List, Dict, Any

# 添加 src 目录到 sys.path 以便导入兄弟模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# [修正] 从正确的模块导入 TextBlock 和 ToolResponse
from agentscope.message import TextBlock
from agentscope.tool import ToolResponse
import config

from agentscope.embedding import EmbeddingModelBase, DashScopeTextEmbedding

# 检查并安装 chromadb
try:
    import chromadb
except ImportError:
    print("错误: 检测到缺失的 chromadb 库，请确保已根据 requirements.txt 安装依赖。")
    sys.exit(1)

# --- 全局变量 ---
global_chroma_collection = None
global_embedder = None

# --- 自定义文档处理函数 ---
def _load_markdown_docs(path: str) -> List[Dict[str, Any]]:
    """遍历目录，加载所有 markdown 文件的内容。"""
    all_md_files = glob.glob(os.path.join(path, "**/*.md"), recursive=True)
    documents = []
    for file_path in all_md_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            documents.append({"content": content, "metadata": {"source": file_path}})
    return documents

def _split_text(documents: List[Dict[str, Any]], chunk_size: int = 1000, chunk_overlap: int = 200) -> List[Dict[str, Any]]:
    """一个简单的文本切片器。"""
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
                    chunks.append({"content": current_chunk_content.strip(), "metadata": metadata})
                current_chunk_content = p + "\n\n"
        if current_chunk_content:
            chunks.append({"content": current_chunk_content.strip(), "metadata": metadata})
    return chunks

# --- 导出的核心函数 ---
async def initialize_vector_db(agent_name: str | None = None) -> Any:
    """初始化向量数据库。

    Args:
        agent_name: 可选，指定为哪个 Agent 选择 embedding 模型；
            若未提供则使用全局默认 embedding 模型。
    """
    global global_chroma_collection, global_embedder
    print("正在初始化向量数据库 (纯 AgentScope 实现)... ")

    # 1. 创建 AgentScope 原生 Embedding 模型
    # 检查至少一个API密钥是否配置
    dashscope_key_configured = "your_" not in config.DASHSCOPE_API_KEY

    if not dashscope_key_configured:
        print("错误：未在 .env 或 config.py 中配置有效的 DASHSCOPE_API_KEY。")
        return None # 返回 None
    
    if dashscope_key_configured:
        embedding_model_name = getattr(config, "get_embedding_model_name", lambda _=None: config.EMBEDDING_MODEL_NAME)(agent_name)
        print(f"使用 AgentScope DashScope Embedding 模型: {embedding_model_name}")
        global_embedder = DashScopeTextEmbedding(model_name=embedding_model_name, api_key=config.DASHSCOPE_API_KEY)
    else:
        # 理论上不应该到达这里，因为上面已经检查过
        print("错误：无法初始化嵌入模型，请检查 API 密钥配置。")
        return None # 返回 None

    documents = _load_markdown_docs(config.RAG_DOCS_PATH)
    chunks = _split_text(documents) if documents else []

    client = chromadb.PersistentClient(path=config.VECTOR_DB_PATH)
    collection_name = "agentscope_rag_collection"
    global_chroma_collection = client.get_or_create_collection(name=collection_name)

    if chunks:
        print(f"文档被切分为 {len(chunks)} 个片段。正在向量化并存入 ChromaDB...")
        chunk_contents = [c['content'] for c in chunks]
        embedding_response = await global_embedder(chunk_contents)
        metadatas = [c['metadata'] for c in chunks]
        ids = [f"chunk_{i}" for i in range(len(chunks))]
        
        # 清空旧集合以避免重复
        if global_chroma_collection.count() > 0:
            global_chroma_collection.delete(ids=global_chroma_collection.get()['ids'])

        global_chroma_collection.add(embeddings=embedding_response.embeddings, documents=chunk_contents, metadatas=metadatas, ids=ids)
        print(f"{len(chunks)} 个片段已存入数据库。")
    else:
        print("未找到新文档，加载现有数据库。 সন")

    print("向量数据库初始化完成。 সন")
    return global_chroma_collection # 返回 collection

def set_vector_store(vector_store: Any):
    pass

async def retrieve_knowledge(query: str, k: int = 3) -> ToolResponse:
    """从向量知识库中检索与查询相关的知识。"""
    if global_chroma_collection is None or global_embedder is None:
        error_msg = "错误：向量数据库或嵌入模型未初始化。"
        return ToolResponse(content=[TextBlock(text=error_msg).to_dict()])

    try:
        print(f"正在从知识库中异步检索 '{query}'...")
        query_embedding_response = await global_embedder([query])
        results = global_chroma_collection.query(query_embeddings=query_embedding_response.embeddings, n_results=k)
        docs = results['documents'][0]
        retrieved_content = "\n---\n".join(docs) if docs else "在知识库中未找到与查询直接相关的信息。"
        response_text = f"从知识库中检索到以下内容：\n{retrieved_content}"
        return ToolResponse(content=[TextBlock(text=response_text).to_dict()])
    except Exception as e:
        error_msg = f"知识库检索时发生错误: {e}"
        return ToolResponse(content=[TextBlock(text=error_msg).to_dict()])