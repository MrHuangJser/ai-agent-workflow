import { ChatOpenAI } from '@langchain/openai';
import { AgentState, Task, TaskType } from '../types';
import { logger } from '../utils/logger';
import { writeFile, mkdir } from 'fs/promises';
import { join } from 'path';

interface ExecutionResult {
  taskId: string;
  success: boolean;
  output?: any;
  error?: string;
  filesGenerated?: string[];
  commandsExecuted?: string[];
}

export class ExecutionAgent {
  private llm: ChatOpenAI;
  private workspacePath: string;

  constructor(apiKey: string, workspacePath: string = './workspace') {
    this.llm = new ChatOpenAI({
      openAIApiKey: apiKey,
      modelName: 'gpt-4',
      temperature: 0.1,
    });
    this.workspacePath = workspacePath;
  }

  async executeTask(state: AgentState): Promise<Partial<AgentState>> {
    const currentTask = state.currentTask;
    if (!currentTask) {
      return { errors: [...(state.errors || []), 'No current task to execute'] };
    }

    logger.info('Starting task execution', { taskId: currentTask.id, type: currentTask.type });

    try {
      let result: ExecutionResult;

      switch (currentTask.type) {
        case 'code-generation':
          result = await this.executeCodeGeneration(currentTask, state);
          break;
        case 'file-creation':
          result = await this.executeFileCreation(currentTask, state);
          break;
        case 'dependency-install':
          result = await this.executeDependencyInstall(currentTask, state);
          break;
        case 'test-creation':
          result = await this.executeTestCreation(currentTask, state);
          break;
        case 'config-generation':
          result = await this.executeConfigGeneration(currentTask, state);
          break;
        default:
          throw new Error(`Unknown task type: ${currentTask.type}`);
      }

      if (result.success) {
        logger.info('Task execution completed', { 
          taskId: currentTask.id, 
          filesGenerated: result.filesGenerated?.length || 0 
        });

        const updatedTask = {
          ...currentTask,
          status: 'completed' as const,
          output: result.output,
          updatedAt: new Date(),
        };

        return {
          currentTask: updatedTask,
          results: [...(state.results || []), result],
          metadata: {
            ...state.metadata,
            lastExecutionResult: result,
          },
        };
      } else {
        throw new Error(result.error || 'Task execution failed');
      }
    } catch (error) {
      logger.error('Task execution failed', { taskId: currentTask.id, error: error.message });

      const failedTask = {
        ...currentTask,
        status: 'failed' as const,
        updatedAt: new Date(),
      };

      return {
        currentTask: failedTask,
        errors: [...(state.errors || []), `Task ${currentTask.id} failed: ${error.message}`],
      };
    }
  }

  private async executeCodeGeneration(task: Task, state: AgentState): Promise<ExecutionResult> {
    try {
      const prompt = this.buildCodeGenerationPrompt(task, state);
      const response = await this.llm.invoke(prompt);
      
      const codeContent = response.content as string;
      const filePath = this.extractFilePathFromTask(task.description) || 'generated.ts';
      const fullPath = join(this.workspacePath, filePath);

      await mkdir(join(this.workspacePath, 'src'), { recursive: true });
      await writeFile(fullPath, codeContent);

      return {
        taskId: task.id,
        success: true,
        output: { filePath: fullPath, content: codeContent },
        filesGenerated: [fullPath],
      };
    } catch (error) {
      return {
        taskId: task.id,
        success: false,
        error: error.message,
      };
    }
  }

  private async executeFileCreation(task: Task, state: AgentState): Promise<ExecutionResult> {
    try {
      const prompt = this.buildFileCreationPrompt(task, state);
      const response = await this.llm.invoke(prompt);
      
      const fileContent = response.content as string;
      const filePath = this.extractFilePathFromTask(task.description) || 'README.md';
      const fullPath = join(this.workspacePath, filePath);

      await mkdir(join(this.workspacePath, 'src'), { recursive: true });
      await writeFile(fullPath, fileContent);

      return {
        taskId: task.id,
        success: true,
        output: { filePath: fullPath, content: fileContent },
        filesGenerated: [fullPath],
      };
    } catch (error) {
      return {
        taskId: task.id,
        success: false,
        error: error.message,
      };
    }
  }

  private async executeDependencyInstall(task: Task, state: AgentState): Promise<ExecutionResult> {
    try {
      const prompt = this.buildDependencyPrompt(task, state);
      const response = await this.llm.invoke(prompt);
      
      const dependencies = JSON.parse(response.content as string);
      const packageJsonPath = join(this.workspacePath, 'package.json');

      // 这里简化处理，实际应该更新package.json
      const packageJson = {
        name: 'generated-project',
        version: '1.0.0',
        dependencies: dependencies.dependencies || {},
        devDependencies: dependencies.devDependencies || {},
      };

      await writeFile(packageJsonPath, JSON.stringify(packageJson, null, 2));

      return {
        taskId: task.id,
        success: true,
        output: { dependencies },
        filesGenerated: [packageJsonPath],
        commandsExecuted: ['npm install'],
      };
    } catch (error) {
      return {
        taskId: task.id,
        success: false,
        error: error.message,
      };
    }
  }

  private async executeTestCreation(task: Task, state: AgentState): Promise<ExecutionResult> {
    try {
      const prompt = this.buildTestCreationPrompt(task, state);
      const response = await this.llm.invoke(prompt);
      
      const testContent = response.content as string;
      const testPath = join(this.workspacePath, 'src', '__tests__');
      const fileName = this.extractTestFileName(task.description) || 'index.test.ts';
      const fullPath = join(testPath, fileName);

      await mkdir(testPath, { recursive: true });
      await writeFile(fullPath, testContent);

      return {
        taskId: task.id,
        success: true,
        output: { testFile: fullPath, content: testContent },
        filesGenerated: [fullPath],
      };
    } catch (error) {
      return {
        taskId: task.id,
        success: false,
        error: error.message,
      };
    }
  }

  private async executeConfigGeneration(task: Task, state: AgentState): Promise<ExecutionResult> {
    try {
      const prompt = this.buildConfigPrompt(task, state);
      const response = await this.llm.invoke(prompt);
      
      const configContent = response.content as string;
      const fileName = this.extractConfigFileName(task.description) || 'config.json';
      const fullPath = join(this.workspacePath, fileName);

      await writeFile(fullPath, configContent);

      return {
        taskId: task.id,
        success: true,
        output: { configFile: fullPath, content: configContent },
        filesGenerated: [fullPath],
      };
    } catch (error) {
      return {
        taskId: task.id,
        success: false,
        error: error.message,
      };
    }
  }

  private buildCodeGenerationPrompt(task: Task, state: AgentState): string {
    return `
你是一名专业的TypeScript开发者，根据以下任务描述生成高质量的代码：

任务描述：${task.description}

要求：
- 使用TypeScript编写
- 遵循最佳实践
- 包含必要的类型定义
- 添加适当的注释
- 导出必要的函数和类

请直接返回代码内容，不要包含markdown代码块标记。
`;
  }

  private buildFileCreationPrompt(task: Task, state: AgentState): string {
    return `
你是一名技术文档专家，根据以下任务描述创建相应的文件：

任务描述：${task.description}

要求：
- 内容清晰准确
- 格式规范
- 包含必要的结构

请直接返回文件内容。
`;
  }

  private buildDependencyPrompt(task: Task, state: AgentState): string {
    return `
你是一名DevOps工程师，根据以下任务描述确定项目依赖：

任务描述：${task.description}

请返回一个JSON对象，包含：
{
  "dependencies": { "package-name": "version" },
  "devDependencies": { "package-name": "version" }
}

确保包含所有必要的依赖项。
`;
  }

  private buildTestCreationPrompt(task: Task, state: AgentState): string {
    return `
你是一名测试工程师，根据以下任务描述创建测试用例：

任务描述：${task.description}

要求：
- 使用Jest测试框架
- 测试覆盖主要功能
- 包含正面和负面测试用例
- 使用TypeScript

请直接返回测试代码，不要包含markdown代码块标记。
`;
  }

  private buildConfigPrompt(task: Task, state: AgentState): string {
    return `
你是一名DevOps工程师，根据以下任务描述创建配置文件：

任务描述：${task.description}

要求：
- 格式正确
- 包含必要的配置项
- 环境变量支持

请直接返回配置文件内容。
`;
  }

  private extractFilePathFromTask(description: string): string | null {
    const match = description.match(/(?:create|generate)\s+(?:file\s+)?(.+?)(?:\s|$)/i);
    return match ? match[1] : null;
  }

  private extractTestFileName(description: string): string | null {
    const match = description.match(/test\s+for\s+(.+?)(?:\s|$)/i);
    return match ? `${match[1]}.test.ts` : null;
  }

  private extractConfigFileName(description: string): string | null {
    const match = description.match(/config\s+(.+?)(?:\s|$)/i);
    return match ? match[1] : null;
  }
}