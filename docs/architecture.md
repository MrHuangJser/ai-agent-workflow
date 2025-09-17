# 架构设计方案 (AI Coding Agent)

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

##### 3.3. Agent 定义

**a. `agents/orchestrator_agent.py` - OrchestratorAgent**

- **职责**: 流程控制中心。
- **实现关键**: 它的 `reply` 方法是整个系统的状态机，通过调用 `tools/agent_tools.py` 中的工具来分派任务，而不直接执行业务逻辑。

**b. `agents/requirement_agent.py` - RequirementAgent**

- **职责**: 解析需求，进行最小澄清并产出小步可验证的实施计划（结构化 JSON + Markdown）。
- **设计说明**: 详见单独文档《RequirementAgent 架构说明》（docs/requirement_agent.md）。

**c. `agents/dev_agent.py` - DevAgent**

- **职责**: 以小步增量实现/修复并完成最小验证与自愈迭代。
- **设计说明**: 详见单独文档《DevAgent 架构说明》（docs/dev_agent.md）。

**d. `agents/test_agent.py` - TestAgent**

- **职责**: 测试代码并生成报告。
- **实现关键**: 将使用 `execute_shell_command` 来运行测试命令 (如 `pytest`)、代码检查工具 (如 `ruff check .`)，并读取测试结果文件。

---

#### 4. Agent 生命周期与信息流

这是一个核心设计决策，用于确保系统的稳定性和可维护性。

- **OrchestratorAgent (长生命周期)**: 在 `main.py` 中被实例化，且**只有一个实例**。它的生命周期与整个应用程序相同。它的短期记忆 (`memory`) 记录了所有任务的派发、代码生成、测试结果和修正历史，是整个项目的“总账本”。

- **Worker Agents (`DevAgent`, `TestAgent`, etc. - 短生命周期)**: 它们是**临时的、任务范围的**实例。当 `OrchestratorAgent` 调用一个协作工具时（例如 `run_development_task`），这个工具函数会**在内部创建一个全新的** `DevAgent` 实例。任务完成后，`DevAgent` 实例返回结果，然后其生命周期结束。这种模式有巨大优势：
  - **高度隔离性**: 每个任务都由一个“全新”的 Agent 来处理，彻底杜绝了上一个任务的上下文泄露到当前任务的风险。
  - **上下文纯净**: Worker Agent 每次都只接收为当前任务精确提供的上下文，避免了被过时或无关的信息干扰。
  - **简化状态管理**: 我们只需关心 `OrchestratorAgent` 的状态，无需管理和重置 Worker Agent 的状态。

- **核心信息流**: `OrchestratorAgent` 的记忆是通过记录自己**调用工具的动作**和**工具返回的结果**来更新的。Worker Agent 的最终产出（如代码、测试报告）会作为工具结果返回，并被 `OrchestratorAgent` 自动记录到自己的记忆中，从而驱动它做出下一步决策。

---

#### 5. 核心工具设计

##### 5.1. Agent 协作工具 (`tools/agent_tools.py`)

这个模块是实现 “Handoffs” 模式的核心，它将子 Agent 的工作封装成 `OrchestratorAgent` 可以调用的工具。这些工具函数内部会负责实例化对应的 Agent 并执行任务。

- `analyze_requirement(requirement_doc: str) -> str`
- `run_development_task(task_description: str, feedback: str = None) -> str`
- `run_test_task(code: str) -> str`

##### 5.2. 知识库工具 (`tools/rag_tool.py`)

- **启动时构建/更新 (`initialize_vector_db`)**: 在 `main.py` 中调用，自动化处理 `rag_docs` 目录下的文档。
- **运行时检索 (`retrieve_knowledge`)**: 封装成独立的工具，供 Agent 在运行时调用。

---

#### 6. 工作流与记忆实现 (核心逻辑)

**a. 短期记忆 (STM)**: 每个 Agent 实例将拥有自己的 `agentscope.memory.InMemoryMemory`。

**b. 开发-测试循环**: 这个核心循环将在 `OrchestratorAgent` 的 `reply` 方法中通过调用在 `agent_tools.py` 中定义的工具和条件判断来实现。

---

#### 7. 状态持久化与人工介入

- **状态持久化**: 在 `main.py` 中使用 `agentscope.session.JSONSession` 来保存和加载会话状态。
- **人工介入 (向上汇报机制)**: 为了保证清晰的指挥链，Worker Agent 不会直接与用户交互。当需要人工澄清时，它会返回一个特定格式的JSON对象（例如 `{"status": "clarification_needed", "question": "..."}`）来向上“汇报”问题。`OrchestratorAgent` 在接收到这个信号后，作为唯一的用户接口，负责向 `UserAgent` 提问，并将用户的回答在下一轮任务中传递给 Worker Agent。

---
