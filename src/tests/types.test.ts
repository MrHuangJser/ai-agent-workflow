import { describe, test, expect } from 'bun:test';
import { TaskSchema, ValidationResultSchema } from '../types';
import { generateTaskId } from '../utils/id-generator';

describe('Types', () => {
  test('TaskSchema validates correct task structure', () => {
    const validTask = {
      id: generateTaskId(),
      description: 'Create a new React component',
      type: 'code-generation',
      complexity: 'medium',
      estimatedHours: 3,
      dependencies: [],
      status: 'pending',
      createdAt: new Date(),
      updatedAt: new Date(),
    };

    const result = TaskSchema.safeParse(validTask);
    expect(result.success).toBe(true);
  });

  test('TaskSchema rejects invalid task type', () => {
    const invalidTask = {
      id: generateTaskId(),
      description: 'Test task',
      type: 'invalid-type',
      complexity: 'low',
      estimatedHours: 1,
      dependencies: [],
      status: 'pending',
      createdAt: new Date(),
      updatedAt: new Date(),
    };

    const result = TaskSchema.safeParse(invalidTask);
    expect(result.success).toBe(false);
  });

  test('ValidationResultSchema validates correctly', () => {
    const validValidation = {
      score: 85,
      passed: true,
      issues: [
        {
          severity: 'warning',
          message: 'Consider adding more comments',
        },
      ],
      suggestions: ['Add JSDoc comments', 'Consider performance optimizations'],
    };

    const result = ValidationResultSchema.safeParse(validValidation);
    expect(result.success).toBe(true);
  });
});