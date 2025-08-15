import { StateGraph, END } from '@langchain/langgraph';
import { AgentState, AgentConfig } from '../types';
import { logger } from '../utils/logger';
import { AnalysisAgent } from './analysis-agent';
import { PlanningAgent } from './planning-agent';
import { ExecutionAgent } from './execution-agent';
import { ValidationAgent } from './validation-agent';

interface GatewayAgentConfig {
  apiKey: string;
  workspacePath?: string;
}

export class GatewayAgent {
  private analysisAgent: AnalysisAgent;
  private planningAgent: PlanningAgent;
  private executionAgent: ExecutionAgent;
  private validationAgent: ValidationAgent;
  private graph: StateGraph;

  constructor(config: GatewayAgentConfig) {
    this.analysisAgent = new AnalysisAgent(config.apiKey);
    this.planningAgent = new PlanningAgent(config.apiKey);
    this.executionAgent = new ExecutionAgent(config.apiKey, config.workspacePath);
    this.validationAgent = new ValidationAgent(config.apiKey);
    
    this.graph = this.buildGraph();
  }

  async processRequest(userInput: string): Promise<AgentState> {
    logger.info('Starting processing request', { userInput });

    const initialState: AgentState = {
      userInput,
      tasks: [],
      results: [],
      errors: [],
      metadata: {
        sessionId: `session_${Date.now()}`,
        startTime: new Date(),
      },
    };

    try {
      const finalState = await this.graph.invoke(initialState);
      logger.info('Request processing completed', { 
        sessionId: finalState.metadata?.sessionId,
        taskCount: finalState.tasks.length,
        errorCount: finalState.errors.length
      });
      return finalState;
    } catch (error) {
      logger.error('Request processing failed', { error: error.message });
      return {
        ...initialState,
        errors: [error.message],
      };
    }
  }

  private buildGraph(): StateGraph {
    const graph = new StateGraph({
      channels: {
        userInput: {
          value: (x: string, y?: string) => y ?? x,
          default: () => '',
        },
        tasks: {
          value: (x: any[], y?: any[]) => y ?? x,
          default: () => [],
        },
        currentTask: {
          value: (x: any, y?: any) => y ?? x,
          default: () => undefined,
        },
        executionPlan: {
          value: (x: any, y?: any) => y ?? x,
          default: () => undefined,
        },
        results: {
          value: (x: any[], y?: any[]) => [...(x || []), ...(y || [])],
          default: () => [],
        },
        errors: {
          value: (x: string[], y?: string[]) => [...(x || []), ...(y || [])],
          default: () => [],
        },
        metadata: {
          value: (x: any, y?: any) => ({ ...x, ...y }),
          default: () => ({}),
        },
      },
    });

    // Define nodes
    graph.addNode('analyze', this.handleAnalysis.bind(this));
    graph.addNode('plan', this.handlePlanning.bind(this));
    graph.addNode('execute', this.handleExecution.bind(this));
    graph.addNode('validate', this.handleValidation.bind(this));
    graph.addNode('gateway', this.handleGateway.bind(this));

    // Define edges
    graph.addEdge('analyze', 'plan');
    graph.addEdge('plan', 'gateway');
    graph.addEdge('gateway', 'execute');
    graph.addEdge('execute', 'validate');
    graph.addEdge('validate', 'gateway');
    graph.addConditionalEdges('gateway', this.shouldContinue.bind(this));

    graph.setEntryPoint('analyze');

    return graph;
  }

  private async handleAnalysis(state: AgentState): Promise<Partial<AgentState>> {
    return await this.analysisAgent.analyzeRequirements(state);
  }

  private async handlePlanning(state: AgentState): Promise<Partial<AgentState>> {
    return await this.planningAgent.createExecutionPlan(state);
  }

  private async handleExecution(state: AgentState): Promise<Partial<AgentState>> {
    return await this.executionAgent.executeTask(state);
  }

  private async handleValidation(state: AgentState): Promise<Partial<AgentState>> {
    return await this.validationAgent.validateTask(state);
  }

  private async handleGateway(state: AgentState): Promise<Partial<AgentState>> {
    logger.debug('Gateway processing', { 
      taskCount: state.tasks.length,
      currentTaskId: state.currentTask?.id,
      completedTasks: state.tasks.filter(t => t.status === 'completed').length
    });

    const pendingTasks = state.tasks.filter(t => t.status === 'pending');
    const inProgressTasks = state.tasks.filter(t => t.status === 'in-progress');

    if (inProgressTasks.length > 0) {
      // Continue with current in-progress task
      const currentTask = inProgressTasks[0];
      return {
        currentTask,
      };
    }

    if (pendingTasks.length === 0) {
      // All tasks completed
      return {
        metadata: {
          ...state.metadata,
          allTasksCompleted: true,
          endTime: new Date(),
        },
      };
    }

    // Find next task to execute based on dependencies
    const readyTasks = this.findReadyTasks(pendingTasks, state.tasks);
    if (readyTasks.length === 0) {
      return {
        errors: [...state.errors, 'No tasks ready for execution (possible dependency cycle)'],
      };
    }

    // Select highest priority task (for now, just take the first one)
    const nextTask = readyTasks[0];
    nextTask.status = 'in-progress';
    nextTask.updatedAt = new Date();

    return {
      currentTask: nextTask,
    };
  }

  private findReadyTasks(pendingTasks: any[], allTasks: any[]): any[] {
    return pendingTasks.filter(task => {
      const dependencies = task.dependencies || [];
      return dependencies.every(depId => {
        const depTask = allTasks.find(t => t.id === depId);
        return depTask && depTask.status === 'completed';
      });
    });
  }

  private shouldContinue(state: AgentState): string {
    const hasErrors = state.errors && state.errors.length > 0;
    const allTasksCompleted = state.tasks.every(t => 
      t.status === 'completed' || t.status === 'failed'
    );
    const metadata = state.metadata || {};

    if (hasErrors) {
      logger.error('Stopping execution due to errors', { errors: state.errors });
      return END;
    }

    if (allTasksCompleted || metadata.allTasksCompleted) {
      logger.info('All tasks completed successfully');
      return END;
    }

    return 'execute';
  }

  // Public methods for monitoring and control
  getCurrentState(): Promise<AgentState> {
    return Promise.resolve({
      userInput: '',
      tasks: [],
      results: [],
      errors: [],
      metadata: {},
    });
  }

  reset(): void {
    logger.info('Resetting Gateway Agent');
  }

  async stop(): Promise<void> {
    logger.info('Stopping Gateway Agent');
  }
}