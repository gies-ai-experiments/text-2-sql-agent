interface AnswerPanelProps {
  answer: string;
  elapsed: number | null;
}

export function AnswerPanel({ answer, elapsed }: AnswerPanelProps) {
  if (!answer) return null;

  return (
    <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl border border-blue-200 shadow-sm overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3 border-b border-blue-100">
        <h3 className="text-sm font-semibold text-blue-800">Answer</h3>
        {elapsed !== null && (
          <span className="text-xs text-blue-500 font-medium">
            {elapsed.toFixed(1)}s
          </span>
        )}
      </div>
      <div className="px-5 py-4">
        <p className="text-sm text-slate-800 leading-relaxed whitespace-pre-wrap">
          {answer}
        </p>
      </div>
    </div>
  );
}
