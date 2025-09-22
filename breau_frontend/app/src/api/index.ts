// src/api/index.ts
// Centralized client so pages can just `import { API } from "@api"`.

export type Json = Record<string, any>;

// Allow object bodies (we'll JSON.stringify them)
type Init = Omit<RequestInit, "body"> & { body?: any };

async function http(path: string, init: Init = {}) {
  const opts: Init = { ...init };

  // Auto-JSON encode non-FormData bodies
  if (opts.body != null && !(opts.body instanceof FormData)) {
    opts.headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
    opts.body = JSON.stringify(opts.body);
  }

  const res = await fetch(path, opts as RequestInit);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `${res.status} ${res.statusText}`);
  }
  if (res.status === 204) return null;
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? res.json() : res.text();
}

// ---------------- Sessions ----------------
function startSession(body: Json) {
  return http("/api/sessions/start", { method: "POST", body });
}

function step({ session_id, step }: { session_id: string; step: Json }) {
  return http("/api/sessions/step", { method: "POST", body: { session_id, step } });
}

function finish(body: { session_id: string } & Json) {
  return http("/api/sessions/finish", { method: "POST", body });
}

/** v2 direct getter — keep for callers that know they’re on v2 */
function getSession(session_id: string) {
  return http(`/api/sessions/${encodeURIComponent(session_id)}`, { method: "GET" });
}

/* -------------------- 🔥 NEW: unified safe getter -------------------- */
/**
 * Fetch a session by id across backends.
 * Tries v2 route first, then legacy fallbacks.
 * Pass { userId } if your legacy server requires it for the v1 path.
 */
async function getSessionById(
  sessionId: string,
  opts?: { userId?: string }
): Promise<any> {
  const id = encodeURIComponent(sessionId);

  // 1) Preferred (v2-style) route
  try {
    return await http(`/api/sessions/${id}`, { method: "GET" });
  } catch (_) {
    // continue to fallbacks
  }

  // 2) Legacy introspect (if present)
  try {
    return await http(`/api/brew/session/introspect/${id}`, { method: "GET" });
  } catch (_) {
    // continue to fallbacks
  }

  // 3) Legacy user-scoped route (v1)
  if (opts?.userId) {
    const uid = encodeURIComponent(opts.userId);
    try {
      return await http(`/api/brew/session/${uid}/${id}`, { method: "GET" });
    } catch (_) {
      // continue to final fallback
    }
  }

  // 4) Generic legacy route (if server exposes it)
  return await http(`/api/brew/session/${id}`, { method: "GET" });
}
/* ------------------ end NEW: unified safe getter -------------------- */

// ---------------- Feedback ----------------
function feedbackSuggest(session_id: string, body: Json) {
  return http(`/api/feedback/${encodeURIComponent(session_id)}/suggest`, {
    method: "POST",
    body,
  });
}

function feedbackUpsert(session_id: string, body: Json) {
  return http(`/api/feedback/${encodeURIComponent(session_id)}`, {
    method: "POST",
    body,
  });
}

// ---------------- STT ----------------
function sttRecognize(
  blob: Blob,
  extra: { mode?: string; card?: string; lang?: string; text_override?: string; hints?: string[] } = {}
) {
  const form = new FormData();
  form.append("audio", blob, "clip.webm");
  if (extra.mode) form.append("mode", extra.mode);
  if (extra.card) form.append("card", extra.card);
  if (extra.lang) form.append("lang", extra.lang);
  if (extra.text_override) form.append("text_override", extra.text_override);
  if (extra.hints) form.append("hints", JSON.stringify(extra.hints));
  return http("/api/stt/recognize", { method: "POST", body: form });
}

export const API = {
  startSession,
  step,
  finish,
  getSession,        
  getSessionById,    
  feedbackSuggest,
  feedbackUpsert,
  sttRecognize,
};

// Optional re-exports if other code imports these directly
export * from "./types";
export * from "./zodSchemas";
