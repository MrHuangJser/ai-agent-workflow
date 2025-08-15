import { ChatOpenAI } from '@langchain/openai';
import { RunnableConfig } from '@langchain/core/runnables';
import { BaseMessage, HumanMessage, AIMessage } from '@langchain/core/messages';
import { AutoCodingState } from './state';
import { generateTaskId } from '../utils/id-generator';

export interface Task {
  id: string;
  description: string;
  type: 'code-generation' | 'file-creation' | 'dependency-install' | 'test-creation' | 'config-generation';
  complexity: 'low' | 'medium' | 'high';
  estimatedHours: number;
  dependencies: string[];
  status: 'pending' | 'in-progress' | 'completed' | 'failed';
  output?: any;
  validation?: ValidationResult;
  createdAt: Date;
  updatedAt: Date;
}

export interface ValidationResult {
  score: number;
  passed: boolean;
  issues: Array<{
    severity: 'error' | 'warning' | 'info';
    message: string;
    file?: string;
    line?: number;
  }>;
  suggestions: string[];
}

export interface TaskResult {
  taskId: string;
  success: boolean;
  output?: any;
  error?: string;
  filesGenerated?: string[];
  commandsExecuted?: string[];
}

export class AnalysisNode {
  private llm: ChatOpenAI;

  constructor(apiKey: string) {
    this.llm = new ChatOpenAI({
      openAIApiKey: apiKey,
      modelName: 'gpt-4',
      temperature: 0.1,
    });
  }

  async invoke(state: AutoCodingState): Promise<Partial<AutoCodingState>> {
    const prompt = this.buildAnalysisPrompt(state.userInput);
    
    const response = await this.llm.invoke([
      new HumanMessage(prompt)
    ]);

    try {
      const analysis = JSON.parse(response.content as string);
      const tasks: Task[] = analysis.tasks.map((task: any) => ({
        id: task.id || generateTaskId(),
        description: task.description,
        type: task.type,
        complexity: task.complexity,
        estimatedHours: task.estimatedHours,
        dependencies: task.dependencies || [],
        status: 'pending',
        createdAt: new Date(),
        updatedAt: new Date(),
      }));

      return {
        tasks,
        messages: [...state.messages, new AIMessage(`Analyzed requirements into ${tasks.length} tasks`)],
        metadata: {
          ...state.metadata,
          totalTasks: tasks.length,
        }
      };
    } catch (error) {
      return {
        errors: [...state.errors, `Analysis failed: ${(error as Error).message}`],
        messages: [...state.messages, new AIMessage(`Analysis failed: ${(error as Error).message}`)]
      };
    }
  }

  private buildAnalysisPrompt(userInput: string): string {
    return `Analyze the following user request and break it down into specific technical tasks.

User Request: ${userInput}

Please provide a JSON response with the following structure:
{
  "tasks": [
    {
      "id": "task_1",
      "description": "Brief task description",
      "type": "code-generation|file-creation|dependency-install|test-creation|config-generation",
      "complexity": "low|medium|high",
      "estimatedHours": 2,
      "dependencies": ["task_id_1", "task_id_2"],
      "technologyStack": ["typescript", "react"],
      "requirements": ["specific requirement 1", "specific requirement 2"]
    }
  ]
}

Ensure each task is:
- Specific and actionable
- Has clear deliverables
- Estimated reasonably (2-8 hours)
- Has accurate dependencies
- Uses appropriate technology stack`;
  }
}

export class PlanningNode {
  invoke(state: AutoCodingState): Partial<AutoCodingState> {
    const tasks = state.tasks;
    const executionOrder = this.getExecutionOrder(tasks);
    const parallelGroups = this.identifyParallelGroups(tasks, executionOrder);
    const criticalPath = this.findCriticalPath(tasks);

    const executionPlan = {
      tasks: executionOrder,
      parallelGroups,
      criticalPath,
      riskFactors: this.identifyRiskFactors(tasks),
    };

    return {
      executionPlan,
      messages: [...state.messages, new AIMessage(`Created execution plan with ${tasks.length} tasks`)],
    };
  }

  private getExecutionOrder(tasks: Task[]): string[] {
    const graph = new Map<string, Set<string>>();
    const visited = new Set<string>();
    const visiting = new Set<string>();
    const order: string[] = [];

    tasks.forEach(task => graph.set(task.id, new Set(task.dependencies)));

    const visit = (taskId: string): void => {
      if (visiting.has(taskId)) throw new Error(`Circular dependency: ${taskId}`);
      if (visited.has(taskId)) return;

      visiting.add(taskId);
      const deps = graph.get(taskId) || new Set();
      deps.forEach(dep => visit(dep));
      visiting.delete(taskId);
      visited.add(taskId);
      order.push(taskId);
    };

    tasks.forEach(task => visit(task.id));
    return order.reverse();
  }

  private identifyParallelGroups(tasks: Task[], executionOrder: string[]): string[][] {
    const groups: string[][] = [];
    const taskMap = new Map(tasks.map(t => [t.id, t]));
    const completed = new Set<string>();

    while (completed.size < tasks.length) {
      const ready = executionOrder.filter(id => 
        !completed.has(id) && 
        (taskMap.get(id)?.dependencies || []).every(dep => completed.has(dep))
      );
      
      if (ready.length > 0) {
        groups.push(ready);
        ready.forEach(id => completed.add(id));
      }
    }

    return groups;
  }

  private findCriticalPath(tasks: Task[]): string[] {
    const taskMap = new Map(tasks.map(t => [t.id, t]));
    const longestPath = new Map<string, number>();
    const path = new Map<string, string[]>();

    tasks.forEach(task => {
      const deps = task.dependencies;
      let maxLength = 0;
      let maxPath: string[] = [];

      deps.forEach(depId => {
        const depLength = longestPath.get(depId) || 0;
        if (depLength > maxLength) {
          maxLength = depLength;
          maxPath = path.get(depId) || [];
        }
      });

      longestPath.set(task.id, maxLength + task.estimatedHours);
      path.set(task.id, [...maxPath, task.id]);
    });

    let criticalPath: string[] = [];
    let maxLength = 0;

    longestPath.forEach((length, taskId) => {
      if (length > maxLength) {
        maxLength = length;
        criticalPath = path.get(taskId) || [];
      }
    });

    return criticalPath;
  }

  private identifyRiskFactors(tasks: Task[]): string[] {
    const risks: string[] = [];
    
    const highComplexity = tasks.filter(t => t.complexity === 'high');
    if (highComplexity.length > 0) {
      risks.push(`${highComplexity.length} high-complexity tasks`);
    }

    const maxDeps = Math.max(...tasks.map(t => t.dependencies.length));
    if (maxDeps > 3) {
      risks.push(`Long dependency chains (max: ${maxDeps})`);
    }

    const totalHours = tasks.reduce((sum, t) => sum + t.estimatedHours, 0);
    if (totalHours > 20) {
      risks.push(`Long total duration (${totalHours} hours)`);
    }

    return risks;
  }
}

export class ExecutionNode {
  private llm: ChatOpenAI;

  constructor(apiKey: string) {
    this.llm = new ChatOpenAI({
      openAIApiKey: apiKey,
      modelName: 'gpt-4',
      temperature: 0.1,
    });
  }

  async invoke(state: AutoCodingState): Promise<Partial<AutoCodingState>> {
    if (state.currentTaskIndex >= state.tasks.length) {
      return { messages: [...state.messages, new AIMessage("All tasks completed")] };
    }

    const task = state.tasks[state.currentTaskIndex];
    task.status = 'in-progress';
    task.updatedAt = new Date();

    try {
      const result = await this.executeTask(task);
      task.status = 'completed';
      task.output = result.output;
      task.updatedAt = new Date();

      return {
        tasks: [...state.tasks],
        results: [...state.results, result],
        currentTaskIndex: state.currentTaskIndex + 1,
        messages: [...state.messages, new AIMessage(`Completed task: ${task.description}`)],
      };
    } catch (error) {
      task.status = 'failed';
      task.updatedAt = new Date();

      return {
        tasks: [...state.tasks],
        errors: [...state.errors, (error as Error).message],
        messages: [...state.messages, new AIMessage(`Failed task: ${task.description} - ${(error as Error).message}`)],
      };
    }
  }

  private async executeTask(task: Task): Promise<TaskResult> {
    const prompt = this.buildExecutionPrompt(task);
    
    const response = await this.llm.invoke([
      new HumanMessage(prompt)
    ]);

    return {
      taskId: task.id,
      success: true,
      output: {
        content: response.content,
        type: task.type,
        filePath: this.getFilePathForTask(task),
      },
    };
  }

  private buildExecutionPrompt(task: Task): string {
    const prompts: Record<Task['type'], string> = {
      'code-generation': `Generate TypeScript code for: ${task.description}\n\nRequirements:\n${task.dependencies.join('\n')}\n\nProvide complete, working code with proper types and error handling.`,
      'file-creation': `Create file content for: ${task.description}\n\nRequirements:\n${task.dependencies.join('\n')}\n\nProvide complete file content.`,
      'dependency-install': `List dependencies needed for: ${task.description}\n\nReturn JSON format: {"dependencies": {"package": "version"}}`,
      'test-creation': `Create test cases for: ${task.description}\n\nRequirements:\n${task.dependencies.join('\n')}\n\nUse Jest with TypeScript.`,
      'config-generation': `Create configuration for: ${task.description}\n\nRequirements:\n${task.dependencies.join('\n')}\n\nProvide complete configuration.`,
    };

    return prompts[task.type];
  }

  private getFilePathForTask(task: Task): string {
    const filePaths: Record<Task['type'], string> = {
      'code-generation': 'src/generated.ts',
      'file-creation': 'README.md',
      'dependency-install': 'package.json',
      'test-creation': 'src/test.test.ts',
      'config-generation': 'config.json',
    };

    return filePaths[task.type];
  }
}

export class ValidationNode {
  private llm: ChatOpenAI;

  constructor(apiKey: string) {
    this.llm = new ChatOpenAI({
      openAIApiKey: apiKey,
      modelName: 'gpt-4',
      temperature: 0.1,
    });
  }

  async invoke(state: AutoCodingState): Promise<Partial<AutoCodingState>> {
    const task = state.tasks[state.currentTaskIndex - 1];
    if (!task || !task.output) {
      return state;
    }

    const prompt = this.buildValidationPrompt(task);
    
    const response = await this.llm.invoke([
      new HumanMessage(prompt)
    ]);

    try {
      const validation = JSON.parse(response.content as string);
      task.validation = validation;

      return {
        tasks: [...state.tasks],
        messages: [...state.messages, new AIMessage(`Validated task: ${task.description} (${validation.score}/100)`)],
      };
    } catch (error) {
      return {
        errors: [...state.errors, `Validation failed: ${(error as Error).message}`],
        messages: [...state.messages, new AIMessage(`Validation failed for task: ${task.description}`)],
      };
    }
  }

  private buildValidationPrompt(task: Task): string {
    return `Validate the following task output:

Task: ${task.description}
Type: ${task.type}
Output: ${JSON.stringify(task.output, null, 2)}

Please provide validation in JSON format:
{
  "score": 0-100,
  "passed": true/false,
  "issues": [
    {
      "severity": "error|warning|info",
      "message": "description",
      "file": "filename",
      "line": 1
    }
  ],
  "suggestions": ["improvement suggestions"]
}

Check for:
- Code quality and best practices
- Completeness of requirements
- Security issues
- Performance considerations
- Maintainability`;
  }
}