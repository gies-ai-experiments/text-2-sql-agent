import { useState, useEffect, useCallback } from 'react';
import type { Preset, TableSchema } from '../types.ts';

interface UseSchemaReturn {
  presets: Preset[];
  schema: TableSchema[];
  selectedPreset: string;
  setSelectedPreset: (preset: string) => void;
  loading: boolean;
}

export function useSchema(): UseSchemaReturn {
  const [presets, setPresets] = useState<Preset[]>([]);
  const [schema, setSchema] = useState<TableSchema[]>([]);
  const [selectedPreset, setSelectedPreset] = useState<string>('enterprise');
  const [loading, setLoading] = useState(false);

  // Fetch available presets on mount
  useEffect(() => {
    let cancelled = false;

    async function fetchPresets() {
      try {
        const res = await fetch('/api/presets');
        if (!res.ok) return;
        const data: Preset[] = await res.json();
        if (!cancelled) {
          setPresets(data);
          // Auto-select first preset if current selection is not in list
          if (data.length > 0 && !data.some((p) => p.id === selectedPreset)) {
            setSelectedPreset(data[0].id);
          }
        }
      } catch {
        // Silently fail -- presets will remain empty
      }
    }

    void fetchPresets();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Fetch schema whenever selectedPreset changes
  const fetchSchema = useCallback(async (preset: string) => {
    if (!preset) return;
    setLoading(true);
    try {
      const res = await fetch(`/api/schema/${preset}`);
      if (!res.ok) {
        setSchema([]);
        return;
      }
      const data = await res.json();
      setSchema(data.tables ?? []);
    } catch {
      setSchema([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchSchema(selectedPreset);
  }, [selectedPreset, fetchSchema]);

  return { presets, schema, selectedPreset, setSelectedPreset, loading };
}
