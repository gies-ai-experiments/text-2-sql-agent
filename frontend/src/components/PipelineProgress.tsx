import type { PipelineNode } from '../types.ts';

interface PipelineProgressProps {
  nodes: PipelineNode[];
  isLoading: boolean;
}

const LABELS: Record<string, string> = {
  schema_analyzer: 'Schema',
  planner: 'Plan',
  query_generator: 'Generate',
  executor_eval: 'Execute',
  summarizer: 'Summarize',
};

function StepIcon({ status, isActive }: { status: 'pending' | 'done'; isActive: boolean }) {
  if (status === 'done') {
    return (
      <div className="flex items-center justify-center w-8 h-8 rounded-full bg-green-100 text-green-600 transition-all duration-300">
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
      </div>
    );
  }

  if (isActive) {
    return (
      <div className="flex items-center justify-center w-8 h-8 rounded-full bg-blue-100 transition-all duration-300">
        <div className="w-3 h-3 rounded-full bg-blue-600 animate-pulse" />
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center w-8 h-8 rounded-full bg-slate-100 transition-all duration-300">
      <div className="w-3 h-3 rounded-full bg-slate-300" />
    </div>
  );
}

export function PipelineProgress({ nodes, isLoading }: PipelineProgressProps) {
  // Find the first pending node index to determine which is "active"
  const firstPendingIdx = nodes.findIndex((n) => n.status === 'pending');

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 px-6 py-4">
      <div className="flex items-center justify-between">
        {nodes.map((node, idx) => {
          const isActive = isLoading && idx === firstPendingIdx;
          const label = LABELS[node.name] ?? node.name;

          return (
            <div key={node.name} className="flex items-center">
              {/* Step */}
              <div className="flex flex-col items-center gap-1.5">
                <StepIcon status={node.status} isActive={isActive} />
                <span
                  className={`text-xs font-medium transition-colors duration-300 ${
                    node.status === 'done'
                      ? 'text-green-700'
                      : isActive
                        ? 'text-blue-700'
                        : 'text-slate-400'
                  }`}
                >
                  {label}
                </span>
              </div>

              {/* Connector line between steps */}
              {idx < nodes.length - 1 && (
                <div
                  className={`h-0.5 w-12 sm:w-16 md:w-20 mx-2 rounded transition-colors duration-300 ${
                    node.status === 'done' ? 'bg-green-300' : 'bg-slate-200'
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
