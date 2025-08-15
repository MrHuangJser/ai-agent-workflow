import { ChatOpenAI } from '@langchain/openai';
import { AgentState, Task } from '../types';
import { logger } from '../utils/logger';

interface TaskGroup {
  id: string;
  tasks: Task[];
  canExecuteInParallel: boolean;
  estimatedStartTime: number;
  estimatedEndTime: number;
  dependencies: string[];
}

interface ExecutionPlan {
  taskGroups: TaskGroup[];
  criticalPath: string[];
  totalEstimatedHours: number;
  parallelGroups: TaskGroup[][];
  riskFactors: string[];
}

export class PlanningAgent {
  private llm: ChatOpenAI;

  constructor(apiKey: string) {
    this.llm = new ChatOpenAI({
      openAIApiKey: apiKey,
      modelName: 'gpt-4',
      temperature: 0.1,
    });
  }

  async createExecutionPlan(state: AgentState): Promise<Partial<AgentState>> {
    logger.info('Starting task planning', { taskCount: state.tasks.length });

    try {
      const plan = await this.generateExecutionPlan(state.tasks);
      
      logger.info('Task planning completed', { 
        totalHours: plan.totalEstimatedHours,
        parallelGroups: plan.parallelGroups.length,
        criticalPathLength: plan.criticalPath.length 
      });

      return {
        executionPlan: plan,
        metadata: {
          ...state.metadata,
          planningCompleted: true,
          criticalPath: plan.criticalPath,
          parallelGroups: plan.parallelGroups.length,
          riskFactors: plan.riskFactors,
        },
      };
    } catch (error) {
      logger.error('Task planning failed', { error: error.message });
      return {
        errors: [...(state.errors || []), `Planning failed: ${error.message}`],
      };
    }
  }

  private async generateExecutionPlan(tasks: Task[]): Promise<ExecutionPlan> {
    const dependencyGraph = this.buildDependencyGraph(tasks);
    const executionOrder = this.getExecutionOrder(dependencyGraph);
    const parallelGroups = this.identifyParallelGroups(tasks, dependencyGraph);
    const criticalPath = this.findCriticalPath(tasks, dependencyGraph);
    const riskFactors = this.identifyRiskFactors(tasks);

    const taskGroups = this.createTaskGroups(executionOrder, tasks);

    return {
      taskGroups,
      criticalPath,
      totalEstimatedHours: tasks.reduce((sum, task) => sum + task.estimatedHours, 0),
      parallelGroups,
      riskFactors,
    };
  }

  private buildDependencyGraph(tasks: Task[]): Map<string, Set<string>> {
    const graph = new Map<string, Set<string>>();
    
    // 初始化图
    tasks.forEach(task => {
      graph.set(task.id, new Set());
    });

    // 构建依赖关系
    tasks.forEach(task => {
      task.dependencies.forEach(depId => {
        if (graph.has(depId)) {
          graph.get(task.id)!.add(depId);
        }
      });
    });

    return graph;
  }

  private getExecutionOrder(dependencyGraph: Map<string, Set<string>>): string[] {
    const visited = new Set<string>();
    const visiting = new Set<string>();
    const order: string[] = [];

    const visit = (nodeId: string): void => {
      if (visiting.has(nodeId)) {
        throw new Error(`Circular dependency detected: ${nodeId}`);
      }
      if (visited.has(nodeId)) {
        return;
      }

      visiting.add(nodeId);
      const dependencies = dependencyGraph.get(nodeId) || new Set();
      dependencies.forEach(dep => visit(dep));
      visiting.delete(nodeId);
      visited.add(nodeId);
      order.push(nodeId);
    };

    Array.from(dependencyGraph.keys()).forEach(nodeId => visit(nodeId));
    
    return order.reverse(); // Reverse to get execution order
  }

  private identifyParallelGroups(tasks: Task[], dependencyGraph: Map<string, Set<string>>): TaskGroup[][] {
    const groups: TaskGroup[][] = [];
    const remainingTasks = new Set(tasks.map(t => t.id));
    const completedTasks = new Set<string>();

    let currentLevel = 0;
    while (remainingTasks.size > 0) {
      const readyTasks = Array.from(remainingTasks).filter(taskId => {
        const deps = dependencyGraph.get(taskId) || new Set();
        return Array.from(deps).every(dep => completedTasks.has(dep));
      });

      if (readyTasks.length === 0) {
        throw new Error('Circular dependency detected in tasks');
      }

      const group: TaskGroup = {
        id: `group_${currentLevel}`,
        tasks: readyTasks.map(id => tasks.find(t => t.id === id)!),
        canExecuteInParallel: readyTasks.length > 1,
        estimatedStartTime: this.calculateGroupStartTime(readyTasks, tasks),
        estimatedEndTime: this.calculateGroupEndTime(readyTasks, tasks),
        dependencies: this.getGroupDependencies(readyTasks, dependencyGraph),
      };

      groups.push([group]);
      readyTasks.forEach(taskId => {
        remainingTasks.delete(taskId);
        completedTasks.add(taskId);
      });
      currentLevel++;
    }

    return groups;
  }

  private findCriticalPath(tasks: Task[], dependencyGraph: Map<string, Set<string>>): string[] {
    const taskMap = new Map(tasks.map(t => [t.id, t]));
    const longestPath = new Map<string, number>();
    const path = new Map<string, string[]>();

    const executionOrder = this.getExecutionOrder(dependencyGraph);
    
    executionOrder.forEach(taskId => {
      const task = taskMap.get(taskId);
      if (!task) return;

      const deps = dependencyGraph.get(taskId) || new Set();
      let maxPathLength = 0;
      let maxDepPath: string[] = [];

      deps.forEach(depId => {
        const depPathLength = longestPath.get(depId) || 0;
        if (depPathLength > maxPathLength) {
          maxPathLength = depPathLength;
          maxDepPath = path.get(depId) || [];
        }
      });

      longestPath.set(taskId, maxPathLength + task.estimatedHours);
      path.set(taskId, [...maxDepPath, taskId]);
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
    const riskFactors: string[] = [];

    // 高复杂度任务风险
    const highComplexityTasks = tasks.filter(t => t.complexity === 'high');
    if (highComplexityTasks.length > 0) {
      riskFactors.push(`包含 ${highComplexityTasks.length} 个高复杂度任务`);
    }

    // 依赖链过长风险
    const maxDependencies = Math.max(...tasks.map(t => t.dependencies.length));
    if (maxDependencies > 3) {
      riskFactors.push(`存在依赖链过长的任务（最多 ${maxDependencies} 个依赖）`);
    }

    // 估算时间过长风险
    const totalHours = tasks.reduce((sum, t) => sum + t.estimatedHours, 0);
    if (totalHours > 20) {
      riskFactors.push(`总估算时间过长（${totalHours} 小时）`);
    }

    return riskFactors;
  }

  private createTaskGroups(
    executionOrder: string[],
    tasks: Task[]
  ): TaskGroup[] {
    const taskMap = new Map(tasks.map(t => [t.id, t]));
    
    return executionOrder.map((taskId, index) => {
      const task = taskMap.get(taskId)!;
      const dependencies = task.dependencies;
      
      const startTime = this.calculateTaskStartTime(task, tasks);
      
      return {
        id: `group_${index}`,
        tasks: [task],
        canExecuteInParallel: false,
        estimatedStartTime: startTime,
        estimatedEndTime: startTime + task.estimatedHours,
        dependencies,
      };
    });
  }

  private calculateTaskStartTime(task: Task, allTasks: Task[]): number {
    if (task.dependencies.length === 0) {
      return 0;
    }

    const taskMap = new Map(allTasks.map(t => [t.id, t]));
    const depEndTimes = task.dependencies.map(depId => {
      const depTask = taskMap.get(depId);
      return depTask ? this.calculateTaskStartTime(depTask, allTasks) + depTask.estimatedHours : 0;
    });

    return Math.max(...depEndTimes);
  }

  private calculateGroupStartTime(taskIds: string[], tasks: Task[]): number {
    const taskMap = new Map(tasks.map(t => [t.id, t]));
    return Math.max(...taskIds.map(id => {
      const task = taskMap.get(id);
      return task ? this.calculateTaskStartTime(task, tasks) : 0;
    }));
  }

  private calculateGroupEndTime(taskIds: string[], tasks: Task[]): number {
    const taskMap = new Map(tasks.map(t => [t.id, t]));
    return Math.max(...taskIds.map(id => {
      const task = taskMap.get(id);
      return task ? this.calculateTaskStartTime(task, tasks) + task.estimatedHours : 0;
    }));
  }

  private getGroupDependencies(taskIds: string[], dependencyGraph: Map<string, Set<string>>): string[] {
    const allDeps = new Set<string>();
    taskIds.forEach(taskId => {
      const deps = dependencyGraph.get(taskId) || new Set();
      deps.forEach(dep => {
        if (!taskIds.includes(dep)) {
          allDeps.add(dep);
        }
      });
    });
    return Array.from(allDeps);
  }
}