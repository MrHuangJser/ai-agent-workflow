### 架构设计方案 (AI Coding Agent)

---

#### 1. 核心设计思想

我们将完全采纳您设计的以 `OrchestratorAgent` 为核心的中央编排模式。Agent 之间的协作将通过两种方式实现：

1. **任务分发 (Handoffs)**: `OrchestratorAgent` 将通过调用一个封装了子 Agent 的**工具 (Tool)** 来向其分派任务。这是实现可控、结构化工作流的最佳方式，符合 `agentscope-docs/workflow_handoffs.py` 中展示的模式。
2. **消息广播 (Broadcast)**: 在需要自由讨论或评审的场景（如果未来有需求），可以使用 `MsgHub`。但在当前的核心工作流中，我们将以工具调用为主。

#### 2. 项目文件结构

为了保证代码的模块化和可维护性，我建议采用以下文件结构：

```
/
├── main.py                     # 项目入口，负责初始化和启动OrchestratorAgent
├── config.py                   # 存放API Keys, 模型名称等配置信息
├── prompts/                    # 存放所有Agent的System Prompt
│   ├── orchestrator.txt
│   ├── requirement_agent.txt
│   ├── dev_agent.txt
│   └── test_agent.txt
├── knowledge_base/             # 存放向量数据库及原始文档
│   ├── source_docs/
│   └── vector_db/
├── agents/
│   ├── __init__.py
│   ├── orchestrator_agent.py
│   ├── requirement_agent.py
│   ├── dev_agent.py
│   └── test_agent.py
└── tools/
    ├── __init__.py
    ├── rag_tool.py
    └── agent_tools.py
```

---

#### 3. Agent 详细设计

所有 Agent 都将继承 `agentscope.agent.ReActAgent`，因为它内置了强大的 ReAct 逻辑和工具调用能力。

##### 3.1. Prompt 管理

我们将创建一个 `prompts` 目录来集中管理所有 Agent 的系统提示 (System Prompt)。每个 Agent 的提示词将存储在对应的 `.txt` 文件中 (例如 `prompts/dev_agent.txt`)。

在 Agent 初始化时，程序会从这些文件中读取内容并作为 `sys_prompt` 参数传入。这样做可以实现 Prompt 与 Agent 逻辑的分离，便于快速迭代和优化提示词，而无需修改 Python 代码。

**加载示例:**

```python
# agents/dev_agent.py
from agentscope.agent import ReActAgent

# 在模块加载时读取文件
with open("../prompts/dev_agent.txt", "r", encoding="utf-8") as f:
    DEV_AGENT_PROMPT = f.read()

class DevAgent(ReActAgent):
    def __init__(self, ...):
        super().__init__(
            name="DevAgent",
            sys_prompt=DEV_AGENT_PROMPT,
            ...
        )
```

**a. `agents/orchestrator_agent.py` - OrchestratorAgent**

- **职责**: 流程控制中心。
- **实现关键**:
  - 它的 `reply` 方法将是整个系统的 **状态机**。它会接收并解析 `TestAgent` 的测试报告。
  - 它不直接与其他 Agent 通信，而是调用定义在 `tools/agent_tools.py` 中的工具函数，例如 `analyze_requirement(requirement_doc)` 和 `run_development_task(task_description, feedback)`。这些工具函数内部会实例化并调用相应的子 Agent。
  - **短期记忆 (`memory`)**: `OrchestratorAgent` 的记忆将完整记录整个任务的生命周期，包括任务分解、代码生成、测试反馈和修正的所有步骤。

**b. `agents/requirement_agent.py` - RequirementAgent**

- **职责**: 解析需求，生成任务列表。
- **实现关键**:
  - 它将被 `tools.agent_tools.analyze_requirement` 函数实例化和调用。
  - 它会装备一个定义在 `tools/rag_tool.py` 中的 `retrieve_knowledge` 工具，用于从 LTM 中查询背景知识。
  - 它的 `reply` 方法将接收原始需求，调用 `retrieve_knowledge` 工具，构建 Prompt，然后调用 LLM 生成结构化的任务列表，并作为最终结果返回。

**c. `agents/dev_agent.py` - DevAgent**

- **职责**: 根据任务描述和反馈编写/修改代码。
- **实现关键**:
  - 它将被 `tools.agent_tools.run_development_task` 函数实例化和调用。
  - 它同样会装备 `retrieve_knowledge` 工具，以查询技术规范和代码示例。
  - 它的 `reply` 方法会接收包含任务描述和可选测试反馈的 `message`。它会利用这些信息和从 LTM 检索到的知识来生成或修正代码。

**d. `agents/test_agent.py` - TestAgent**

- **职责**: 测试代码并生成报告。
- **实现关键**:
  - 它将被 `tools.agent_tools.run_test_task` 函数实例化和调用。
  - 它的 `reply` 方法接收代码，然后可以：
        1. 调用 **静态分析工具** (如 `ruff`, `pylint`)。
        2. 调用 LLM **生成单元测试** 并使用 `execute_python_code` 工具执行。
  - 最后，它会返回一个结构化的 JSON 报告，如 `{"pass": false, "report": "..."}`。为了保证格式，我们会使用 `structured_model` 参数，这在 `task_agent.py` 中有详细说明。

---

#### 4. 知识库 (LTM) 实现

我们将把 RAG 功能封装成一个独立的工具，供所有需要它的 Agent 使用。

**`tools/rag_tool.py`:**

```python
# tools/rag_tool.py
from agentscope.tool import ToolResponse, TextBlock
# 假设使用 ChromaDB 和 LangChain/LlamaIndex
import chromadb
from langchain.vectorstores import Chroma
from langchain.embeddings import OpenAIEmbeddings # 或者其他 embedding
from config import OPENAI_API_KEY

# --- LTM 构建过程 (离线完成) ---
# 1. 加载 source_docs/ 中的文档
# 2. 切片 (Splitting)
# 3. 向量化 (Embedding) & 存入 ChromaDB

# --- LTM 检索工具 ---
# 在 main.py 中初始化 vector_store
vector_store = Chroma(
    persist_directory="./knowledge_base/vector_db",
    embedding_function=OpenAIEmbeddings(api_key=OPENAI_API_KEY)
)

def retrieve_knowledge(query: str, k: int = 3) -> ToolResponse:
    """
    从向量知识库中检索与查询相关的知识。

    Args:
        query (str): 用于检索的查询文本。
        k (int): 返回的相关文档数量。
    """
    docs = vector_store.similarity_search(query, k=k)
    retrieved_content = "
---
".join([doc.page_content for doc in docs])
    
    return ToolResponse(
        content=[
            TextBlock(
                type="text",
                text=f"从知识库中检索到以下内容：
{retrieved_content}"
            )
        ]
    )
```

这个 `retrieve_knowledge` 函数将被注册到 `RequirementAgent` 和 `DevAgent` 的 `Toolkit` 中。

---

#### 5. 工作流与记忆实现 (核心逻辑)

**a. 短期记忆 (STM)**

每个 Agent 实例将拥有自己的 `agentscope.memory.InMemoryMemory`。这完全符合 AgentScope 的设计，Agent 的对话历史就是其短期记忆。

**b. 开发-测试循环**

这个核心循环将在 `OrchestratorAgent` 的 `reply` 方法中通过 **工具调用** 和 **条件判断** 来实现。

**`agents/orchestrator_agent.py` (伪代码):**

```python
# agents/orchestrator_agent.py
from agentscope.agent import ReActAgent
from agentscope.message import Msg
from tools.agent_tools import analyze_requirement, run_development_task, run_test_task
import json

class OrchestratorAgent(ReActAgent):
    
    # ... (初始化, sys_prompt, model, etc.)
    # toolkit 中注册了 analyze_requirement, run_development_task, run_test_task
    
    async def reply(self, message: Msg) -> Msg:
        # 1. 初始需求 -> 分解任务
        if "task_list" not in self.memory: # 假设用 memory 存状态
            task_list_str = await self.toolkit.call_tool_function(
                "analyze_requirement",
                requirement_doc=message.content
            )
            self.memory["task_list"] = json.loads(task_list_str)
            self.memory["current_task_index"] = 0

        # 2. 按顺序处理任务
        task_index = self.memory["current_task_index"]
        if task_index >= len(self.memory["task_list"]):
            return Msg(self.name, "所有任务已完成！", "assistant")

        current_task = self.memory["task_list"][task_index]
        
        # 3. 开发-测试循环
        feedback = None
        for i in range(MAX_RETRY_ATTEMPTS): # 设置最大重试次数
            # 调用 DevAgent 工具
            code_output = await self.toolkit.call_tool_function(
                "run_development_task",
                task_description=current_task,
                feedback=feedback
            )
            
            # 调用 TestAgent 工具
            test_result_str = await self.toolkit.call_tool_function(
                "run_test_task",
                code=code_output
            )
            test_result = json.loads(test_result_str)

            if test_result["pass"]:
                # 测试通过，跳出循环，处理下一个任务
                self.memory["current_task_index"] += 1
                # ... (返回成功信息) ...
                break 
            else:
                # 测试失败，准备反馈，进入下一次循环
                feedback = test_result["report"]
        
        # ... (处理循环结束后的逻辑) ...
```

---

#### 6. 状态持久化与人工介入

- **状态持久化**: 正如 `task_state.py` 文档所示，我们可以在 `main.py` 中使用 `agentscope.session.JSONSession`。在程序启动时加载上一次的会话状态，在程序结束前保存所有 Agent 的状态。这可以轻松实现任务的中断和恢复。
- **人工介入**: AgentScope 的 `UserAgent` 让此功能非常自然。在任何子 Agent（如 `DevAgent`）的逻辑中，如果检测到需要人工输入，它可以直接向 `UserAgent` 返回一个提问消息。`OrchestratorAgent` 在收到这个特殊消息后，将其转发给用户，等待输入，然后将用户的回答传回给子 Agent，从而恢复流程。

---
