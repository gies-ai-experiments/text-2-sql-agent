import { useState } from 'react';
import type { QueryTask } from '../types.ts';

interface PlanViewProps {
  planType: string;
  tasks: QueryTask[];
}

function PlanTypeBadge({ planType }: { planType: string }) {
  const label = planType.replace(/-/g, ' ').replace(/_/g, ' ');
  const colors =
    planType === 'single'
      ? 'bg-blue-100 text-blue-700'
      : 'bg-purple-100 text-purple-700';

  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${colors}`}
    >
      {label}
    </span>
  );
}

export function PlanView({ planType, tasks }: PlanViewProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-5 py-3 text-left hover:bg-slate-50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <h3 className="text-sm font-semibold text-slate-700">Query Plan</h3>
          <PlanTypeBadge planType={planType} />
          <span className="text-xs text-slate-400">
            {tasks.length} task{tasks.length !== 1 ? 's' : ''}
          </span>
        </div>
        <svg
          className={`w-4 h-4 text-slate-400 transition-transform duration-200 ${
            expanded ? 'rotate-180' : ''
          }`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {expanded && (
        <div className="border-t border-slate-100 px-5 py-3">
          {tasks.length === 0 ? (
            <p className="text-sm text-slate-400 italic">No tasks in plan</p>
          ) : (
            <ul className="space-y-2">
              {tasks.map((task, idx) => (
                <li key={task.id} className="flex items-start gap-3">
                  <span className="shrink-0 flex items-center justify-center w-6 h-6 rounded-full bg-slate-100 text-xs font-medium text-slate-600">
                    {idx + 1}
                  </span>
                  <div>
                    <span className="text-xs font-mono text-slate-400">{task.id}</span>
                    <p className="text-sm text-slate-700">{task.description}</p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
