// src/hooks/useRoundPref.ts
import { useCallback, useEffect, useState } from "react";
import { readPreferences, mergePreferences } from "../utils/localMirror";
import useProfile from "./useProfile";

export type RoundPref = {
  timeRoundingSec?: number;
  gramStep?: number;
  units?: "metric" | "imperial";
  smartSuggestions?: boolean;
  learningOverlay?: boolean;
  ttsEnabled?: boolean;
  sttEnabled?: boolean;
};

const DEFAULT_PREF: RoundPref = {
  timeRoundingSec: 5,
  gramStep: 1,
  units: "metric",
  smartSuggestions: true,
  learningOverlay: true,
  ttsEnabled: true,
  sttEnabled: true,
};

export default function useRoundPref() {
  const { data: profile } = useProfile();
  const userId = profile?.userId || "default-user";

  const [prefs, setPrefs] = useState<RoundPref>(DEFAULT_PREF);

  useEffect(() => {
    const p = readPreferences(userId) as RoundPref;
    setPrefs({ ...DEFAULT_PREF, ...(p ?? {}) });
  }, [userId]);

  const setTimeRounding = useCallback((sec: number) => {
    const next = mergePreferences(userId, { timeRoundingSec: sec }) as RoundPref;
    setPrefs({ ...DEFAULT_PREF, ...(next ?? {}) });
  }, [userId]);

  const setGramStep = useCallback((val: number) => {
    const next = mergePreferences(
      userId,
      { gramStep: Number(val) } as Partial<RoundPref>
    ) as RoundPref | undefined;

    setPrefs({ ...DEFAULT_PREF, ...(next ?? { gramStep: Number(val) }) });
  }, [userId]);


  const setUnits = useCallback((units: RoundPref["units"]) => {
    const next = mergePreferences(userId, { units }) as RoundPref;
    setPrefs({ ...DEFAULT_PREF, ...(next ?? {}) });
  }, [userId]);

  return { userId, prefs, setTimeRounding, setGramStep, setUnits, setPrefs };
}
