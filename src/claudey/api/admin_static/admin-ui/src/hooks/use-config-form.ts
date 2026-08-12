import { useCallback, useEffect, useState } from "react";

import { fetchConfig, fetchModels, validateConfig, applyConfig, restartServer } from "@/api/client";
import type { ConfigPayload, ConfigField } from "@/api/types";
import { inputValue, wireValue, isFieldChanged, sourceLabel } from "@/lib/config";

interface UseConfigFormReturn {
  payload: ConfigPayload | null;
  isLoading: boolean;
  error: string | null;
  editedValues: Record<string, string>;
  dirtyCount: number;
  setEdited: (key: string, value: string) => void;
  validate: () => Promise<boolean>;
  apply: () => Promise<boolean>;
  restart: () => Promise<void>;
  refresh: () => Promise<void>;
  getInputValue: (field: ConfigField) => string;
  getSourceLabel: (source: string) => string;
}

export function useConfigForm(): UseConfigFormReturn {
  const [payload, setPayload] = useState<ConfigPayload | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editedValues, setEditedValues] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchConfig();
      setPayload(data);
      setEditedValues({});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load config");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const setEdited = useCallback((key: string, value: string) => {
    setEditedValues((prev) => ({ ...prev, [key]: value }));
  }, []);

  const dirtyCount = Object.entries(editedValues).filter(([key, value]) => {
    const field = payload?.fields.find((f) => f.key === key);
    return field && isFieldChanged(field, value);
  }).length;

  const validate = useCallback(async () => {
    const values: Record<string, string> = {};
    for (const [key, edited] of Object.entries(editedValues)) {
      const field = payload?.fields.find((f) => f.key === key);
      if (field) values[key] = wireValue(field, edited);
    }
    try {
      const result = await validateConfig(values);
      return result.valid;
    } catch {
      return false;
    }
  }, [editedValues, payload?.fields]);

  const apply = useCallback(async () => {
    const values: Record<string, string> = {};
    for (const [key, edited] of Object.entries(editedValues)) {
      const field = payload?.fields.find((f) => f.key === key);
      if (field) values[key] = wireValue(field, edited);
    }
    try {
      const result = await applyConfig(values);
      if (result.applied) {
        await load();
        return true;
      }
      return false;
    } catch {
      return false;
    }
  }, [editedValues, payload?.fields, load]);

  const restart = useCallback(async () => {
    await restartServer();
  }, []);

  const refresh = useCallback(async () => {
    await fetchModels();
    await load();
  }, [load]);

  return {
    payload,
    isLoading,
    error,
    editedValues,
    dirtyCount,
    setEdited,
    validate,
    apply,
    restart,
    refresh,
    getInputValue: (field: ConfigField) => inputValue(field),
    getSourceLabel: sourceLabel,
  };
}