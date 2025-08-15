import { BaseMessage } from "@langchain/core/messages";

export interface AutoCodingState {
  messages: BaseMessage[];
  userInput: string;
  tasks: Task[];
  executionPlan: any;
  currentTaskIndex: number;
  results: TaskResult[];
  errors: string[];
  metadata: {
    sessionId: string;
    startTime: Date;
    endTime?: Date;
    totalTasks: number;
    completedTasks: number;
  };
}

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

export const initialState: AutoCodingState = {
  messages: [],
  userInput: "",
  tasks: [],
  executionPlan: null,
  currentTaskIndex: 0,
  results: [],
  errors: [],
  metadata: {
    sessionId: "",
    startTime: new Date(),
    totalTasks: 0,
    completedTasks: 0,
  },
};