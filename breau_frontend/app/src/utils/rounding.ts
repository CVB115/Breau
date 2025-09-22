// src/utils/rounding.ts
export type RoundPrefs = {
  timeRoundingSec?: number; // snap seconds (e.g., 5)
  gramStep?: number;        // snap grams (e.g., 1 or 0.5)
};

function snap(x: number, step: number): number {
  if (!step || step <= 0) return x;
  return Math.round(x / step) * step;
}

export function roundSeconds(sec: number, prefs?: RoundPrefs): number {
  return snap(sec, prefs?.timeRoundingSec ?? 0);
}

export function roundGrams(grams: number, prefs?: RoundPrefs): number {
  return snap(grams, prefs?.gramStep ?? 0);
}

export function roundPours<T extends { grams?: number }>(pours: T[], pref: RoundPrefs): T[] {
  const step = pref.gramStep ?? 0;
  if (!step) return pours;
  return pours.map(p => (typeof p.grams === "number" ? { ...p, grams: roundGrams(p.grams, pref) } : p));
}
