## 背景

捏脸业务是当前已有的 C 端业务模块，已具备完整的代码工程和业务逻辑。  
目标是基于现有业务知识，构建一个 自动化 AI Coding Agent 系统，实现：

- 对代码进行深度分析，生成业务文档（业务页面文档、技术架构文档、前端设计规范）
- 构建向量知识库（长期记忆）
- 使用 LangGraph.js 构建多角色 Agent 协同的代码生成与测试工作流
- 支持任务循环、自动修正以及人工干预
- 遵循 上下文工程 思路，区分长期记忆和短期记忆

## 技术选型

- 编程语言：Node.js
- 核心框架：
  - LangGraph.js — 多Agent工作流编排
  - LangChain.js — LLM调用与RAG检索
- 向量数据库：Chroma / Milvus / Weaviate（可选）
- 上下文工程：基于 Context-Engineering 方法论
- LLM：可使用 OpenAI / Claude / 其他 API

## 整体架构

### 架构总览

```mermaid
graph TD
    PM[产品经理
需求文档] --> RA[需求分析 Agent]
    RA -->|任务拆解 & Checklist| DEV[开发 Agent]
    DEV --> TEST[测试 Agent]
    TEST -->|通过| DONE[完成交付]
    TEST -->|未通过| DEV
    RA --> KB
    DEV --> KB
    TEST --> KB
    H[人工干预] -.-> RA
    H -.-> DEV
    H -.-> TEST

    subgraph 知识存储
        KB[向量数据库
长期记忆]
        STM[短期记忆
任务上下文]
    end
```

- 各 Agent 均可访问 长期记忆（向量知识库）
- 短期记忆 用于保存当前任务的进度和状态
- 人工可在任意节点介入

### 知识库设计

设计要点：

- 数据来源：代码分析生成的业务文档、技术架构文档、前端设计规范
- 切分：按语义切片（chunking）
- 嵌入：使用 Embedding 模型
- 存储：向量数据库
- 检索方式：RAG（检索增强生成）

```mermaid
graph LR
    Docs[业务文档集合] --> Split[文档切片]
    Split --> Embed[向量化]
    Embed --> VDB[向量数据库]
    Query[Agent 查询] --> QEmbed[查询向量化]
    QEmbed --> Search[相似度搜索]
    Search --> Result[返回相关文档]
```

示例代码（构建知识库）：

```javascript
import { Chroma } from "@langchain/community/vectorstores/chroma";
import { OpenAIEmbeddings } from "@langchain/openai";
import fs from "fs";

async function buildKnowledgeBase() {
  const docs = fs.readFileSync("./docs/business.md", "utf-8");
  const chunks = splitText(docs, 500); // 分片
  const embeddings = new OpenAIEmbeddings();
  const vectorStore = await Chroma.fromTexts(chunks, {}, embeddings);
  await vectorStore.persist();
}
```

### Workflow设计

```mermaid
sequenceDiagram
    participant PM as 需求分析 Agent
    participant DEV as 开发 Agent
    participant KB as 知识库(LTM)
    participant STM as 短期记忆(STM)

    PM->>KB: 查询业务文档
    PM->>STM: 存储任务需求
    DEV->>KB: 检索架构规范
    DEV->>STM: 更新任务进度
```

#### 各个Agent角色的设计

```mermaid
flowchart LR
    RA[RequirementAgent] --> DEV[DevAgent]
    DEV --> TEST[TestAgent]
    TEST -->|pass| END((END))
    TEST -->|fail| DEV
```

角色说明：

- RequirementAgent：解析需求 → 生成任务列表 & checklist
- DevAgent：根据任务生成代码
- TestAgent：执行测试，决定是否回退到开发

示例代码（LangGraph.js 节点定义）：

```javascript
import { StateGraph, Command } from "@langchain/langgraph";

const builder = new StateGraph({ tasks: [] });

builder.addNode("RequirementAgent", async (state) => {
  const tasks = await generateTasks(state.requirements);
  return new Command({ goto: "DevAgent", update: { tasks } });
});

builder.addNode("DevAgent", async (state) => {
  const code = await generateCode(state.tasks[0]);
  return new Command({ goto: "TestAgent", update: { code } });
});

builder.addNode("TestAgent", async (state) => {
  const pass = await runTests(state.code);
  return new Command({ goto: pass ? "END" : "DevAgent" });
});

const graph = builder.compile();
```

#### Workflow中长期记忆和短期记忆的划分

```mermaid
graph TB
    STM[短期记忆
当前任务上下文] --> Agent
    LTM[长期记忆
向量知识库] --> Agent
    Agent[任意Agent节点]
    subgraph 持久化
        CP[Checkpointer]
        KB[向量数据库]
    end
    Agent -->|更新| STM
    Agent -->|检索| LTM
    LTM --> KB
    STM --> CP
```

- 短期记忆：StateGraph 内的 state 对象
- 长期记忆：向量数据库检索的文档
- 持久化：checkpointer 保存状态，保证中断可恢复

示例代码（记忆调用）：

```javascript
const relatedDocs = await vectorStore.similaritySearch(taskDescription, 3);
state.context = [...state.context, ...relatedDocs];
```

#### 任务循环和人工介入

```mermaid
graph TD
    Start[任务开始] --> AI[AI 执行任务]
    AI --> DEC{需要人工帮助?}
    DEC -->|是| Human[人工回答]
    Human --> AI
    DEC -->|否| Next[继续执行]
    Next --> Verify[测试验收]
    Verify -->|失败| AI
    Verify -->|成功| End[完成]
```

```mermaid
sequenceDiagram
    participant DEV as 开发 Agent
    participant HUMAN as 人类
    participant TEST as 测试 Agent

    DEV->>DEV: 判断是否需要人工输入
    alt 需要人工
        DEV->>HUMAN: 抛出问题
        HUMAN-->>DEV: 人工回答
    end
    DEV->>TEST: 提交任务产出
    TEST-->>DEV: 验收结果（通过/不通过）
```

- 任意Agent可触发人工介入
- 人工介入后可继续执行任务
- 测试失败 → 回到开发 Agent

示例代码：
Node 定义（判断人工介入）

```javascript
import { Node } from "@langchain/langgraph";

const humanInterventionNode = new Node({
  name: "human_intervention",
  description: "判断并处理人工介入",
  run: async (context) => {
    const { taskContext, llm } = context;

    const decision = await llm.invoke(`
      任务内容：${taskContext}
      判断是否需要人工帮助，返回 JSON：{"needHuman": true/false, "question": "若需要，给出具体问题"}
    `);

    if (decision.needHuman) {
      // 暂停执行，等待人工输入
      context.state = "WAITING_FOR_HUMAN";
      context.humanQuestion = decision.question;
      return { status: "paused_for_human", question: decision.question };
    }

    return { status: "continue" };
  }
});

export default humanInterventionNode;
```

人工输入在代码中的表现

```javascript
// 人工输入回调接口
app.post("/human-response", async (req, res) => {
  const { taskId, answer } = req.body;
  
  // 将人工回答注入短期记忆
  shortTermMemory[taskId].push({
    role: "human",
    content: answer
  });

  // 恢复执行 AI 流程
  await workflow.resumeFromNode(taskId, "human_intervention");
  res.send({ status: "resumed" });
});
```
