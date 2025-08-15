import { ChatOpenAI } from '@langchain/openai';
import { StateGraph } from '@langchain/langgraph';
import { z } from 'zod';
import { AgentState } from '../types';
import { logger } from '../utils/logger';
import { generateTaskId } from '../utils/id-generator';

const TaskAnalysisSchema = z.object({
  tasks: z.array(z.object({
    id: z.string(),
    description: z.string(),
    type: z.enum(['code-generation', 'file-creation', 'dependency-install', 'test-creation', 'config-generation']),
    complexity: z.enum(['low', 'medium', 'high']),
    estimatedHours: z.number().min(0),
    dependencies: z.array(z.string()),
    technologyStack: z.array(z.string()),
    requirements: z.array(z.string()),
  })),
});

export class AnalysisAgent {
  private llm: ChatOpenAI;

  constructor(apiKey: string) {
    this.llm = new ChatOpenAI({
      openAIApiKey: apiKey,
      modelName: 'gpt-4',
      temperature: 0.1,
    });
  }

  async analyzeRequirements(state: AgentState): Promise<Partial<AgentState>> {
    logger.info('Starting requirement analysis', { userInput: state.userInput });

    try {
      const prompt = this.buildAnalysisPrompt(state.userInput);
      const response = await this.llm.invoke(prompt);
      
      const analysis = TaskAnalysisSchema.parse(
        JSON.parse(response.content as string)
      );

      const tasks = analysis.tasks.map(task => ({
        id: task.id || generateTaskId(),
        description: task.description,
        type: task.type,
        complexity: task.complexity,
        estimatedHours: task.estimatedHours,
        dependencies: task.dependencies,
        status: 'pending' as const,
        createdAt: new Date(),
        updatedAt: new Date(),
      }));

      logger.info('Requirement analysis completed', { taskCount: tasks.length });

      return {
        tasks,
        metadata: {
          ...state.metadata,
          analysisCompleted: true,
          taskCount: tasks.length,
          estimatedTotalHours: tasks.reduce((sum, task) => sum + task.estimatedHours, 0),
        },
      };
    } catch (error) {
      logger.error('Requirement analysis failed', { error: error.message });
      return {
        errors: [...(state.errors || []), `Analysis failed: ${error.message}`],
      };
    }
  }

  private buildAnalysisPrompt(userInput: string): string {
    return `
你是一名专业的软件架构师，负责将用户需求拆解为可执行的技术任务。

用户需求：${userInput}

请分析这个需求并将其拆解为具体的技术任务。每个任务应该：
1. 有明确的描述和目标
2. 指定任务类型（代码生成、文件创建、依赖安装、测试创建、配置生成）
3. 评估复杂度（低、中、高）
4. 估计完成时间（小时）
5. 识别依赖关系
6. 指定所需技术栈
7. 列出具体要求

返回格式必须是有效的JSON，结构如下：
{
  "tasks": [
    {
      "id": "task_xxx",
      "description": "任务描述",
      "type": "code-generation|file-creation|dependency-install|test-creation|config-generation",
      "complexity": "low|medium|high",
      "estimatedHours": 2,
      "dependencies": ["task_id_1", "task_id_2"],
      "technologyStack": ["typescript", "react"],
      "requirements": ["实现用户认证功能", "使用JWT令牌"]
    }
  ]
}

请确保：
- 任务粒度适中，每个任务可在2-8小时内完成
- 依赖关系准确，避免循环依赖
- 技术栈具体明确
- 要求清晰可验证

分析用户需求并生成任务列表：`;
  }
}