import { useState } from 'react';
import type { Preset } from '../types.ts';

interface QueryInputProps {
  presets: Preset[];
  selectedPreset: string;
  onPresetChange: (preset: string) => void;
  onSubmit: (question: string, preset: string) => void;
  isLoading: boolean;
}

export function QueryInput({
  presets,
  selectedPreset,
  onPresetChange,
  onSubmit,
  isLoading,
}: QueryInputProps) {
  const [question, setQuestion] = useState('');

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = question.trim();
    if (!trimmed || isLoading) return;
    onSubmit(trimmed, selectedPreset);
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
      <div className="flex items-center gap-3 mb-3">
        <label htmlFor="preset-select" className="text-sm font-medium text-slate-600 shrink-0">
          Database
        </label>
        <select
          id="preset-select"
          value={selectedPreset}
          onChange={(e) => onPresetChange(e.target.value)}
          disabled={isLoading}
          className="block w-full max-w-xs rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 shadow-sm transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 focus:outline-none disabled:opacity-50"
        >
          {presets.length === 0 && (
            <option value="enterprise">Enterprise Data Warehouse</option>
          )}
          {presets.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </div>

      <textarea
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        placeholder="Ask a question about your data..."
        rows={3}
        disabled={isLoading}
        className="block w-full rounded-lg border border-slate-300 bg-white px-4 py-3 text-sm text-slate-800 placeholder-slate-400 shadow-sm transition resize-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 focus:outline-none disabled:opacity-50"
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
            handleSubmit(e);
          }
        }}
      />

      <div className="flex items-center justify-between mt-3">
        <span className="text-xs text-slate-400">
          Press Cmd+Enter to submit
        </span>
        <button
          type="submit"
          disabled={isLoading || !question.trim()}
          className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500/40 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isLoading ? (
            <>
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Running...
            </>
          ) : (
            'Run Query'
          )}
        </button>
      </div>
    </form>
  );
}
