// src/utils/localMirror.ts

// ---------- Stable keys (per-user) ----------
export const mirrorKey = {
  profile: () => `breau.profile`,                              // global profile doc (stores userId)
  beans: (userId: string) => `breau.beans.${userId}`,
  gear: (userId: string) => `breau.gear.${userId}`,
  gearActive: (userId: string) => `breau.active_gear.${userId}`,
  history: (userId: string) => `breau.history.${userId}`,
  preferences: (userId: string) => `breau.prefs.${userId}`,
} as const;

// ---------- JSON + storage safety ----------
type Json = null | boolean | number | string | Json[] | { [k: string]: Json };

function getStorage(): Storage | null {
  try { if (typeof window !== "undefined") return window.localStorage; } catch {}
  return null;
}
function safeParse<T = unknown>(raw: string | null): T | undefined {
  if (!raw) return undefined;
  try { return JSON.parse(raw) as T; } catch { return undefined; }
}
function safeStringify(v: unknown): string {
  try { return JSON.stringify(v); } catch { return "{}"; }
}

// ---------- core ops ----------
export function readMirror<T = any>(key: string, fallback: T): T {
  const s = getStorage();
  if (!s) return fallback;
  try { return (safeParse<T>(s.getItem(key)) ?? fallback); } catch { return fallback; }
}
export function writeMirror<T = any>(key: string, value: T): void {
  const s = getStorage();
  if (!s) return;
  try {
    const json = safeStringify(value);
    s.setItem(key, json);
    try { window.dispatchEvent(new StorageEvent("storage", { key, newValue: json })); } catch {}
  } catch {}
}
export function mergeMirror<T extends Record<string, any>>(key: string, patch: Partial<T>): T {
  const cur = readMirror<T>(key, {} as T);
  const next = { ...cur, ...patch } as T;
  writeMirror(key, next);
  return next;
}

// ---------- preferences + gear helpers ----------
export interface PreferencesShape {
  timeRoundingSec?: number;
  units?: "metric" | "imperial";
  smartSuggestions?: boolean;
  learningOverlay?: boolean;
  ttsEnabled?: boolean;
  sttEnabled?: boolean;
}
export function readPreferences(userId: string): PreferencesShape {
  return readMirror<PreferencesShape>(mirrorKey.preferences(userId), {});
}
export function mergePreferences(userId: string, patch: PreferencesShape): PreferencesShape {
  const next = { ...readPreferences(userId), ...patch };
  writeMirror(mirrorKey.preferences(userId), next);
  return next;
}
export function setTimeRounding(userId: string, seconds: number): void {
  mergePreferences(userId, { timeRoundingSec: seconds });
}

export function getActiveGearId(userId: string): string | undefined {
  return readMirror<string | undefined>(mirrorKey.gearActive(userId), undefined);
}
export function setActiveGearId(userId: string, id: string): void {
  writeMirror(mirrorKey.gearActive(userId), id);
}
