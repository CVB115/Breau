// src/api/session.ts
// -----------------------------------------------------------------------------
// Self-contained Session API with proper finish() payload support.
// - No imports from ./client or ./endpoints (avoids export mismatch).
// - Uses fetch() directly.
// - Adds compileStepsFromManualPlan() so you can send the full recipe.steps.
// -----------------------------------------------------------------------------

// ---------- Types (lean; align to your backend without being strict) ----------
export type PourStyle = "center" | "spiral" | "pulse" | string;

export type ManualPlanBloom = {
  water_g?: number | null;     // incremental grams for bloom
  style?: PourStyle | null;
  plan_start?: string | null;  // "mm:ss"
  plan_end?: string | null;    // "mm:ss"
};

export type ManualPlanPour = {
  water_g?: number | null;     // incremental grams for this pour
  style?: PourStyle | null;
  plan_start?: string | null;  // "mm:ss"
  plan_end?: string | null;    // "mm:ss"
};

export type ManualPlan = {
  bloom?: ManualPlanBloom | null;
  pours?: ManualPlanPour[] | null;
};

export type GearSnapshot = {
  label?: string | null;
  brewer?: { name?: string | null } | null;
  grinder?: { name?: string | null } | null;
  filter?: { name?: string | null } | null;
  water?: { name?: string | null; temp_c?: number | null } | null;
};

export type GrindScale =
  | { type: "numbers"; min?: number; max?: number; step?: number }
  | { type: string; [k: string]: unknown };

export type RecipeSnapshot = {
  brew_name?: string | null;
  dose_g?: number | null;
  ratio?: number | string | null;
  total_water?: number | null;
  temperature_c?: number | null;

  steps?: Array<{
    id?: string;
    label?: string;
    type: "bloom" | "pour";
    water_to: number;                 // cumulative target grams
    pour_style?: PourStyle | null;
    plan_start?: string | null;       // "mm:ss"
    plan_end?: string | null;         // "mm:ss"
  }>;

  // grind info
  grind_target_micron?: number | null;
  grind_setting?: number | string | null;
  grind_label?: string | null;
  grind_scale?: GrindScale | null;
};

export type StartBody = {
  user_id?: string | null;
  session_id?: string | null;
  mode?: "manual" | "auto" | string | null;
  created_at_ms?: number | null;

  recipe?: RecipeSnapshot;
  gear?: GearSnapshot;
};

export type FinishBody = {
  session_id: string;
  ended_at_ms?: number | null;

  // ✅ snapshots the server should persist
  recipe?: RecipeSnapshot;
  gear?: GearSnapshot;

  // optional streams if you keep them
  pours?: any[];
  events?: any[];
  summary?: any;
};

export type SessionDoc = {
  session?: {
    schema_version?: string;
    id: string;
    user_id?: string;
    created_utc?: number;
    status?: "started" | "finished" | string;
    mode?: "manual" | "auto" | string;
    source?: string;

    bean?: any;
    gear?: GearSnapshot;
    recipe?: RecipeSnapshot;
    pours?: any[];
    events?: any[];
    rating?: number | null;
    notes?: string | null;
    finished_utc?: number | null;
    summary?: any;
  };
};

// ----------------------- Minimal fetch helpers -------------------------------
async function apiGet<T>(url: string): Promise<T> {
  const res = await fetch(url, { credentials: "same-origin" });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`GET ${url} failed: ${res.status} ${text}`);
  }
  return res.json() as Promise<T>;
}

async function apiPost<T>(url: string, body: any): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`POST ${url} failed: ${res.status} ${text}`);
  }
  return res.json() as Promise<T>;
}

// ------------------ Compile plan: incremental -> cumulative -------------------
const num = (v: any): number => {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : 0;
};

/**
 * Convert your UI manual plan (incremental per step) into Summary‑ready steps
 * with cumulative `water_to`.
 */
export function compileStepsFromManualPlan(plan?: ManualPlan): RecipeSnapshot["steps"] {
  if (!plan) return [];
  let cum = 0;
  const steps: NonNullable<RecipeSnapshot["steps"]> = [];

  // Bloom
  if (plan.bloom) {
    const inc = num(plan.bloom.water_g);
    cum += inc;
    steps.push({
      id: "bloom",
      label: "Bloom",
      type: "bloom",
      water_to: cum,
      pour_style: plan.bloom.style ?? "center",
      plan_start: plan.bloom.plan_start ?? "0:00",
      plan_end: plan.bloom.plan_end ?? null,
    });
  }

  // Pours
  const N = plan.pours?.length ?? 0;
  for (let i = 0; i < N; i++) {
    const p = plan.pours![i] || {};
    const inc = num(p.water_g);
    cum += inc;
    steps.push({
      id: `p${i + 1}`,
      label: `Pour ${i + 1}`,
      type: "pour",
      water_to: cum,
      pour_style: p.style ?? "center",
      plan_start: p.plan_start ?? null,
      plan_end: p.plan_end ?? null,
    });
  }

  return steps;
}

// ------------------------------ API calls ------------------------------------
/** Start a session */
async function start(body: StartBody): Promise<SessionDoc> {
  // You had logs for /api/sessions/start earlier, but the working set uses /api/brew/start.
  // Use brew/* for consistency with Summary fetches.
  return apiPost<SessionDoc>("/api/brew/start", body);
}

/** Finish a session (send full snapshot here) */
async function finish(body: FinishBody): Promise<SessionDoc> {
  return apiPost<SessionDoc>("/api/brew/finish", body);
}

/** Fetch a single session doc (the one Summary shows in "debug: server doc") */
async function getOne(userId: string, sessionId: string): Promise<SessionDoc> {
  const u = encodeURIComponent(userId);
  const s = encodeURIComponent(sessionId);
  return apiGet<SessionDoc>(`/api/brew/session/${u}/${s}`);
}

/** Optionally list recent sessions for a user */
async function listRecent(userId: string, limit = 20): Promise<{ sessions: SessionDoc["session"][] }> {
  const u = encodeURIComponent(userId);
  return apiGet<{ sessions: SessionDoc["session"][] }>(`/api/brew/sessions/${u}?limit=${limit}`);
}

// ------------------------------ Facade ---------------------------------------
export const session = { start, finish, getOne, listRecent };
export default session;
