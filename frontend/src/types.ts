export interface Preset {
  id: string;
  name: string;
  description: string;
}

export interface TableSchema {
  name: string;
  columns: { name: string; type: string }[];
}

export interface SchemaResponse {
  tables: TableSchema[];
}

export interface QueryTask {
  id: string;
  description: string;
}

export interface QueryResult {
  task_id: string;
  sql: string;
  score: number;
  data: Record<string, unknown>[];
  relevance: { score: number; reasoning: string } | null;
  status: string;
  error?: string;
}

export interface PipelineNode {
  name: string;
  status: 'pending' | 'done';
}

export type SSEEvent =
  | { event: 'node'; node: string; status: string }
  | { event: 'plan'; data: { plan_type: string; tasks: QueryTask[] } }
  | { event: 'query_result'; data: QueryResult }
  | { event: 'answer'; data: { final_answer: string } }
  | { event: 'done'; data: { elapsed: number } };
