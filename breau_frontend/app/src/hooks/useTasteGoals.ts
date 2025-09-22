// src/hooks/useTasteGoals.ts
import { useCallback, useMemo, useState } from "react";
import { useUser } from "@context/UserProvider";
import { readMirror, writeMirror } from "@utils/localMirror";

// Single source of truth for taste goals (local-first, backend-optional)
export type TasteGoals = {
  strength: "light" | "medium" | "strong";
  acidity: "low" | "medium" | "high";
  body: "light" | "medium" | "heavy";
  sweetness: "low" | "medium" | "high";
  notes: string; // comma-separated notes
  use_for_suggest?: boolean;
};

const DEFAULTS: TasteGoals = {
  strength: "medium",
  acidity: "medium",
  body: "medium",
  sweetness: "medium",
  notes: "",
  use_for_suggest: true,
};

export default function useTasteGoals() {
  const { userId } = useUser();

  // mirror key (works even if mirrorKey.tasteGoals doesn't exist in your util)
  const key = useMemo(
    () => `breau.goals.${userId}`,
    [userId]
  );

  // local-first state
  const [goals, setGoals] = useState<TasteGoals>(() => {
    try {
      // Prefer mirror util if present
      const fromMirror = readMirror<TasteGoals>(key, null as any);
      if (fromMirror && typeof fromMirror === "object") return { ...DEFAULTS, ...fromMirror };
    } catch {}
    try {
      const raw = localStorage.getItem(key);
      if (raw) return { ...DEFAULTS, ...(JSON.parse(raw) as any) };
    } catch {}
    return DEFAULTS;
  });

  const persist = useCallback((next: TasteGoals) => {
    setGoals(next);
    try {
      writeMirror(key, next);
    } catch {
      localStorage.setItem(key, JSON.stringify(next));
    }
  }, [key]);

  const patch = useCallback((p: Partial<TasteGoals>) => {
    persist({ ...goals, ...p });
  }, [goals, persist]);

  const reset = useCallback(() => persist(DEFAULTS), [persist]);

  const refresh = useCallback(() => {
    try {
      const fromMirror = readMirror<TasteGoals>(key, null as any);
      if (fromMirror && typeof fromMirror === "object") {
        setGoals({ ...DEFAULTS, ...fromMirror });
        return;
      }
    } catch {}
    try {
      const raw = localStorage.getItem(key);
      setGoals(raw ? { ...DEFAULTS, ...(JSON.parse(raw) as any) } : DEFAULTS);
    } catch {
      setGoals(DEFAULTS);
    }
  }, [key]);

  return { key, goals, setGoals: persist, patch, reset, refresh, DEFAULTS };
}
