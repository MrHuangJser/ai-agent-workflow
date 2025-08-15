export function generateId(prefix: string = 'task'): string {
  const timestamp = Date.now().toString(36);
  const random = Math.random().toString(36).substring(2, 8);
  return `${prefix}_${timestamp}_${random}`;
}

export function generateTaskId(): string {
  return generateId('task');
}

export function generateSessionId(): string {
  return generateId('session');
}