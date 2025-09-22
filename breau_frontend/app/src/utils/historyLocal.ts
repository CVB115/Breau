// src/utils/historyLocal.ts
import { mirrorKey, readMirror, writeMirror } from "./localMirror";

export type HistorySession = Record<string, any>;
export type HistoryBag = { sessions: HistorySession[] };

// Normalize anything we load into the expected bag shape
function safeBag(x: any): HistoryBag {
  if (!x || typeof x !== "object") return { sessions: [] };
  const sessions = Array.isArray((x as any).sessions) ? (x as any).sessions : [];
  return { sessions };
}

// Accept missing/nullable user ids; fall back to "local"
function keyFor(userId?: string | null) {
  return mirrorKey.history(userId ? String(userId) : "local");
}

function bag(userId?: string | null): HistoryBag {
  // readMirror’s default only kicks in if nothing is stored;
  // safeBag also covers corrupt / legacy shapes.
  const raw = readMirror<HistoryBag>(keyFor(userId), { sessions: [] });
  return safeBag(raw);
}

function save(userId: string | null | undefined, b: HistoryBag) {
  // Always persist a normalized array
  const out: HistoryBag = { sessions: Array.isArray(b.sessions) ? b.sessions : [] };
  writeMirror(keyFor(userId), out);
}

/** Get all sessions for a user (never throws, always returns an array) */
export function getHistory(userId?: string | null): HistorySession[] {
  return bag(userId).sessions;
}

/** Append a new session (returns ensured id) */
export function appendSession(userId: string | null | undefined, session: HistorySession): string {
  const id =
    (session as any).id ??
    `s_${Math.random().toString(36).slice(2)}_${Date.now().toString(36)}`;

  const current = bag(userId).sessions;
  const next = [{ ...session, id }, ...current];
  save(userId, { sessions: next });
  return id;
}

/** Update a session by id (shallow); upserts if missing */
export function updateSession(
  userId: string | null | undefined,
  id: string,
  patch: Partial<HistorySession>
) {
  const current = bag(userId).sessions;
  const idx = current.findIndex((s: any) => String(s?.id) === String(id));
  if (idx >= 0) {
    const next = [...current];
    next[idx] = { ...next[idx], ...patch };
    save(userId, { sessions: next });
  } else {
    // Upsert behavior keeps things resilient if we finished while storage was empty
    appendSession(userId, { id, ...patch });
  }
}

/** Remove a session by id */
export function removeSession(userId: string | null | undefined, id: string) {
  const current = bag(userId).sessions;
  const next = current.filter((s: any) => String(s?.id) !== String(id));
  save(userId, { sessions: next });
}

/** Clear history for a user */
export function clearHistory(userId?: string | null) {
  save(userId, { sessions: [] });
}
