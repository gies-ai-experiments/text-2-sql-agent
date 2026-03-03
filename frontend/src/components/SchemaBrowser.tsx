import { useState } from 'react';
import type { TableSchema } from '../types.ts';

interface SchemaBrowserProps {
  tables: TableSchema[];
  loading: boolean;
  collapsed: boolean;
  onToggle: () => void;
}

function TableItem({ table }: { table: TableSchema }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <li>
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-3 py-1.5 text-left hover:bg-slate-100 rounded-md transition-colors group"
      >
        <div className="flex items-center gap-2 min-w-0">
          <svg
            className="w-3.5 h-3.5 text-slate-400 shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
            />
          </svg>
          <span className="text-xs font-medium text-slate-700 truncate">
            {table.name}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-slate-400">
            {table.columns.length}
          </span>
          <svg
            className={`w-3 h-3 text-slate-400 transition-transform duration-150 ${
              expanded ? 'rotate-180' : ''
            }`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {expanded && (
        <ul className="ml-5 mt-0.5 mb-1 space-y-0.5">
          {table.columns.map((col) => (
            <li
              key={col.name}
              className="flex items-center justify-between px-2 py-0.5"
            >
              <span className="text-[11px] text-slate-600 font-mono truncate">
                {col.name}
              </span>
              <span className="text-[10px] text-slate-400 font-mono uppercase shrink-0 ml-2">
                {col.type}
              </span>
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

export function SchemaBrowser({ tables, loading, collapsed, onToggle }: SchemaBrowserProps) {
  return (
    <aside
      className={`bg-white border-r border-slate-200 flex flex-col transition-all duration-200 ${
        collapsed ? 'w-12' : 'w-72'
      }`}
    >
      {/* Sidebar header */}
      <div className="flex items-center justify-between px-3 py-3 border-b border-slate-100">
        {!collapsed && (
          <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Schema
          </h2>
        )}
        <button
          type="button"
          onClick={onToggle}
          className="p-1 rounded hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors"
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            {collapsed ? (
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 5l7 7-7 7M5 5l7 7-7 7" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
            )}
          </svg>
        </button>
      </div>

      {/* Collapsed state */}
      {collapsed && (
        <div className="flex-1 flex items-start justify-center pt-4">
          <svg
            className="w-5 h-5 text-slate-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4"
            />
          </svg>
        </div>
      )}

      {/* Expanded content */}
      {!collapsed && (
        <div className="flex-1 overflow-y-auto px-2 py-2">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <svg className="animate-spin h-5 w-5 text-slate-400" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            </div>
          ) : tables.length === 0 ? (
            <p className="text-xs text-slate-400 text-center py-4">
              No tables found
            </p>
          ) : (
            <ul className="space-y-0.5">
              {tables.map((table) => (
                <TableItem key={table.name} table={table} />
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Table count footer */}
      {!collapsed && tables.length > 0 && (
        <div className="px-3 py-2 border-t border-slate-100">
          <span className="text-[10px] text-slate-400">
            {tables.length} table{tables.length !== 1 ? 's' : ''}
          </span>
        </div>
      )}
    </aside>
  );
}
