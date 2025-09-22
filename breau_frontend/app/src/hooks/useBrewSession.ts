// src/hooks/useBrewSession.ts
import { useCallback, useMemo } from "react";
import { useUser } from "@context/UserProvider";
import * as historyLocal from "@utils/historyLocal";

/** ------------------------------------------------------------------------ */
/** Types                                                                    */
/** ------------------------------------------------------------------------ */

export type BrewMode = "manual" | "suggested";

export type SessionStartPayload = {
  mode: BrewMode;
  bean?: any;                 // { id, name?, roaster? }
  activeGearSnapshot?: any;   // kettle, grinder, dripper, etc.
  recipe?: {
    brew_name?: string;
    dose?: number;
    total_water?: number;
    ratio?: number | string;
    ratio_str?: string;
    temperature_c?: number;
    steps?: Array<{
      id?: string;
      label?: string;
      type?: "bloom" | "pour";
      water_to?: number; // cumulative g
      pour_style?: "center" | "spiral" | "pulse";
      temp_C?: number;
      kettle_temp_c?: number;
      note?: string;
      plan_start?: string; // "m:ss"
      plan_end?: string;   // "m:ss"
    }>;
  };
  goals_text?: string;
  goals?: string[];
  source?: string;

  // backend needs this (fix for 422):
  user_id?: string;

  [k: string]: any;
};

export type SessionStepPayload = {
  type: "bloom_done" | "pour_done" | "drawdown_done" | string;
  at_ms?: number;       // relative to start
  to_g?: number;        // cumulative mass at the end of this step
  delta_g?: number;     // mass poured in this step
  note?: string;
  [k: string]: any;
};

export type SessionFinishPayload = {
  duration_ms?: number;
  summary?: {
    brew_name?: string;
    timeline?: Array<{
      type: "bloom" | "pour" | "drawdown";
      label?: string;
      start_ms: number;
      end_ms: number;
      cum_g?: number;
      style?: "center" | "spiral" | "pulse";
      agitation?: any;
      note?: string;
    }>;
    [k: string]: any;
  };
  recipe_snapshot?: any; // allow caller (Log) to supply full snapshot
  feedback?: {
    rating?: number; comments?: string;
    acidity?: number; sweetness?: number; bitterness?: number; body?: number; clarity?: number;
    notes?: string[];
    [k: string]: any;
  };
  [k: string]: any;
};

type LiveSession = {
  id: string;                 // server id or local-*
  mode: BrewMode;
  started_at: number;         // epoch ms
  finalized: boolean;

  // snapshots to persist
  bean?: any;
  activeGearSnapshot?: any;
  recipe?: SessionStartPayload["recipe"];
  goals_text?: string;
  goals?: string[];

  // live log
  steps: SessionStepPayload[];
};

// module singleton for the live session
let CURRENT: LiveSession | null = null;

/** ------------------------------------------------------------------------ */
/** JSON client with good error surfacing                                    */
/** ------------------------------------------------------------------------ */

async function postJSON<T>(url: string, body?: any): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`[POST ${url}] ${res.status} ${res.statusText}: ${text || "<empty>"}`);
  }
  return (res.status === 204 ? ({} as any) : await res.json()) as T;
}

// v2-first endpoints with v1 fallbacks
const API = {
  // start
  start_v2: "/api/sessions/start",
  start_v1: "/api/brew/start",

  // step
  step_v2: "/api/sessions/step", // expects { session_id, ... }
  step_v1: (id: string) => `/api/brew/step/${encodeURIComponent(id)}`,

  // finish
  finish_v2: "/api/sessions/finish", // expects { session_id, ... }
  finish_v1: (id: string) => `/api/brew/finish/${encodeURIComponent(id)}`,
};

/** ------------------------------------------------------------------------ */
/** Hook                                                                      */
/** ------------------------------------------------------------------------ */

export default function useBrewSession() {
  const { userId } = useUser();

  /** Start (or reuse) a session */
  const start = useCallback(async (payload: SessionStartPayload) => {
    // Reuse existing unfinalized session
    if (CURRENT && !CURRENT.finalized) {
      CURRENT.recipe = payload.recipe ?? CURRENT.recipe;
      CURRENT.bean = payload.bean ?? CURRENT.bean;
      CURRENT.activeGearSnapshot = payload.activeGearSnapshot ?? CURRENT.activeGearSnapshot;
      CURRENT.goals_text = payload.goals_text ?? CURRENT.goals_text;
      CURRENT.goals = payload.goals ?? CURRENT.goals;
      return CURRENT.id;
    }

    // Provisional local id
    const localId = `local-${Date.now()}`;
    CURRENT = {
      id: localId,
      mode: (payload.mode ?? "manual") as BrewMode,
      started_at: Date.now(),
      finalized: false,
      bean: payload.bean ?? null,
      activeGearSnapshot: payload.activeGearSnapshot ?? null,
      recipe: payload.recipe ?? null,
      goals_text: payload.goals_text ?? "",
      goals: payload.goals ?? [],
      steps: [],
    };

    // include required user_id and normalize fields
    const cleanPayload: SessionStartPayload = {
      user_id: userId || "default-user",
      mode: CURRENT.mode,
      bean: CURRENT.bean ?? null,
      activeGearSnapshot: CURRENT.activeGearSnapshot ?? null,
      recipe: CURRENT.recipe ?? null,
      goals_text: CURRENT.goals_text ?? "",
      goals: Array.isArray(CURRENT.goals) ? CURRENT.goals : [],
      source: payload.source ?? "ui",
    };

    // Try v2 first, then v1 silently
    try {
      const resp = await postJSON<{ session_id?: string }>(API.start_v2, cleanPayload);
      if (resp?.session_id && CURRENT) CURRENT.id = resp.session_id;
    } catch {
      try {
        const resp = await postJSON<{ session_id?: string }>(API.start_v1, cleanPayload);
        if (resp?.session_id && CURRENT) CURRENT.id = resp.session_id;
      } catch {
        // offline/validation: keep local session usable
      }
    }
    return CURRENT.id;
  }, [userId]);

  /** Append a step (Bloom done, Pour N done, etc.) */
  const step = useCallback(async (s: SessionStepPayload) => {
    if (!CURRENT || CURRENT.finalized) return;
    const clone = { ...s };
    if (typeof clone.at_ms !== "number") {
      clone.at_ms = Math.max(0, Date.now() - CURRENT.started_at);
    }
    // store locally
    CURRENT.steps.push(clone);

    // best effort server log (v2 first)
    try {
      await postJSON(API.step_v2, { session_id: CURRENT.id, ...clone });
    } catch {
      try {
        await postJSON(API.step_v1(CURRENT.id), clone);
      } catch {
        /* ignore offline */
      }
    }
  }, []);

  /** Finish the session and persist to local history */
  const finish = useCallback(async (extra?: SessionFinishPayload) => {
    if (!CURRENT) return "";
    if (CURRENT.finalized) return CURRENT.id;

    const id = CURRENT.id;
    const endedAt = Date.now();
    const duration_ms =
      typeof extra?.duration_ms === "number"
        ? extra.duration_ms
        : Math.max(0, endedAt - CURRENT.started_at);

    // Normalize plan steps (accept multiple legacy keys)
    const normalizeSteps = (steps: any[] = []) =>
      steps.map((s: any) => ({
        id: s.id,
        label: s.label,
        type: s.type, // "bloom" | "pour"
        water_to: s.water_to ?? s.target_g ?? s.to_g ?? s.cum_g ?? 0,
        pour_style: s.pour_style ?? s.style ?? undefined,
        kettle_temp_c: s.kettle_temp_c ?? s.temp_C ?? undefined,
        note: s.note,
        plan_start: s.plan_start,
        plan_end: s.plan_end,
      }));

    // Prefer the recipe_snapshot coming from Log (has all pours)
    const recipeSnap: any = extra?.recipe_snapshot
      ? { ...extra.recipe_snapshot, steps: normalizeSteps(extra.recipe_snapshot.steps) }
      : {
          ...(CURRENT.recipe || {}),
          steps: normalizeSteps((CURRENT.recipe as any)?.steps),
        };

    // Ensure bean/gear present so Summary can render offline
    if (recipeSnap && !("bean" in recipeSnap)) recipeSnap.bean = CURRENT.bean || null;
    if (recipeSnap && !("gear" in recipeSnap)) recipeSnap.gear = CURRENT.activeGearSnapshot || null;

    // Build finish payload (best-effort server write)
    const finishPayload: SessionFinishPayload & {
      recipe_snapshot?: any;
      steps?: SessionStepPayload[];
    } = {
      duration_ms,
      summary: { ...(extra?.summary || {}) },
      feedback: extra?.feedback ? { ...extra.feedback } : undefined,
      steps: CURRENT.steps,        // actual logged events (can be empty)
      recipe_snapshot: recipeSnap, // full plan with all pours
    };

    // Try v2 first (body includes session_id), then v1 (id in URL)
    try {
      await postJSON<{ ok?: boolean }>(API.finish_v2, { session_id: id, ...finishPayload });
    } catch {
      try {
        await postJSON<{ ok?: boolean }>(API.finish_v1(id), finishPayload);
      } catch {
        /* offline allowed */
      }
    }

    // ------- Local history write (Summary reads this) -------
    const uid = userId || "default-user";
    const existing = historyLocal
      .getHistory(uid)
      .find((s: any) => String(s?.id) === String(id));

    const entry = {
      id,
      createdAt: existing?.createdAt || new Date(CURRENT.started_at).toISOString(),
      updatedAt: new Date().toISOString(),
      mode: CURRENT.mode,

      // snapshots for Summary
      bean: CURRENT.bean || null,
      activeGearSnapshot: CURRENT.activeGearSnapshot || null,

      // Persist the normalized recipe snapshot so Summary always has the full plan
      recipe_snapshot: {
        ...recipeSnap,
        // convenience aliases Summary expects in your UI
        dose_g: recipeSnap.dose ?? (CURRENT as any)?.dose ?? undefined,
        water_g: recipeSnap.total_water ?? (CURRENT as any)?.total_water ?? undefined,
        temperature_c: recipeSnap.temperature_c,
        ratio: recipeSnap.ratio ?? recipeSnap.ratio_str,
        grind_label: recipeSnap.grind_label,
        grind_setting: recipeSnap.grind_setting,
        grind_target_micron: recipeSnap.grind_target_micron,
        grind_scale: recipeSnap.grind_scale,
      },

      // raw steps/events user actually marked done
      steps: CURRENT.steps.slice(),

      // summary block with timeline if provided
      summary: {
        brew_name:
          extra?.summary?.brew_name ||
          recipeSnap?.brew_name ||
          existing?.summary?.brew_name ||
          "",
        duration_ms,
        timeline: extra?.summary?.timeline || [],
      },

      // assessment (from /brew/assess)
      feedback: extra?.feedback
        ? { ...existing?.feedback, ...extra.feedback }
        : existing?.feedback || undefined,
    };

    if (existing) historyLocal.updateSession(uid, id, entry);
    else historyLocal.appendSession(uid, entry);

    CURRENT.finalized = true;
    return id;
  }, [userId]);

  /** Utilities */
  const getSessionId = useCallback(() => CURRENT?.id || null, []);
  const clear = useCallback(() => { CURRENT = null; }, []);
  const current = useMemo(() => CURRENT, []);

  return { start, step, finish, getSessionId, clear, current };
}
