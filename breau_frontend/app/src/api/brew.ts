// src/api/brew.ts
export type BrewStartResponse = { session_id: string };

// Payloads the server expects:
export type BloomStep = {
  type: "bloom";
  water_g: number;
  at_ms: number;   // epoch ms
  style: string;   // e.g., "gentle circle"
};

export type PourStep = {
  type: "pour";
  target_g: number; // a.k.a. "water_to"
  at_ms: number;    // epoch ms
  style: string;
};

export type AnyStep = BloomStep | PourStep;

export type BrewFinishBody = {
  session_id: string;
  rating: number;     // integer, not float
  notes?: string;     // optional
};

// Minimal shape for what we read back.
// Keep this flexible because backend “raw session” can evolve.
export type RawSession = {
  session_id: string;
  user_id?: string;
  created_at?: string | number;
  updated_at?: string | number;
  recipe?: {
    total_water_g?: number;
    bloom?: { water_g?: number } | null;
  } | null;
  pours?: Array<{
    type?: "bloom" | "pour";
    at_ms?: number;
    to_g?: number | null;       // server-computed cumulative target (optional)
    target_g?: number | null;   // sometimes stored alongside
    water_g?: number | null;    // bloom water (if bloom step)
    style?: string | null;
  }>;
  events?: Array<{
    kind: string;
    at_ms: number;
    data?: any;
  }>;
  feedback?: {
    rating?: number;
    notes?: string;
  } | null;
};

// Helpers
async function postJSON<T>(path: string, body: any): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const errText = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status} ${res.statusText}: ${errText}`);
  }
  return res.json() as Promise<T>;
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) {
    const errText = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status} ${res.statusText}: ${errText}`);
  }
  return res.json() as Promise<T>;
}

// API
export function startBrew(): Promise<BrewStartResponse> {
  return postJSON<BrewStartResponse>("/api/brew/start", {});
}

// IMPORTANT: do NOT send `to_g`. Server computes/stores it.
export function postBrewStep(session_id: string, step: AnyStep): Promise<{ ok: true }> {
  return postJSON<{ ok: true }>("/api/brew/step", { session_id, step });
}

export function finishBrew(body: BrewFinishBody): Promise<{ ok: true }> {
  return postJSON<{ ok: true }>("/api/brew/finish", body);
}

/**
 * Canonical read URL discovered by tests:
 *   GET /api/brew/session/introspect/:session_id
 * If your deployment uses user scoping, switch to:
 *   `/api/brew/session/${encodeURIComponent(user_id)}/${encodeURIComponent(session_id)}`
 */
export function readSession(session_id: string): Promise<RawSession> {
  return getJSON<RawSession>(`/api/brew/session/introspect/${encodeURIComponent(session_id)}`);
}
