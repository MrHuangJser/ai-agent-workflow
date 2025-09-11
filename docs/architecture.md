### 架构设计方案 (AI Coding Agent)

---

#### 1. 核心设计思想

我们将完全采纳您设计的以 `OrchestratorAgent` 为核心的中央编排模式。Agent 之间的协作将通过两种方式实现：

1. **任务分发 (Handoffs)**: `OrchestratorAgent` 将通过调用一个封装了子 Agent 的**工具 (Tool)** 来向其分派任务。这是实现可控、结构化工作流的最佳方式，符合 `agentscope-docs/workflow_handoffs.py` 中展示的模式。
2. **消息广播 (Broadcast)**: 在需要自由讨论或评审的场景（如果未来有需求），可以使用 `MsgHub`。但在当前的核心工作流中，我们将以工具调用为主。

#### 2. 项目文件结构

为了保证代码的模块化和可维护性，我建议采用以下文件结构：

```
/src/
├── main.py                     # 项目入口，负责初始化和启动OrchestratorAgent
├── config.py                   # 存放API Keys, 模型名称等配置信息
├── rag_docs/                   # [新] 存放RAG的原始文档
├── vector_db/                  # [更名] 存放ChromaDB等向量数据库文件
├── prompts/                    # 存放所有Agent的System Prompt
│   ├── orchestrator.txt
│   ├── requirement_agent.txt
│   ├── dev_agent.txt
│   └── test_agent.txt
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

**a. `agents/orchestrator_agent.py` - OrchestratorAgent**

- **职责**: 流程控制中心。
- **实现关键**:
  - 它的 `reply` 方法将是整个系统的 **状态机**。它会接收并解析 `TestAgent` 的测试报告。
  - 它不直接与其他 Agent 通信，而是调用定义在 `tools/agent_tools.py` 中的工具函数。这些工具函数内部会实例化并调用相应的子 Agent。
  - **短期记忆 (`memory`)**: `OrchestratorAgent` 的记忆将完整记录整个任务的生命周期。

**b. `agents/requirement_agent.py` - RequirementAgent**

- **职责**: 解析需求，生成任务列表。
- **实现关键**:
  - 它会装备一个定义在 `tools/rag_tool.py` 中的 `retrieve_knowledge` 工具，用于从 LTM 中查询背景知识。

**c. `agents/dev_agent.py` - DevAgent**

- **职责**: 根据任务描述和反馈编写/修改代码。
- **实现关键**:
  - 它同样会装备 `retrieve_knowledge` 工具，以查询技术规范和代码示例。

**d. `agents/test_agent.py` - TestAgent**

- **职责**: 测试代码并生成报告。
- **实现关键**:
  - 它的 `reply` 方法接收代码，然后可以调用静态分析工具或使用LLM生成并执行单元测试。
  - 它将使用 `structured_model` 参数来保证输出报告的格式统一。

---

#### 4. 知识库 (LTM) 实现 (含自动化向量流程)

知识库功能将分为两部分：**启动时构建/更新** 和 **运行时检索**。

##### 4.1. 启动时构建/更新 (在 `main.py` 中调用)

应用启动时，会有一个初始化函数 (`initialize_vector_db`) 负责自动化地处理 `rag_docs` 目录下的文档。流程如下：

1. **加载文档**: 使用 `LangChain` 的 `DirectoryLoader` 加载 `rag_docs` 目录下的所有文档。
2. **增量更新 (可选但建议)**: 通过比较文件修改时间或内容的哈希值，只对新增或修改过的文档进行处理，避免重复向量化。
3. **文本切片**: 将加载的文档切割成小的、语义完整的块。
4. **向量化与存储**: 将文本块向量化并存入位于 `vector_db` 目录的 `Chroma` 数据库中。

##### 4.2. 运行时检索 (在 `tools/rag_tool.py` 中实现)

检索功能将封装成一个独立的工具，供所有需要它的 Agent 使用。

**`tools/rag_tool.py`:**

```python
# tools/rag_tool.py
from agentscope.tool import ToolResponse, TextBlock
from langchain.vectorstores import Chroma
from langchain.embeddings import OpenAIEmbeddings
import config

# 这个 vector_store 对象将在 main.py 中被初始化并传入
global_vector_store = None

def set_vector_store(vector_store):
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
        return ToolResponse(content=[TextBlock(text="错误：向量数据库未初始化。")])

    docs = global_vector_store.similarity_search(query, k=k)
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

每个 Agent 实例将拥有自己的 `agentscope.memory.InMemoryMemory`，用于记录其对话历史。

**b. 开发-测试循环**

这个核心循环将在 `OrchestratorAgent` 的 `reply` 方法中通过 **工具调用** 和 **条件判断** 来实现。

**`agents/orchestrator_agent.py` (伪代码):**

```python
# agents/orchestrator_agent.py
# ... imports ...

class OrchestratorAgent(ReActAgent):
    # ... (初始化)
    
    async def reply(self, message: Msg) -> Msg:
        # 1. 初始需求 -> 分解任务
        if "task_list" not in self.memory:
            task_list_str = await self.toolkit.call_tool_function(
                "analyze_requirement", requirement_doc=message.content
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
        for i in range(config.MAX_RETRY_ATTEMPTS):
            code_output = await self.toolkit.call_tool_function(
                "run_development_task", task_description=current_task, feedback=feedback
            )
            
            test_result_str = await self.toolkit.call_tool_function(
                "run_test_task", code=code_output
            )
            test_result = json.loads(test_result_str)

            if test_result["pass"]:
                self.memory["current_task_index"] += 1
                # ... 任务成功逻辑 ...
                break 
            else:
                feedback = test_result["report"]
        
        # ... (处理循环结束后的逻辑) ...
```

---

#### 6. 状态持久化与人工介入

- **状态持久化**: 在 `main.py` 中使用 `agentscope.session.JSONSession` 来保存和加载会话状态，实现任务的中断和恢复。
- **人工介入**: 任何 Agent 都可以通过向 `UserAgent` 发送消息来提问，`OrchestratorAgent` 负责协调这一过程，实现自然的人机交互。

---
