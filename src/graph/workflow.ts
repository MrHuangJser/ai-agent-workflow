import { StateGraph, END } from "@langchain/langgraph";
import { AutoCodingState } from "./state";
import { AnalysisNode, PlanningNode, ExecutionNode, ValidationNode } from "./nodes";
import { BaseMessage, AIMessage } from "@langchain/core/messages";

const START = "__start__";

export class AutoCodingWorkflow {
  private graph: StateGraph;
  private nodes: {
    analysis: AnalysisNode;
    planning: PlanningNode;
    execution: ExecutionNode;
    validation: ValidationNode;
  };

  constructor(apiKey: string) {
    this.nodes = {
      analysis: new AnalysisNode(apiKey),
      planning: new PlanningNode(),
      execution: new ExecutionNode(apiKey),
      validation: new ValidationNode(apiKey),
    };

    this.graph = this.createGraph();
  }

  private createGraph(): any {
    const workflow = new StateGraph({
      channels: {
        messages: {
          value: (x: BaseMessage[], y?: BaseMessage[]) => [...x, ...(y || [])],
          default: () => [],
        },
        userInput: {
          value: (x: string, y?: string) => y ?? x,
          default: () => "",
        },
        tasks: {
          value: (x: any[], y?: any[]) => y ?? x,
          default: () => [],
        },
        executionPlan: {
          value: (x: any, y?: any) => y ?? x,
          default: () => null,
        },
        currentTaskIndex: {
          value: (x: number, y?: number) => y ?? x,
          default: () => 0,
        },
        results: {
          value: (x: any[], y?: any[]) => [...x, ...(y || [])],
          default: () => [],
        },
        errors: {
          value: (x: string[], y?: string[]) => [...x, ...(y || [])],
          default: () => [],
        },
        metadata: {
          value: (x: any, y?: any) => ({ ...x, ...y }),
          default: () => ({}),
        },
      },
    });

    workflow
      .addNode("analysis", this.nodes.analysis.invoke.bind(this.nodes.analysis))
      .addNode("planning", this.nodes.planning.invoke.bind(this.nodes.planning))
      .addNode("execution", this.nodes.execution.invoke.bind(this.nodes.execution))
      .addNode("validation", this.nodes.validation.invoke.bind(this.nodes.validation))
      .addNode("gateway", this.gatewayNode.bind(this));

    workflow
      .addEdge(START, "analysis")
      .addEdge("analysis", "planning")
      .addEdge("planning", "gateway")
      .addEdge("execution", "validation")
      .addEdge("validation", "gateway")
      .addConditionalEdges("gateway", this.shouldContinue.bind(this));

    return workflow;
  }

  private async gatewayNode(state: AutoCodingState): Promise<Partial<AutoCodingState>> {
    const pendingTasks = state.tasks.filter(t => t.status === 'pending');
    const readyTasks = pendingTasks.filter(task => {
      return task.dependencies.every(depId => {
        const depTask = state.tasks.find(t => t.id === depId);
        return depTask && depTask.status === 'completed';
      });
    });

    if (readyTasks.length === 0 && pendingTasks.length > 0) {
      return {
        errors: [...state.errors, "No tasks ready for execution (possible circular dependency)"],
        messages: [...state.messages, new AIMessage("No ready tasks found")]
      };
    }

    if (readyTasks.length > 0) {
      return {
        messages: [...state.messages, new AIMessage(`Executing task: ${readyTasks[0].description}`)]
      };
    }

    return {
      messages: [...state.messages, new AIMessage("All tasks completed")],
      metadata: {
        ...state.metadata,
        endTime: new Date(),
        completedTasks: state.tasks.filter(t => t.status === 'completed').length
      }
    };
  }

  private shouldContinue(state: AutoCodingState): "execution" | typeof END {
    const hasErrors = state.errors.length > 0;
    const allTasksCompleted = state.tasks.every(t => t.status === 'completed' || t.status === 'failed');
    const pendingTasks = state.tasks.filter(t => t.status === 'pending');
    const readyTasks = pendingTasks.filter(task => 
      task.dependencies.every(depId => {
        const depTask = state.tasks.find(t => t.id === depId);
        return depTask && depTask.status === 'completed';
      })
    );

    if (hasErrors) {
      return END;
    }

    if (allTasksCompleted || (pendingTasks.length > 0 && readyTasks.length === 0)) {
      return END;
    }

    return "execution";
  }

  async invoke(userInput: string): Promise<AutoCodingState> {
    const workflow = this.createGraph().compile();
    
    const initialState: AutoCodingState = {
      messages: [],
      userInput,
      tasks: [],
      executionPlan: null,
      currentTaskIndex: 0,
      results: [],
      errors: [],
      metadata: {
        sessionId: `session_${Date.now()}`,
        startTime: new Date(),
        totalTasks: 0,
        completedTasks: 0,
      }
    };

    return await workflow.invoke(initialState);
  }
}