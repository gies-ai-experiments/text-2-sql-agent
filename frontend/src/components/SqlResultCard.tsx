import type { QueryResult } from '../types.ts';

interface SqlResultCardProps {
  result: QueryResult;
}

function ScoreBadge({ score }: { score: number }) {
  let colors: string;
  if (score >= 0.9) {
    colors = 'bg-green-100 text-green-700';
  } else if (score >= 0.7) {
    colors = 'bg-yellow-100 text-yellow-700';
  } else {
    colors = 'bg-red-100 text-red-700';
  }

  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${colors}`}>
      {(score * 100).toFixed(0)}%
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const isSuccess = status === 'success' || status === 'ok';
  const colors = isSuccess
    ? 'bg-green-50 text-green-700 border-green-200'
    : 'bg-red-50 text-red-700 border-red-200';

  return (
    <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${colors}`}>
      {status}
    </span>
  );
}

export function SqlResultCard({ result }: SqlResultCardProps) {
  const columns = result.data.length > 0 ? Object.keys(result.data[0]) : [];

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100">
        <div className="flex items-center gap-3">
          <span className="text-xs font-mono text-slate-400">
            {result.task_id}
          </span>
          <StatusBadge status={result.status} />
        </div>
        <ScoreBadge score={result.score} />
      </div>

      {/* SQL Block */}
      <div className="px-5 py-3">
        <pre className="bg-slate-900 text-slate-100 rounded-lg px-4 py-3 text-sm font-mono overflow-x-auto whitespace-pre-wrap leading-relaxed">
          {result.sql || '-- No SQL generated'}
        </pre>
      </div>

      {/* Error Message */}
      {result.error && (
        <div className="mx-5 mb-3 rounded-lg bg-red-50 border border-red-200 px-4 py-2">
          <p className="text-sm text-red-700">{result.error}</p>
        </div>
      )}

      {/* Data Table */}
      {result.data.length > 0 && (
        <div className="px-5 pb-3">
          <div className="border border-slate-200 rounded-lg overflow-hidden">
            <div className="overflow-x-auto max-h-64">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="bg-slate-50">
                    {columns.map((col) => (
                      <th
                        key={col}
                        className="px-3 py-2 text-left text-xs font-semibold text-slate-600 uppercase tracking-wider border-b border-slate-200"
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.data.map((row, rowIdx) => (
                    <tr
                      key={rowIdx}
                      className={rowIdx % 2 === 0 ? 'bg-white' : 'bg-slate-50/50'}
                    >
                      {columns.map((col) => (
                        <td
                          key={col}
                          className="px-3 py-1.5 text-slate-700 whitespace-nowrap border-b border-slate-100"
                        >
                          {String(row[col] ?? '')}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {result.data.length > 10 && (
              <div className="px-3 py-1.5 bg-slate-50 text-xs text-slate-400 text-center border-t border-slate-200">
                Showing {result.data.length} rows
              </div>
            )}
          </div>
        </div>
      )}

      {/* Relevance */}
      {result.relevance && (
        <div className="px-5 pb-4">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-medium text-slate-500">Relevance</span>
            <ScoreBadge score={result.relevance.score} />
          </div>
          {result.relevance.reasoning && (
            <p className="text-xs text-slate-500 leading-relaxed">
              {result.relevance.reasoning}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
