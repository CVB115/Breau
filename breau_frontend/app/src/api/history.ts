import { api } from "./client";
import { API } from "./endpoints";

/** ---------- Normalized types used by the UI ---------- */
export type NoteScore = { note: string; score: number };
export type HistoryItem = {
  session_id: string;
  date: string; // ISO
  predicted_notes?: NoteScore[];
  perceived_notes?: NoteScore[];
};
export type SessionDetail = HistoryItem & {
  recipe?: any;
  feedback?: any;
  metrics?: Record<string, any>;
};

/** ---------- Fetch list & detail with loose normalization ---------- */
export async function fetchHistory(userId: string, limit = 20): Promise<HistoryItem[]> {
  const raw = await api.get<unknown>(API.history(userId, limit));
  return normalizeHistory(raw);
}

export async function fetchSessionDetail(userId: string, sessionId: string): Promise<SessionDetail> {
  const raw = await api.get<unknown>(API.sessionDetail(userId, sessionId));
  return normalizeSessionDetail(raw);
}

/** ---------- Normalizers (accept many shapes) ---------- */
function normalizeHistory(raw: any): HistoryItem[] {
  let arr: any[] = [];
  if (Array.isArray(raw)) arr = raw;
  else if (Array.isArray(raw?.data)) arr = raw.data;
  else if (Array.isArray(raw?.sessions)) arr = raw.sessions;

  return arr
    .map((x) => normalizeHistoryItem(x))
    .filter((x): x is HistoryItem => !!x);
}

function normalizeHistoryItem(x: any): HistoryItem | undefined {
  if (!x || typeof x !== "object") return;
  const id = x.session_id ?? x.sessionId ?? x.id ?? x._id;
  if (!id) return;

  const dateRaw =
    x.date ?? x.started_at ?? x.start_time ?? x.timestamp ?? x.created_at ?? new Date().toISOString();
  const date = toISO(dateRaw);

  const predicted = normalizeNotes(x.predicted_notes ?? x.predictedNotes ?? x.notes_predicted);
  const perceived = normalizeNotes(x.perceived_notes ?? x.perceivedNotes ?? x.notes_perceived);

  return {
    session_id: String(id),
    date,
    predicted_notes: predicted,
    perceived_notes: perceived,
  };
}

function normalizeSessionDetail(raw: any): SessionDetail {
  const x = raw?.data && typeof raw.data === "object" ? raw.data : raw?.session || raw;

  const base = normalizeHistoryItem(x) || {
    session_id: String(x?.session_id ?? x?.id ?? "unknown"),
    date: toISO(x?.date ?? Date.now()),
  };

  const recipe = x?.recipe ?? x?.Recipe ?? x?.result?.recipe;
  const feedback = x?.feedback ?? x?.result?.feedback;
  const metrics = x?.metrics ?? x?.stats;

  return { ...base, recipe, feedback, metrics };
}

function normalizeNotes(n: any): { note: string; score: number }[] | undefined {
  if (!n) return undefined;
  const arr = Array.isArray(n) ? n : [n];
  return arr
    .map((it) => {
      if (typeof it === "string") return { note: it, score: 0 };
      if (typeof it?.note === "string") return { note: it.note, score: Number(it.score ?? it.prob ?? 0) };
      if (typeof it?.label === "string") return { note: it.label, score: Number(it.score ?? 0) };
      return null;
    })
    .filter((x): x is { note: string; score: number } => !!x);
}

function toISO(v: any): string {
  const d = v instanceof Date ? v : new Date(v);
  return isNaN(d as any) ? new Date().toISOString() : d.toISOString();
}
