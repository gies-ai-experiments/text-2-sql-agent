import { useState, useCallback, useRef } from 'react';
import type { PipelineNode, QueryTask, QueryResult } from '../types.ts';

const PIPELINE_STEPS: string[] = [
  'schema_analyzer',
  'planner',
  'query_generator',
  'executor_eval',
  'summarizer',
];

interface Plan {
  plan_type: string;
  tasks: QueryTask[];
}

interface UseQueryReturn {
  submit: (question: string, preset: string) => void;
  isLoading: boolean;
  nodes: PipelineNode[];
  plan: Plan | null;
  queryResults: QueryResult[];
  answer: string;
  elapsed: number | null;
  error: string | null;
}

function initialNodes(): PipelineNode[] {
  return PIPELINE_STEPS.map((name) => ({ name, status: 'pending' }));
}

/**
 * Parse an SSE stream from the response body.
 *
 * sse_starlette sends events in standard SSE format:
 *   data: {"event":"node","node":"planner","status":"done"}
 *
 * We read the stream as text, split on double-newlines, and extract
 * the `data:` payload from each chunk.
 */
async function readSSEStream(
  response: Response,
  onEvent: (parsed: Record<string, unknown>) => void,
  signal: AbortSignal,
) {
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      if (signal.aborted) break;

      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // SSE events are separated by double newlines
      const parts = buffer.split('\n\n');
      // Keep the last (potentially incomplete) chunk in the buffer
      buffer = parts.pop() ?? '';

      for (const part of parts) {
        const trimmed = part.trim();
        if (!trimmed) continue;

        // Extract the data: line(s) from the SSE event block
        const lines = trimmed.split('\n');
        for (const line of lines) {
          if (line.startsWith('data:')) {
            const jsonStr = line.slice(5).trim();
            if (!jsonStr) continue;
            try {
              const parsed = JSON.parse(jsonStr);
              onEvent(parsed);
            } catch {
              // Skip malformed JSON lines
            }
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export function useQuery(): UseQueryReturn {
  const [isLoading, setIsLoading] = useState(false);
  const [nodes, setNodes] = useState<PipelineNode[]>(initialNodes);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [queryResults, setQueryResults] = useState<QueryResult[]>([]);
  const [answer, setAnswer] = useState('');
  const [elapsed, setElapsed] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);

  const submit = useCallback((question: string, preset: string) => {
    // Cancel any in-flight request
    if (abortRef.current) {
      abortRef.current.abort();
    }

    // Reset state
    setIsLoading(true);
    setNodes(initialNodes());
    setPlan(null);
    setQueryResults([]);
    setAnswer('');
    setElapsed(null);
    setError(null);

    const controller = new AbortController();
    abortRef.current = controller;

    (async () => {
      try {
        const res = await fetch('/api/query', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question, preset }),
          signal: controller.signal,
        });

        if (!res.ok) {
          const body = await res.text();
          setError(`Server error ${res.status}: ${body}`);
          setIsLoading(false);
          return;
        }

        if (!res.body) {
          setError('No response body -- SSE streaming not supported');
          setIsLoading(false);
          return;
        }

        await readSSEStream(
          res,
          (parsed) => {
            const eventType = parsed.event as string;

            switch (eventType) {
              case 'node': {
                const nodeName = parsed.node as string;
                const nodeStatus = parsed.status as string;
                if (nodeStatus === 'done') {
                  setNodes((prev) =>
                    prev.map((n) =>
                      n.name === nodeName ? { ...n, status: 'done' } : n,
                    ),
                  );
                }
                break;
              }

              case 'plan': {
                const planData = parsed.data as Plan;
                setPlan(planData);
                break;
              }

              case 'query_result': {
                const result = parsed.data as QueryResult;
                setQueryResults((prev) => [...prev, result]);
                break;
              }

              case 'answer': {
                const answerData = parsed.data as { final_answer: string };
                setAnswer(answerData.final_answer);
                break;
              }

              case 'done': {
                const doneData = parsed.data as { elapsed: number };
                setElapsed(doneData.elapsed);
                break;
              }

              case 'error': {
                const errData = parsed.data as { message: string };
                setError(errData.message);
                break;
              }
            }
          },
          controller.signal,
        );
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === 'AbortError') {
          // Request was intentionally cancelled
          return;
        }
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setIsLoading(false);
      }
    })();
  }, []);

  return { submit, isLoading, nodes, plan, queryResults, answer, elapsed, error };
}
