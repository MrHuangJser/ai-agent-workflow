# src/config.py
import os
from dotenv import load_dotenv

# 从 .env 文件加载环境变量
# 建议您在项目根目录下创建一个 .env 文件来存放敏感信息
# 例如: DASHSCOPE_API_KEY=sk-xxxxxxxx
load_dotenv()

# --- LLM 提供商 API Keys ---
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "your_dashscope_api_key_here")

# --- 模型名称（默认） ---
# 全局默认模型名称，作为兜底配置
# 例如: "qwen3-max-preview"
CHAT_MODEL_NAME = "qwen3-max-preview"
# 例如: "text-embedding-v4"
EMBEDDING_MODEL_NAME = "text-embedding-v4"

# --- 按 Agent 的模型映射（可按需修改/扩展） ---
# 键为 Agent 名称（通常与类中传入的 name 一致，如 "DevAgent"）
# 值为该 Agent 使用的模型名称。未配置的 Agent 将回退到全局默认。
AGENT_CHAT_MODELS = {
    # 开发/实现类 Agent
    "DevAgent": os.getenv("CHAT_MODEL_DEVAGENT", CHAT_MODEL_NAME),
    # 需求分析类 Agent
    "RequirementAgent": os.getenv("CHAT_MODEL_REQUIREMENTAGENT", CHAT_MODEL_NAME),
    # 测试验证类 Agent
    "TestAgent": os.getenv("CHAT_MODEL_TESTAGENT", CHAT_MODEL_NAME),
    # 调度/编排类 Agent（如有）
    "OrchestratorAgent": os.getenv("CHAT_MODEL_ORCHESTRATORAGENT", CHAT_MODEL_NAME),
}

AGENT_EMBEDDING_MODELS = {
    # 向量化/RAG 相关任务默认使用统一 embedding 模型
    # 也可以为不同工作流指定不同的 embedding 模型
    "DevAgent": os.getenv("EMBEDDING_MODEL_DEVAGENT", EMBEDDING_MODEL_NAME),
    "RequirementAgent": os.getenv("EMBEDDING_MODEL_REQUIREMENTAGENT", EMBEDDING_MODEL_NAME),
    "TestAgent": os.getenv("EMBEDDING_MODEL_TESTAGENT", EMBEDDING_MODEL_NAME),
    "OrchestratorAgent": os.getenv("EMBEDDING_MODEL_ORCHESTRATORAGENT", EMBEDDING_MODEL_NAME),
}


def get_chat_model_name(agent_name: str | None = None) -> str:
    """
    根据 Agent 名称获取聊天模型名称；若未传入或未配置，返回全局默认。
    """
    if agent_name and agent_name in AGENT_CHAT_MODELS:
        return AGENT_CHAT_MODELS[agent_name]
    return CHAT_MODEL_NAME


def get_embedding_model_name(agent_name: str | None = None) -> str:
    """
    根据 Agent 名称获取 embedding 模型名称；若未传入或未配置，返回全局默认。
    """
    if agent_name and agent_name in AGENT_EMBEDDING_MODELS:
        return AGENT_EMBEDDING_MODELS[agent_name]
    return EMBEDDING_MODEL_NAME

# --- 向量数据库 ---
VECTOR_DB_PATH = "./src/vector_db"
RAG_DOCS_PATH = "./src/rag-docs"

# --- Agent 工作流 ---
MAX_RETRY_ATTEMPTS = 3  # Dev-Test 循环的最大重试次数

# 添加一个简单的检查，提醒用户配置密钥
if "your_" in DASHSCOPE_API_KEY:
    print(
        "\033[93m提醒: 您似乎还没有配置API密钥。请在项目根目录创建 .env 文件并填入您的密钥，或直接修改 src/config.py 文件。\033[0m")
