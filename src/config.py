# src/config.py
import os
from dotenv import load_dotenv

# 从 .env 文件加载环境变量
# 建议您在项目根目录下创建一个 .env 文件来存放敏感信息
# 例如: DASHSCOPE_API_KEY=sk-xxxxxxxx
load_dotenv()

# --- LLM 提供商 API Keys ---
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")

# --- 模型名称 ---
# 在这里可以方便地切换不同的模型
# 例如: "qwen-max", "gpt-4-turbo", "claude-3-opus-20240229"
CHAT_MODEL_NAME = "qwen3-max-preview"
# 例如: "text-embedding-v2", "text-embedding-3-large"
EMBEDDING_MODEL_NAME = "text-embedding-v4"

# --- 向量数据库 ---
VECTOR_DB_PATH = "./src/vector_db"
RAG_DOCS_PATH = "./src/rag-docs"

# --- Agent 工作流 ---
MAX_RETRY_ATTEMPTS = 3  # Dev-Test 循环的最大重试次数

# 添加一个简单的检查，提醒用户配置密钥
if "your_" in DASHSCOPE_API_KEY:
    print(
        "\033[93m提醒: 您似乎还没有配置API密钥。请在项目根目录创建 .env 文件并填入您的密钥，或直接修改 src/config.py 文件。\033[0m")
