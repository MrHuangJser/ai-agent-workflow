# AI Coding Agent System Overview (AgentScope)

This document provides a comprehensive overview of the AI Coding Agent system, detailing its requirements, architecture, and core design principles, primarily leveraging the AgentScope framework.

## 1. Background and Goals

The primary objective is to build an automated AI Coding Agent system based on existing business knowledge. Key functionalities include:

* **Codebase Analysis**: Automatically generate business documentation, technical architecture documentation, and frontend design specifications from existing codebases.
* **Knowledge Base Construction**: Build a vector knowledge base (Long-Term Memory - LTM) from generated documentation.
* **Multi-Agent Workflow**: Utilize the **AgentScope** framework to construct a collaborative code generation and testing workflow involving multiple agents.
* **Development-Test-Fix Loop**: Support an iterative development cycle with automatic correction capabilities.
* **Human Intervention**: Allow for manual intervention at critical junctures to ensure process control.
* **Context Engineering**: Clearly delineate and utilize Long-Term Memory (knowledge base) and Short-Term Memory (task context).

## 2. Technical Stack

* **Programming Language**: Python
* **Core Frameworks**:
  * **AgentScope**: For multi-agent definition, communication, and workflow orchestration.
  * **LangChain / LlamaIndex (Python)**: For LLM invocation, document loading, chunking, and RAG retrieval.
* **Vector Database**: Chroma / Milvus / Weaviate (one to be selected).
* **Context Engineering**: Adherence to the Context-Engineering methodology.
* **LLM**: Configurable via AgentScope to support OpenAI, Claude, Qwen, and other model APIs.

## 3. Overall Architecture (AgentScope-based)

The system adopts a central orchestration pattern with an `OrchestratorAgent` acting as the project manager, driving the process, distributing tasks, and making decisions. Agent collaboration is primarily achieved through **task handoffs** via tool calls, with `MsgHub` available for broader communication if needed in the future.

```mermaid
graph TD
    subgraph AgentScope Workflow
        U[用户 UserAgent] --> O[编排 Agent <br/> OrchestratorAgent]
        O --> RA[需求分析 Agent <br/> RequirementAgent]
        RA -->|任务列表| O
        O --> DEV[开发 Agent <br/> DevAgent]
        DEV -->|代码产出| TEST[测试 Agent <br/> TestAgent]
        TEST -->|测试结果| O
        O -- "通过" --> DONE[完成交付]
        O -- "不通过，附带失败信息" --> DEV
    end

    subgraph 知识存储
        KB[向量数据库 <br/> 长期记忆 (LTM)]
        STM[消息历史 <br/> 短期记忆 (STM)]
    end

    %% Agent 与知识库的交互
    RA <--> KB
    DEV <--> KB
    TEST <--> KB

    %% 人工干预通过编排Agent进行
    H[人工干预] -- "通过UserAgent" --> O
```

**Core Design Principles**:

* **Central Orchestration**: `OrchestratorAgent` is the central control point, managing the flow.
* **Message-Driven**: Agents communicate by passing messages.
* **Natural Human-Agent Interaction**: `UserAgent` seamlessly integrates human operators into the workflow.
* **Task Handoffs**: `OrchestratorAgent` delegates tasks by calling encapsulated tools that represent sub-agents.

## 4. Project File Structure

The project adheres to a modular and maintainable file structure:

```
/src/
├── main.py                     # Project entry point, initializes and starts OrchestratorAgent
├── config.py                   # Stores API Keys, model names, etc.
├── rag_docs/                   # Stores raw documents for RAG
├── vector_db/                  # Stores vector database files (e.g., ChromaDB)
├── prompts/                    # Stores System Prompts for all Agents
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
    ├── rag_tool.py             # Knowledge retrieval tool
    └── agent_tools.py          # Agent collaboration tools
```

## 5. Agent Detailed Design

All agents inherit from `agentscope.agent.ReActAgent` for ReAct logic and tool calling capabilities.

### 5.1. Prompt Management

System prompts for all agents are centrally managed in the `prompts/` directory, with each agent's prompt stored in a dedicated `.txt` file (e.g., `prompts/dev_agent.txt`).

### 5.2. Core Toolset and Information Acquisition

* **Knowledge Base Retrieval (`retrieve_knowledge`)**: Defined in `tools/rag_tool.py`, used for high-level, semantic knowledge.
* **Shell Commands (`execute_shell_command`)**: AgentScope built-in tool for executing commands like `ls`, `cat`, `grep` to obtain precise real-time context.
* **Agent Collaboration Tools**: Defined in `tools/agent_tools.py`, serving as bridges for `OrchestratorAgent` to delegate tasks to other agents.

`DevAgent`, `TestAgent`, and `RequirementAgent` are equipped with `retrieve_knowledge` and `execute_shell_command`. `OrchestratorAgent` is equipped with Agent collaboration tools.

### 5.3. Agent Roles and Responsibilities

* **`OrchestratorAgent` (orchestrator_agent.py)**:
  * **Responsibilities**: Receives user requirements, calls `RequirementAgent` to decompose them, manages task queues, dispatches tasks, forwards code to `TestAgent`, decides on task completion or re-assignment based on test results (forming a loop), and interacts with `UserAgent` for human intervention.
  * **Implementation Key**: Its `reply` method acts as the system's state machine, delegating tasks via tools in `tools/agent_tools.py`.

* **`RequirementAgent` (requirement_agent.py)**:
  * **Responsibilities**: Parses raw requirements, queries LTM for business context/specifications, uses LLM to generate structured task lists, and returns them to `OrchestratorAgent`.
  * **Implementation Key**: Uses `execute_shell_command` to inspect documents/code and `retrieve_knowledge` for global context to generate context-aware task lists.

* **`DevAgent` (dev_agent.py)**:
  * **Responsibilities**: Receives development tasks (potentially with test feedback), queries LTM for technical architecture/code standards, constructs prompts with task requirements and context, calls LLM to generate code, and returns code blocks.
  * **Implementation Key**: Extensively uses `execute_shell_command` (e.g., `ls`, `cat`, `grep`) to explore code and `retrieve_knowledge` for high-level design specifications.

* **`TestAgent` (test_agent.py)**:
  * **Responsibilities**: Receives code from `DevAgent`, executes tests (static analysis, LLM-generated unit tests, pre-defined test cases), and generates structured test reports.
  * **Implementation Key**: Uses `execute_shell_command` to run test commands (e.g., `pytest`), code linters (e.g., `ruff check .`), and read test result files.

## 6. Knowledge Base Design (Long-Term Memory - LTM)

The knowledge base is decoupled from the agent framework and serves as a service for agents.

### 6.1. Building Process

```mermaid
graph LR
    Docs[业务/技术文档集合] --> Split[语义化文档切片]
    Split --> Embed[向量化 (Embedding)]
    Embed --> VDB[存入向量数据库]
```

### 6.2. Retrieval Process (RAG)

Agents interact with LTM by calling RAG functions within their `reply` methods.

```mermaid
graph LR
    Query[Agent 查询 <br/> "实现用户登录功能"] --> QEmbed[查询向量化]
    QEmbed --> Search[在向量数据库中<br/>进行相似度搜索]
    VDB[向量数据库] --> Search
    Search --> Result[返回相关文档片段]
```

## 7. Workflow Memory Management

AgentScope naturally maps to short-term and long-term memory.

```mermaid
graph TB
    STM[短期记忆 <br/> Agent 的 Message History] --> Agent
    LTM[长期记忆 <br/> 向量知识库 (外部调用)] --> Agent
    Agent[任意 Agent 节点]

    subgraph 持久化存储
        MSG[消息历史日志]
        KB[向量数据库]
    end

    Agent -- "对话交互" --> |更新| STM
    Agent -- "RAG查询" --> |检索| LTM
    LTM --> KB
    STM --> MSG
```

* **Short-Term Memory (STM)**: Corresponds to each Agent's `memory` attribute in AgentScope, automatically recording the full conversation history and forming the current task context. `OrchestratorAgent`'s memory records the entire task lifecycle. AgentScope's memory supports persistence for task interruption and resumption.
* **Long-Term Memory (LTM)**: Corresponds to the external, independent vector knowledge base. It is stateless and passively queried via RAG functions when needed.

## 8. Task Loop and Human Intervention

### 8.1. Task Loop (Development-Test)

The task loop is driven by `OrchestratorAgent`'s decision logic.

1. `OrchestratorAgent` sends a development task to `DevAgent`.
2. `DevAgent` replies with code; `OrchestratorAgent` forwards it to `TestAgent`.
3. `TestAgent` replies with test results.
4. `OrchestratorAgent` checks results:
    * If **failed**, the failure report and original task are **re-sent** to `DevAgent`, forming a loop.
    * If **successful**, the loop ends, and the next task is processed.

### 8.2. Human Intervention

Implemented via `UserAgent`, ensuring a natural flow without special state management.

* **Trigger**: Any agent can decide to request human help within its `reply` method (e.g., `if ambiguity_detected:`).
* **Execution**: The agent needing help sends a question message directly to `UserAgent`.
* **Pause and Resume**: AgentScope's `msghub` automatically outputs the question to the console and waits for user input. After user input, `UserAgent` returns the answer as a message to the querying agent, and the workflow automatically resumes.

### 8.3. Agent Lifecycle and Information Flow

* **`OrchestratorAgent` (Long Lifecycle)**: A single instance instantiated in `main.py`, its lifecycle matches the application's. Its STM (`memory`) records all task dispatches, code generations, test results, and correction history, serving as the project's "master ledger."
* **Worker Agents (`DevAgent`, `TestAgent`, etc. - Short Lifecycle)**: These are **temporary, task-scoped** instances. When `OrchestratorAgent` calls a collaboration tool (e.g., `run_development_task`), the tool function **internally creates a new** instance of the respective agent. Upon task completion, the worker agent returns the result, and its lifecycle ends. This ensures high isolation, pure context, and simplified state management.
* **Core Information Flow**: `OrchestratorAgent`'s memory is updated by recording its **tool calls** and the **results returned by tools**. Worker Agent outputs (e.g., code, test reports) are returned as tool results and automatically recorded in `OrchestratorAgent`'s memory, driving its next decisions.

## 9. State Persistence and Human Intervention (Advanced)

* **State Persistence**: `agentscope.session.JSONSession` is used in `main.py` to save and load session states.
* **Human Intervention (Escalation Mechanism)**: Worker agents do not directly interact with the user. If human clarification is needed, they return a specific JSON object (e.g., `{"status": "clarification_needed", "question": "..."}`). `OrchestratorAgent`, as the sole user interface, receives this signal, queries `UserAgent`, and passes the user's response to the worker agent in the next task round.
