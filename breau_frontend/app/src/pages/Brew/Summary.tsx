// src/pages/Brew/Summary.tsx
import React, { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import useProfile from "@hooks/useProfile";
import useBrewHistory from "@hooks/useBrewHistory";
import { API } from "@api";

/* ------------------------------ local types ----------------------------- */
type TimelineSeg = {
  type: "bloom" | "pour" | "drawdown";
  label?: string;
  start_ms: number;
  end_ms: number;
  cum_g?: number;
  style?: "center" | "spiral" | "pulse";
  note?: string;
};

type StepSnap = {
  id?: string;
  label?: string;
  type?: "bloom" | "pour";
  water_to?: number;
  pour_style?: "center" | "spiral" | "pulse";
  kettle_temp_c?: number;
  note?: string;
  plan_start?: string;
  plan_end?: string;
};

type RecipeSnap = {
  brew_name?: string;
  dose?: number;
  ratio?: string | number;
  total_water?: number;
  temperature_c?: number;

  // NEW: grind info from Setup/Log
  grind_text?: string;      // e.g., "22 clicks" or "Med‑fine"
  grind_micron?: number;    // e.g., 800
  grind_unit?: string;      // "µm" by default

  bean?: Record<string, any> | null;
  gear?: Record<string, any> | null;
  steps?: StepSnap[];
};


type SummaryShape = {
  brew_name?: string;
  target_total_g?: number;
  recipe_snapshot?: RecipeSnap;
  timeline?: TimelineSeg[];
};

type LocalHistoryEntry = {
  id: string;
  started_at_ms?: number;
  duration_ms?: number;
  summary?: any;
  meta?: any;
  feedback?: any;
  cup_feedback?: any;
  session_id?: string;
  server_session_id?: string;
  aliases?: string[];
};

type NavState = { session_id?: string; brew_name?: string; type?: "manual" | "suggested" };

/* --------------------------- normalization helpers --------------------------- */
function pick<T>(...vals: (T | undefined)[]): T | undefined {
  for (const v of vals) if (v !== undefined) return v;
  return undefined;
}

function normalizeStep(raw: any, idx: number): StepSnap {
  return {
    id: raw?.id ?? String(idx),
    label: raw?.label,
    type: raw?.type === "bloom" ? "bloom" : "pour",
    water_to: pick(raw?.water_to, raw?.to_g, raw?.target_g),
    pour_style: pick(raw?.pour_style, raw?.style),
    kettle_temp_c: pick(raw?.kettle_temp_c, raw?.temp_c, raw?.temperature_c, raw?.temp_C),
    note: raw?.note,
    plan_start: raw?.plan_start,
    plan_end: raw?.plan_end,
  };
}

function normalizeRecipe(raw: any): RecipeSnap {
  if (!raw) return {};
  return {
    brew_name: pick(raw.brew_name, raw.name, raw.title),
    dose: pick(raw.dose, raw.dose_g, raw.doseGrams),
    ratio: pick(raw.ratio, raw.ratio_str, raw.ratioString),
    total_water: pick(raw.total_water, raw.water_g, raw.totalWater),
    temperature_c: pick(raw.temperature_c, raw.temp_c, raw.kettle_temp_c),

    // NEW — grind fields from backend Setup/Log shapes
    grind_text: pick(
      raw.grind_text, raw.grind, raw.grindLabel, raw.grind_setting, raw.grindSetting, raw.grind_notes
    ),
    grind_micron: pick(
      raw.grind_micron, raw.grind_um, raw.micron, raw.grindMicron
    ),
    grind_unit: pick(raw.grind_unit, raw.grindUnit, "µm"),

    bean: raw.bean ?? null,
    gear: raw.gear ?? null,
    steps: Array.isArray(raw.steps)
      ? raw.steps.map(normalizeStep)
      : Array.isArray(raw.steps_plan)
      ? raw.steps_plan.map(normalizeStep)
      : [],
  };
}


function normalizeTimelineFromPoursEvents(pours: any[], events: any[]): TimelineSeg[] {
  const tl: TimelineSeg[] = [];
  for (const p of pours || []) {
    const t = Number(p.at_ms ?? p.start_ms ?? p.ms);
    if (Number.isFinite(t)) {
      tl.push({
        type: p.type === "bloom" ? "bloom" : "pour",
        label: p.label ?? (p.type === "bloom" ? "Bloom" : "Pour"),
        start_ms: t,
        end_ms: t + 1,
        cum_g: pick(p.to_g, p.target_g, p.water_to),
        style: pick(p.style, p.pour_style),
        note: p.note,
      });
    }
  }
  for (const e of events || []) {
    if (e.type === "drawdown") {
      const t = Number(e.at_ms ?? e.ms);
      if (Number.isFinite(t)) tl.push({ type: "drawdown", label: "Drawdown", start_ms: t, end_ms: t + 1 });
    }
  }
  return tl.sort((a, b) => a.start_ms - b.start_ms);
}

function normalizeSummary(raw: any): SummaryShape {
  if (!raw) return {};
  const s = raw.recipe_snapshot || raw.recipe || raw.recipeSnapshot ? raw : (raw.summary ?? {});
  const recipeRaw = pick(s.recipe_snapshot, s.recipe, s.recipeSnapshot);
  const recipe = normalizeRecipe(recipeRaw);

  const timeline: TimelineSeg[] =
    Array.isArray(s.timeline) ? s.timeline : normalizeTimelineFromPoursEvents(s.pours || [], s.events || []);

  return {
    brew_name: pick(s.brew_name, recipe.brew_name),
    target_total_g: pick(s.target_total_g, recipe.total_water),
    recipe_snapshot: recipe,
    timeline,
  };
}

// --- new helpers: mode/goals/startedAt derived from either local or server ---
function deriveMode(local: any, serverDoc: any): "manual" | "suggested" {
  const m =
    local?.meta?.mode ||
    local?.mode ||
    serverDoc?.session?.mode ||
    serverDoc?.mode;
  return m === "suggested" ? "suggested" : "manual";
}
function deriveGoals(local: any, serverDoc: any): any[] {
  const g =
    local?.meta?.goals ||
    local?.goals ||
    serverDoc?.session?.goals ||
    serverDoc?.goals;
  if (Array.isArray(g) && g.length) return g;

  // graceful fallback if only a text prompt exists
  const txt = local?.meta?.goals_text || serverDoc?.session?.goals_text;
  return txt?.trim() ? [{ raw: String(txt).trim() }] : [];
}
function deriveStartedAt(local: any, serverDoc: any): string | number | undefined {
  return serverDoc?.session?.started_at || local?.started_at_ms;
}

// --- new helper: normalize gear for UI regardless of where fields live ---
function normalizeGearForDisplay(g: any) {
  if (!g) {
    return { display: "—", brewer: "—", grinder: "—", water: "—", filter: undefined };
  }
  const brewer =
    g?.brewer?.name || g?.brewer?.id || g?.brewer_name || (typeof g?.brewer === "string" ? g.brewer : undefined);
  const grinder =
    g?.grinder?.model || g?.grinder?.name || g?.grinder?.brand ||
    g?.grinder_model || (typeof g?.grinder === "string" ? g.grinder : undefined);
  const water =
    g?.water?.name || g?.water?.style || g?.water_profile || (typeof g?.water === "string" ? g.water : undefined);
  const filter =
    g?.filter?.name || g?.filter?.material || (typeof g?.filter === "string" ? g.filter : undefined);

  const label = g?.label || g?.display || [brewer, grinder, water].filter(Boolean).join(" • ");
  return {
    display: label || "—",
    brewer: brewer || "—",
    grinder: grinder || "—",
    water: water || "—",
    filter,
  };
}

function deriveSuggestFeedback(local: any, serverDoc: any): { rating?: number; comment?: string } {
  // try server canonical shape first
  const sfb = serverDoc?.session?.feedback ?? serverDoc?.feedback ?? {};
  let rating = sfb?.suggest_rating;
  let comment = sfb?.suggest_comment;

  // fallbacks from local mirrors
  if (rating == null) rating = local?.feedback?.suggest_rating ?? local?.meta?.suggest?.rating;
  if (comment == null) comment = local?.feedback?.suggest_comment ?? local?.meta?.suggest?.comment;

  // normalize to numbers/strings
  const rNum = typeof rating === "string" ? Number(rating) : rating;
  const cStr = typeof comment === "number" ? String(comment) : comment;

  return { rating: Number.isFinite(rNum) ? rNum : undefined, comment: cStr?.trim() ? cStr : undefined };
}



/* -------------------------------- component -------------------------------- */
export default function BrewSummary() {
  const nav = useNavigate();
  const { state } = useLocation();
  const { session_id: navId, brew_name: nameFromNav } = (state || {}) as NavState;

  const { data: profile } = useProfile();
  const { sessions: history } = useBrewHistory() as any;

  const [sessionId, setSessionId] = useState<string | null>(navId ?? null);
  const [local, setLocal] = useState<LocalHistoryEntry | null>(null);
  const [serverDoc, setServerDoc] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);

  const brewType: "manual" | "suggested" = deriveMode(local, serverDoc);
  // pick latest if none passed
  useEffect(() => {
    if (sessionId) return;
    const latest = Array.isArray(history) && history.length ? history[history.length - 1] : null;
    if (latest?.id) setSessionId(latest.id);
  }, [sessionId, history]);

  // pull local entry (match by several ids/aliases)
  useEffect(() => {
    if (!sessionId) return;
    const arr = Array.isArray(history) ? history : [];
    const entry =
      arr.find(
        (x: any) =>
          x.id === sessionId ||
          x.session_id === sessionId ||
          x.server_session_id === sessionId ||
          (Array.isArray(x.aliases) && x.aliases.includes(sessionId))
      ) || null;
    setLocal(entry as LocalHistoryEntry | null);
  }, [sessionId, history]);

  // best-effort server read (via API client)
  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!sessionId) return;
      if (String(sessionId).startsWith("local-")) return;
      try {
        setLoading(true);
        const doc = await API.getSessionById(sessionId, { userId: profile?.userId || "default-user" });
        if (!cancelled) setServerDoc(doc || null);
      } catch {
        // ignore & stay on local summary
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [sessionId, profile?.userId]);


  /* ------------------------------ choose summary ------------------------------ */
  const rawLocalSummary = useMemo(() => {
  if (!local) return undefined;
  const base = pick(local.summary, local.meta?.summary, local.meta) || {};
  const rs = base.recipe_snapshot ?? (local as any).recipe_snapshot ?? (local as any).meta?.recipe_snapshot;
  return rs ? { ...base, recipe_snapshot: rs } : base;
}, [local]);
  const localSummary = normalizeSummary(rawLocalSummary);

  const serverDerived = useMemo<SummaryShape>(() => {
    if (!serverDoc) return {};
    // your backend wraps under { session: { ... } }
    const S = (serverDoc as any).session ?? serverDoc;

    const recipeRaw = pick(S?.recipe, S?.recipe_snapshot, S?.recipeSnapshot);
    const recipe = normalizeRecipe(recipeRaw);

    // carry bean/gear onto the recipe snapshot
    const recipeWithSnaps: RecipeSnap = {
      ...recipe,
      bean: S?.bean ?? recipe?.bean ?? null,
      gear: S?.gear ?? recipe?.gear ?? null,
    };

    const tl =
      Array.isArray(S?.timeline) ? S.timeline : normalizeTimelineFromPoursEvents(S?.pours || [], S?.events || []);

    return {
      brew_name: pick(S?.brew_name, recipe?.brew_name),
      target_total_g: pick(S?.target_total_g, recipe?.total_water),
      recipe_snapshot: recipeWithSnaps,
      timeline: tl,
    };
  }, [serverDoc]);

  const summary: SummaryShape =
    localSummary && (localSummary.recipe_snapshot || localSummary.timeline || localSummary.brew_name)
      ? localSummary
      : serverDerived;

  /* ------------------------------ derived ui ------------------------------ */
  const brewName = (nameFromNav && nameFromNav.trim()) || summary?.brew_name || "Manual brew";
  const recipe = summary?.recipe_snapshot;
  const bean = recipe?.bean || null;
  const gear = recipe?.gear || null;
  const gearUI = normalizeGearForDisplay(gear);
  const goalsList = deriveGoals(local, serverDoc);
  const startedAt = deriveStartedAt(local, serverDoc);
  const steps: StepSnap[] = Array.isArray(recipe?.steps) ? (recipe!.steps as StepSnap[]) : [];
  const suggestFB = deriveSuggestFeedback(local, serverDoc);

  const totalWater = useMemo(() => {
    if (Number.isFinite(recipe?.total_water as any)) return Number(recipe!.total_water);
    const fromTL = Math.max(0, ...(summary?.timeline || []).map((s) => Number(s.cum_g || 0)));
    if (fromTL > 0) return fromTL;
    const fromSteps = Math.max(0, ...steps.map((s) => Number(s.water_to || 0)));
    return fromSteps || undefined;
  }, [recipe?.total_water, summary?.timeline, steps]);

  const windowMs = useMemo(() => {
    const base = 5 * 60 * 1000;
    const end = Math.max(0, ...(summary?.timeline || []).map((s) => s.end_ms));
    return Math.max(base, end || base);
  }, [summary?.timeline]);

  const segColor = (t: TimelineSeg["type"]) =>
    t === "bloom" ? "#ff9f43" : t === "pour" ? "#3a86ff" : "#9aa0a6";

  function msToMMSS(ms: number) {
    const s = Math.max(0, Math.round(ms / 1000));
    const mm = Math.floor(s / 60);
    const ss = String(s % 60).padStart(2, "0");
    return `${mm}:${ss}`;
  }

  const feedback = pick(local?.feedback, local?.cup_feedback);
  function Stars({ value = 0, max = 5, size = 16 }: { value?: number; max?: number; size?: number }) {
    const n = Math.round(value);
    return (
      <div className="row" aria-label="overall stars">
        {Array.from({ length: max }, (_, i) => (
          <svg key={i} width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 2l3.09 6.26L22 9.27l-5 4.88L18.18 22 12 18.56 5.82 22 7 14.15l-5-4.88 6.91-1.01L12 2z"
                  fill={i < n ? "#ffd166" : "none"} stroke="#9aa0a6" strokeWidth="1.2"/>
          </svg>
        ))}
      </div>
    );
  }

  function makeRebrewState() {
    return {
      source: "summary-brew-again" as const,
      from_session_id: sessionId ?? undefined,   // <— add
      recipe: recipe ?? {},
      bean: bean ?? null,
      gear: gear ?? null,
      historySession: { id: sessionId ?? undefined, date: startedAt },
    };
  }
  function makeAdjustState() {
    return {
      source: "summary-adjust" as const,
      reference_session_id: sessionId ?? undefined, // <— add
      prior_recipe: recipe ?? {},
      bean: bean ?? null,
      gear: gear ?? null,
      historySession: { id: sessionId ?? undefined, date: startedAt },
    };
  }

  /* ---------------------------------- UI ---------------------------------- */
  return (
    <main className="page">
      {/* Header */}
      <section className="card">
        <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
          <div className="col" style={{ gap: 6 }}>
            <h1>{brewName}</h1>
            <div className="row" style={{ gap: 10, flexWrap: "wrap", fontSize: 13, opacity: 0.9 }}>
              <span className="pill pill--type">{brewType}</span>
              <div>💧 Water: <b>{totalWater ?? "—"}</b> g</div>
              <div>⚖️ Dose: <b>{recipe?.dose ?? "—"}</b> g</div>
              <div>📐 Ratio: <b>{(recipe?.ratio as any) ?? "—"}</b></div>
              {loading ? <span className="form-label">syncing…</span> : null}
            </div>
          </div>
          <div className="row" style={{ gap: 8 }}>
            <button className="btn secondary" onClick={() => nav(-1)}>Back</button>
          </div>
        </div>
      </section>

      {/* Bean & Gear */}
      <section className="grid-2col">
        <div className="card col" style={{ gap: 6 }}>
          <h2>Bean</h2>
          {bean ? (
            <>
              <KV k="Name" v={bean.name || "—"} />
              <KV k="Roaster" v={bean.roaster || "—"} />
              <KV k="Origin" v={bean.origin || "—"} />
              <KV k="Variety" v={bean.variety || "—"} />
              <KV k="Process" v={bean.process || "—"} />
            </>
          ) : (
            <div className="form-label">No bean snapshot.</div>
          )}
        </div>

        <div className="card col" style={{ gap: 6 }}>
         <h2>Gear</h2>
          {gear ? (
            <>
              <KV k="Display" v={gearUI.display} />
              <KV k="Brewer"  v={gearUI.brewer} />
              <KV k="Grinder" v={gearUI.grinder} />
              <KV k="Water"   v={gearUI.water} />
              {gearUI.filter ? <KV k="Filter" v={gearUI.filter} /> : null}
              <KV
                k="Grind"
                v={
                  recipe?.grind_text
                    ? (recipe.grind_micron
                        ? `${recipe.grind_text} • ${recipe.grind_micron}${recipe.grind_unit || "µm"}`
                        : recipe.grind_text)
                    : gearUI.grinder
                }
              />
            </>
          ) : (
            <div className="form-label">No gear snapshot.</div>
          )}

        </div>
      </section>

      {/* Recipe steps */}
      <section className="card">
        <h2>Recipe</h2>
        {steps.length ? (
          <div className="grid-2col" style={{ marginTop: 8 }}>
            {steps.map((s, i) => (
              <div key={s.id || i} className="card">
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <h3>{s.label || (s.type === "bloom" ? "Bloom" : `Pour ${i}`)}</h3>
                  <small className="form-label">Ends at <b>{s.water_to ?? "—"}</b> g</small>
                </div>
                <div className="grid-2col">
                  <KV k="Style" v={s.pour_style || (s.type === "bloom" ? "center" : "spiral")} />
                  <KV
                    k="Kettle temp"
                    v={typeof s.kettle_temp_c === "number" ? `${s.kettle_temp_c} °C` : "—"}
                  />
                </div>
                <div className="grid-2col">
                  <KV k="Plan start" v={s.plan_start || "—"} />
                  <KV k="Plan end" v={s.plan_end || "—"} />
                </div>
                {s.note ? (
                  <div className="form-label" style={{ marginTop: 6, opacity: 0.9 }}>
                    <b>Comment:</b> {s.note}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        ) : (
          <div className="form-label">No step snapshot.</div>
        )}
      </section>

      {/* Timeline */}
      <section className="card">
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
          <h2>Timeline</h2>
          <small className="form-label">Orange = Bloom, Blue = Pours, Gray = Drawdown</small>
        </div>

        {summary?.timeline?.length ? (
          <div
            className="timeline-shell"
            style={{
              border: "1px solid #242731",
              borderRadius: 10,
              background: "#0f1114",
              padding: 8,
              overflow: "hidden",
              marginTop: 8,
            }}
          >
            <div
              style={{
                position: "relative",
                height: 64,
                width: "100%",
                borderRadius: 8,
                background:
                  "repeating-linear-gradient(90deg, rgba(255,255,255,0.04) 0, rgba(255,255,255,0.04) 1px, transparent 1px, transparent 40px)",
              }}
            >
              {summary.timeline.map((s, idx) => {
                const left = Math.max(0, Math.min(100, (s.start_ms / windowMs) * 100));
                const width = Math.max(0.5, Math.min(100, ((s.end_ms - s.start_ms) / windowMs) * 100));
                const title = [
                  s.label || s.type,
                  `${msToMMSS(s.end_ms - s.start_ms)}`,
                  s.cum_g != null ? `• ${s.cum_g}g` : "",
                  s.style ? `• ${s.style}` : "",
                  s.note ? `• ${s.note}` : "",
                ]
                  .filter(Boolean)
                  .join(" ");
                return (
                  <div
                    key={idx}
                    title={title}
                    style={{
                      position: "absolute",
                      left: `${left}%`,
                      top: 18,
                      height: 28,
                      width: `${width}%`,
                      background: segColor(s.type),
                      borderRadius: 6,
                    }}
                  />
                );
              })}
            </div>
            <div
              className="row"
              style={{ justifyContent: "space-between", opacity: 0.7, fontSize: 12, marginTop: 4 }}
            >
              <span>0:00</span>
              <span>{msToMMSS(windowMs)}</span>
            </div>
          </div>
        ) : (
          <div className="form-label">No timeline recorded.</div>
        )}
      </section>

      {/* Cup assessment */}
      <section className="card">
        <h2>Cup assessment</h2>
        {feedback ? (
          <div className="grid-2col" style={{ gap: 12, marginTop: 4 }}>
            {/* LEFT: aligned rows (label | value | comment) */}
            <div className="card col assess-grid">
              {[
                ["Acidity",     feedback.acidity,     feedback.trait_comments?.acidity],
                ["Sweetness",   feedback.sweetness,   feedback.trait_comments?.sweetness],
                ["Bitterness",  feedback.bitterness,  feedback.trait_comments?.bitterness],
                ["Body",        feedback.body,        feedback.trait_comments?.body],
                ["Clarity",     feedback.clarity,     feedback.trait_comments?.clarity],
              ].map(([label, val, c], i) => (
                <div key={i} className="assess-row">
                  <div className="assess-label form-label">{label as string}</div>
                  <div className="assess-val">
                    {Number.isFinite(val as number) ? (val as number).toFixed(1) : "—"}
                  </div>
                  <div className="assess-cmt">
                    <span className="form-label">
                      {(c as string)?.trim() || "—"}
                    </span>
                  </div>
                </div>
              ))}
            </div>

            {/* RIGHT: Overall (stars) + overall comment + notes chips */}
            <div className="card col" style={{ gap: 12 }}>
              <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
                <h3>Overall</h3>
                <div className="row" style={{ gap: 8 }}>
                  <Stars value={feedback.overall_rating} />
                  <span className="form-label">
                    {Number.isFinite(feedback.overall_rating) ? feedback.overall_rating.toFixed(1) : "—"}
                  </span>
                </div>
              </div>

              {/* overall comments */}
              <div>
                <div className="form-label" style={{ marginBottom: 4 }}><b>Comment:</b></div>
                <div style={{ whiteSpace: "pre-wrap"}}>
                  <span className="form-label">
                    {feedback.comments?.trim() ? feedback.comments : "—"}
                  </span>
                </div>
              </div>

              {/* notes chips */}
              <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
                {(Array.isArray(feedback.notes) ? feedback.notes : []).map((n: string, i: number) => (
                  <span
                    key={i}
                    className="form-label"
                    style={{
                      padding: "4px 8px",
                      border: "1px solid #242731",
                      borderRadius: 6,
                      background: "#0f1114",
                    }}
                  >
                    {n}
                  </span>
                ))}
                {!feedback.notes?.length && <span className="form-label" style={{ opacity: 0.75 }}>No notes</span>}
              </div>
            </div>
          </div>
        ) : (
          <div className="form-label">
            No assessment yet.
            <button
              className="btn secondary"
              style={{ marginLeft: 8 }}
              onClick={() => nav("/brew/assess", { state: { session_id: sessionId } })}
            >
              Add assessment
            </button>
          </div>
        )}
      </section>

        {/* Suggestion Result (only for suggested sessions) */}
        {brewType === "suggested" && (
          <section className="card">
            <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
              <h2>Suggestion result</h2>
              {typeof suggestFB.rating === "number" && (
                <div className="row" style={{ gap: 8 }}>
                  <Stars value={suggestFB.rating} />
                  <span className="form-label">{suggestFB.rating.toFixed(1)}/5</span>
                </div>
              )}
            </div>

            {suggestFB.comment && (
              <p className="form-label" style={{ marginTop: 6 }}>“{suggestFB.comment}”</p>
            )}

            {goalsList?.length ? (
              <div className="row" style={{ gap: 6, flexWrap: "wrap", marginTop: 8 }}>
                {goalsList.map((g: any, i: number) => (
                  <span key={i} className="pill">
                    {(g?.direction === "reduce" ? "↓" : "↑")} {g?.trait || g?.raw || "goal"}
                  </span>
                ))}
              </div>
            ) : (
              <div className="form-label" style={{ marginTop: 6 }}>No goals captured.</div>
            )}
          </section>
        )}

        {/* Actions */}
        <section className="row" style={{ gap: 8 }}>
          <button className="btn" onClick={() => nav("/brew/suggest/preview", { state: makeRebrewState() })}>
            Brew again
          </button>
          <button className="btn secondary" onClick={() => nav("/brew/suggest", { state: makeAdjustState() })}>
            Adjust &amp; brew (goal-based)
          </button>
        </section>

      {/* Debug drawers */}
      <details style={{ marginTop: 16, opacity: 0.8 }}>
        <summary>debug: local entry</summary>
        <pre style={{ margin: 0, padding: 12, background: "#0f1114", borderRadius: 8, overflow: "auto" }}>
          {JSON.stringify(local, null, 2)}
        </pre>
      </details>
      <details style={{ marginTop: 8, opacity: 0.8 }}>
        <summary>debug: server doc</summary>
        <pre style={{ margin: 0, padding: 12, background: "#0f1114", borderRadius: 8, overflow: "auto" }}>
          {JSON.stringify(serverDoc, null, 2)}
        </pre>
      </details>
    </main>
  );

}

/* small key/value row */
function KV({ k, v }: { k: string; v?: React.ReactNode }) {
  return (
    <div className="row" style={{ gap: 8, fontSize: 14 }}>
      <span className="form-label" style={{ width: 130 }}>
        {k}
      </span>
      <span>{v ?? "—"}</span>
    </div>
  );
}
