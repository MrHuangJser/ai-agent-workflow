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

##### 3.2. 核心工具集与信息获取模式

- **知识库检索 (`retrieve_knowledge`)**: 定义在 `tools/rag_tool.py`，用于获取高阶、语义化的知识。
- **Shell 命令 (`execute_shell_command`)**: AgentScope 内置工具，用于执行 `ls`, `cat`, `grep` 等命令，获取精确的实时上下文。
- **Agent 协作工具**: 定义在 `tools/agent_tools.py`，是 `OrchestratorAgent` 用来委派任务给其他 Agent 的桥梁。下文将详细介绍。

`DevAgent`、`TestAgent` 和 `RequirementAgent` 都将配备 `retrieve_knowledge` 和 `execute_shell_command` 工具。
`OrchestratorAgent` 将配备 Agent 协作工具。

**a. `agents/orchestrator_agent.py` - OrchestratorAgent**

- **职责**: 流程控制中心。
- **实现关键**: 它的 `reply` 方法是整个系统的状态机，通过调用 `tools/agent_tools.py` 中的工具来分派任务，而不直接执行业务逻辑。

**b. `agents/requirement_agent.py` - RequirementAgent**

- **职责**: 解析需求，生成任务列表。
- **实现关键**: 将使用 `execute_shell_command` 查看相关文档或代码文件，并结合 `retrieve_knowledge` 获取的全局知识，生成更具上下文感知能力的任务列表。

**c. `agents/dev_agent.py` - DevAgent**

- **职责**: 根据任务描述和反馈编写/修改代码。
- **实现关键**: 将大量使用 `execute_shell_command` 工具 (例如 `ls`, `cat`, `grep`) 来探索现有代码、理解上下文，并使用 `retrieve_knowledge` 工具获取高阶设计规范。

**d. `agents/test_agent.py` - TestAgent**

- **职责**: 测试代码并生成报告。
- **实现关键**: 将使用 `execute_shell_command` 来运行测试命令 (如 `pytest`)、代码检查工具 (如 `ruff check .`)，并读取测试结果文件。

---

#### 4. 核心工具设计

##### 4.1. Agent 协作工具 (`tools/agent_tools.py`)

这个模块是实现 “Handoffs” 模式的核心，它将子 Agent 的工作封装成 `OrchestratorAgent` 可以调用的工具。这些工具函数内部会负责实例化对应的 Agent 并执行任务。

- `analyze_requirement(requirement_doc: str) -> str`:
  - **作用**: 调用 `RequirementAgent` 来分析原始需求。
  - **内部逻辑**: 实例化一个 `RequirementAgent`，将 `requirement_doc` 作为输入消息传递给它，等待其返回结果（JSON 格式的任务列表字符串），然后将该结果返回。

- `run_development_task(task_description: str, feedback: str = None) -> str`:
  - **作用**: 调用 `DevAgent` 来执行单个开发任务。
  - **内部逻辑**: 实例化一个 `DevAgent`，将 `task_description` 和可选的 `feedback` 组合成输入消息，调用 Agent，并返回其产出的代码字符串。

- `run_test_task(code: str) -> str`:
  - **作用**: 调用 `TestAgent` 来测试一段代码。
  - **内部逻辑**: 实例化一个 `TestAgent`，将 `code` 作为输入消息，调用 Agent，并返回其产出的 JSON 格式测试报告字符串。

##### 4.2. 知识库工具 (`tools/rag_tool.py`)

知识库功能将分为两部分：**启动时构建/更新** 和 **运行时检索**。

- **启动时构建/更新 (在 `main.py` 中调用)**: 应用启动时，会有一个初始化函数 (`initialize_vector_db`) 负责自动化地处理 `rag_docs` 目录下的文档。
- **运行时检索 (`retrieve_knowledge`)**: 封装成一个独立的工具，供所有需要它的 Agent 使用。

---

#### 5. 工作流与记忆实现 (核心逻辑)

**a. 短期记忆 (STM)**

每个 Agent 实例将拥有自己的 `agentscope.memory.InMemoryMemory`，用于记录其对话历史。

**b. 开发-测试循环**

这个核心循环将在 `OrchestratorAgent` 的 `reply` 方法中通过调用在 `agent_tools.py` 中定义的工具和条件判断来实现。

---

#### 6. 状态持久化与人工介入

- **状态持久化**: 在 `main.py` 中使用 `agentscope.session.JSONSession` 来保存和加载会话状态，实现任务的中断和恢复。
- **人工介入**: 任何 Agent 都可以通过向 `UserAgent` 发送消息来提问，`OrchestratorAgent` 负责协调这一过程，实现自然的人机交互。

---
