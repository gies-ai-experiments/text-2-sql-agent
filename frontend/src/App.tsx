import { useState } from 'react';
import { useSchema } from './hooks/useSchema.ts';
import { useQuery } from './hooks/useQuery.ts';
import { QueryInput } from './components/QueryInput.tsx';
import { PipelineProgress } from './components/PipelineProgress.tsx';
import { PlanView } from './components/PlanView.tsx';
import { SqlResultCard } from './components/SqlResultCard.tsx';
import { AnswerPanel } from './components/AnswerPanel.tsx';
import { SchemaBrowser } from './components/SchemaBrowser.tsx';

function App() {
  const { presets, schema, selectedPreset, setSelectedPreset, loading: schemaLoading } =
    useSchema();
  const { submit, isLoading, nodes, plan, queryResults, answer, elapsed, error } =
    useQuery();

  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // Track whether any query has been submitted to show the results area
  const hasResults =
    isLoading || plan !== null || queryResults.length > 0 || answer !== '' || error !== null;

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* Left sidebar -- Schema Browser */}
      <SchemaBrowser
        tables={schema}
        loading={schemaLoading}
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed((c) => !c)}
      />

      {/* Main content area */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Header */}
        <header className="shrink-0 bg-white border-b border-slate-200 px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-blue-600 text-white">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4"
                />
              </svg>
            </div>
            <div>
              <h1 className="text-lg font-bold text-slate-900">Text2SQL Playground</h1>
              <p className="text-xs text-slate-400">Natural language to SQL, powered by AI</p>
            </div>
          </div>
        </header>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-4xl mx-auto px-6 py-6 space-y-4">
            {/* Query Input */}
            <QueryInput
              presets={presets}
              selectedPreset={selectedPreset}
              onPresetChange={setSelectedPreset}
              onSubmit={submit}
              isLoading={isLoading}
            />

            {/* Results area */}
            {hasResults && (
              <div className="space-y-4">
                {/* Pipeline Progress */}
                <PipelineProgress nodes={nodes} isLoading={isLoading} />

                {/* Plan View */}
                {plan && (
                  <PlanView planType={plan.plan_type} tasks={plan.tasks} />
                )}

                {/* Query Result Cards */}
                {queryResults.map((result, idx) => (
                  <SqlResultCard key={`${result.task_id}-${idx}`} result={result} />
                ))}

                {/* Error */}
                {error && (
                  <div className="bg-red-50 border border-red-200 rounded-xl px-5 py-4">
                    <div className="flex items-start gap-3">
                      <svg
                        className="w-5 h-5 text-red-500 shrink-0 mt-0.5"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={2}
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                        />
                      </svg>
                      <div>
                        <h3 className="text-sm font-semibold text-red-800">Error</h3>
                        <p className="text-sm text-red-700 mt-0.5">{error}</p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Final Answer */}
                <AnswerPanel answer={answer} elapsed={elapsed} />
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
