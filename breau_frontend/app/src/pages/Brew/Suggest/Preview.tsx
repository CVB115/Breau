// src/pages/Brew/Suggest/Preview.tsx
import React, { useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import useRoundPref from "@hooks/useRoundPref"; // default export hook

type Step = {
  id?: string;
  label?: string;   // "Bloom", "Pour 1", ...
  water_to?: number;
  plan_start_s?: number;
  plan_end_s?: number;
};

type Recipe = {
  brew_name?: string;
  dose?: number;
  ratio?: string;          // "1:15" or "15"
  total_water?: number;
  temperature_c?: number;
  bloom_water?: number;

  // Grind (display-normalized)
  grind_text?: string;     // e.g., "22 clicks" or "Medium-fine"
  grind_micron?: number;   // e.g., 620
  grind_unit?: string;     // default "µm"

  steps?: Step[];
  [k: string]: any;
};

type Bean = { id?: string; name?: string; roaster?: string } | null;

type UpstreamNavState = {
  recipe?: Recipe;
  bean_id?: string;
  bean?: Bean;
  gear?: any;
  goals?: any[];
  source?: "summary-brew-again" | "summary-adjust" | "goals-normal" | string;
  reference_session_id?: string;
  prior_recipe?: Recipe;
  explain?: {
    summary?: string;
    changes?: Array<{ field: string; from?: any; to?: any; reason?: string }>;
  };
};

/* ------------------------------ timing utils ----------------------------- */

const TIMING = {
  BLOOM_S: 30,
  POUR_S: 20,
  DRAWDOWN_MAX_S: 30,
} as const;

function mmss(total: number) {
  const m = Math.floor(total / 60);
  const s = Math.round(total % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

function parseRatio(input: string | number | undefined): number | undefined {
  if (input == null) return undefined;
  const s = String(input).trim();
  if (!s) return undefined;
  if (s.includes(":")) {
    const parts = s.split(":");
    const a = parseFloat(parts[0] || "1");
    const b = parseFloat(parts[1] || "0");
    if (isFinite(a) && isFinite(b) && a > 0) return b / a;
    return undefined;
  }
  const n = parseFloat(s);
  return isFinite(n) && n > 0 ? n : undefined;
}

function fmtRatio(r?: number): string {
  if (r == null || !isFinite(r) || r <= 0) return "";
  const rounded = Math.round(r);
  const val = Math.abs(rounded - r) < 0.05 ? rounded : Math.round(r * 10) / 10;
  return `1:${val}`;
}

/* Build plan times if missing: bloom 30s, pours 20s, drawdown 30s cap. */
function addPlanTimes(recipe: any) {
  const r = { ...(recipe || {}), steps: [...(recipe?.steps || [])] };

  // Ensure bloom first, then pours sorted by water_to
  const bloomIdx = r.steps.findIndex(
    (s: any) => (s?.label || "").toLowerCase().includes("bloom")
  );
  const bloom = bloomIdx >= 0 ? r.steps[bloomIdx] : null;

  const pours = r.steps
    .filter((s: any) => !((s?.label || "").toLowerCase().includes("bloom")))
    .sort((a: any, b: any) => (a?.water_to ?? 0) - (b?.water_to ?? 0));

  const ordered = bloom ? [bloom, ...pours] : pours;

  let t = 0;
  for (let i = 0; i < ordered.length; i++) {
    const s = ordered[i];
    const hasTimes =
      typeof s.plan_start_s === "number" && typeof s.plan_end_s === "number";

    if (!hasTimes) {
      const isBloom = (s?.label || "").toLowerCase().includes("bloom");
      const dur = isBloom ? TIMING.BLOOM_S : TIMING.POUR_S;
      s.plan_start_s = t;
      s.plan_end_s = t + dur;
      t += dur;
    } else {
      t = Math.max(t, s.plan_end_s);
    }
  }

  const drawdownEnd = t + TIMING.DRAWDOWN_MAX_S;
  (r as any).__plan_drawdown = { start_s: t, end_s: drawdownEnd };
  return r;
}

function buildTimeline(recipeWithPlan: any) {
  const steps = recipeWithPlan?.steps || [];
  const segs: Array<{ type: "bloom" | "pour" | "drawdown"; start_s: number; end_s: number; label: string }> = [];

  for (const s of steps) {
    const label = (s?.label || "").toLowerCase();
    const type: "bloom" | "pour" = label.includes("bloom") ? "bloom" : "pour";
    segs.push({
      type,
      start_s: s.plan_start_s ?? 0,
      end_s: s.plan_end_s ?? (type === "bloom" ? TIMING.BLOOM_S : TIMING.POUR_S),
      label: s?.label || (type === "bloom" ? "Bloom" : "Pour"),
    });
  }

  if (recipeWithPlan?.__plan_drawdown) {
    const d = recipeWithPlan.__plan_drawdown;
    segs.push({ type: "drawdown", start_s: d.start_s, end_s: d.end_s, label: "Drawdown" });
  }

  const total_s =
    segs.length > 0 ? Math.max(...segs.map((s) => s.end_s)) : TIMING.BLOOM_S + TIMING.DRAWDOWN_MAX_S;

  segs.sort((a, b) => a.start_s - b.start_s);
  return { segs, total_s };
}

/* --------------------------------- view --------------------------------- */

export default function Preview() {
  const nav = useNavigate();
  const loc = useLocation();
  const {
    recipe: initialRecipe,
    bean_id,
    bean,
    gear,
    goals,
    source,
    reference_session_id,
    prior_recipe,
    explain,
  } = (loc.state || {}) as UpstreamNavState;

  const { prefs } = useRoundPref();
  const roundG = useMemo(() => {
    const step = Math.max(0.01, Number(prefs?.gramStep ?? 1));
    return (v: number) => Math.round(v / step) * step;
  }, [prefs?.gramStep]);

  const defaults: Recipe = useMemo(
    () => ({
      brew_name: "Suggested brew",
      dose: 15,
      ratio: "1:15",
      total_water: 225,
      temperature_c: 96,
      bloom_water: 30,
      steps: [
        { id: "bloom", label: "Bloom", water_to: 30 },
        { id: "pour_1", label: "Pour 1", water_to: 150 },
        { id: "pour_2", label: "Pour 2", water_to: 225 },
      ],
    }),
    []
  );

  const [edited, setEdited] = useState<Recipe>(() => {
    const base = initialRecipe && Object.keys(initialRecipe).length ? initialRecipe : defaults;
    const r = parseRatio(base.ratio ?? "");

    // ---- normalize grind (handles nested recipe.grind object) ----
    const g = (base as any).grind;
    let normGrind: any = {
      grind_text:
        base.grind_text ??
        base.grindLabel ??
        base.grind_label ??
        base.grind_setting ??
        base.grindSetting ??
        base.grind_notes ??
        undefined,
      grind_micron:
        base.grind_micron ??
        base.grind_um ??
        base.micron ??
        base.grindMicron ??
        undefined,
      grind_unit: base.grind_unit ?? base.grindUnit ?? "µm",
    };

    if (g && typeof g === "object") {
      const clicks =
        g.scale === "clicks" && g.value != null ? `${g.value} clicks` : undefined;
      normGrind = {
        ...normGrind,
        grind_text: clicks ?? g.label ?? normGrind.grind_text,
        grind_micron: g.approx_microns ?? normGrind.grind_micron,
      };
    }

    return {
      ...base,
      ...normGrind,
      ratio: fmtRatio(r ?? 15),
      steps: Array.isArray(base.steps) && base.steps.length ? base.steps : defaults.steps,
    };
  });

  const recipeWithPlan = useMemo(() => addPlanTimes(edited), [edited]);
  const previewTimeline = useMemo(() => buildTimeline(recipeWithPlan), [recipeWithPlan]);
  const original = useMemo(() => initialRecipe || defaults, [initialRecipe, defaults]);

  const POUR_LIMIT = 5;
  const nonBloomCount = (edited.steps || []).filter(
    (s) => !((s?.label || "").toLowerCase().includes("bloom"))
  ).length;
  const atPourLimit = nonBloomCount >= POUR_LIMIT;

  function setDose(next?: number) {
    setEdited((prev) => {
      const dose = next ?? undefined;
      const r = parseRatio(prev.ratio) ?? undefined;
      const total = dose != null && r != null ? roundG(dose * r) : prev.total_water;
      return { ...prev, dose, total_water: total };
    });
  }

  function setRatioText(text: string) {
    setEdited((prev) => {
      const r = parseRatio(text);
      const dose = prev.dose ?? undefined;
      const total = dose != null && r != null ? roundG(dose * r) : prev.total_water;
      return { ...prev, ratio: text, total_water: total };
    });
  }

  function setTotalWater(next?: number) {
    setEdited((prev) => {
      const total = next ?? undefined;
      const dose = prev.dose ?? undefined;
      const r = dose != null && total != null && dose > 0 ? total / dose : undefined;
      return { ...prev, total_water: total, ratio: fmtRatio(r) };
    });
  }

  function setBloomWater(next?: number) {
    setEdited((prev) => {
      const steps = [...(prev.steps || [])];
      const bloomIdx = steps.findIndex((s) => (s?.label || "").toLowerCase().includes("bloom"));
      if (bloomIdx >= 0) steps[bloomIdx] = { ...(steps[bloomIdx] || {}), water_to: next ?? undefined };
      return { ...prev, bloom_water: next ?? undefined, steps };
    });
  }

  function setStepWater(i: number, next?: number) {
    setEdited((prev) => {
      const steps = [...(prev.steps || [])];
      steps[i] = { ...(steps[i] || {}), water_to: next ?? undefined };
      return { ...prev, steps };
    });
  }

  function resetToSuggested() {
    const r = parseRatio(original.ratio ?? "");
    setEdited({
      ...original,
      ratio: fmtRatio(r ?? 15),
      steps: Array.isArray(original.steps) && original.steps.length ? original.steps : defaults.steps,
    });
  }

  function startBrew() {
    const isRebrew = source === "summary-brew-again"; // manual path
    nav("/brew/suggest/guide", {
      state: {
        mode: isRebrew ? "manual" : "suggested",
        recipe: recipeWithPlan,
        bean_id, bean, gear,
        goals: Array.isArray(goals) ? goals : undefined,
        reference_session_id,
        prior_recipe,
        brew_name: edited.brew_name || "Suggested brew",
        source: source || "preview",
      },
    });
  }

  return (
    <main className="page">
      {/* Header */}
      <section className="card">
        <header className="row items-center justify-between">
          <div className="col" style={{ gap: 6 }}>
            <h1>Preview &amp; tweak</h1>
            {bean?.name && (
              <div className="form-label">
                {bean.name}{bean?.roaster ? ` · ${bean.roaster}` : ""}
              </div>
            )}

            {/* stat pills, compact like Log */}
            <div className="row" style={{ flexWrap: "wrap", gap: 8, fontSize: 12, opacity: .9 }}>
              <span className="pill">Suggested</span>
              <span className="pill">{edited.brew_name || "Suggested brew"}</span>
              <span className="pill">Dose: {edited.dose ?? "—"} g</span>
              <span className="pill">Total: {edited.total_water ?? "—"} g</span>
              <span className="pill">
                Ratio: {
                  edited.ratio ||
                  (edited.total_water != null && edited.dose
                    ? `1:${Math.round((edited.total_water / (edited.dose || 1)) * 10) / 10}`
                    : "—")
                }
              </span>
              <span className="pill">Temp: {edited.temperature_c ?? "—"}°C</span>
              <span className="pill">
                Grind: {
                  typeof edited.grind_text === "string" && edited.grind_text
                    ? (edited.grind_micron
                        ? `${edited.grind_text} • ${edited.grind_micron}${edited.grind_unit || "µm"}`
                        : edited.grind_text)
                    : (
                        (gear?.grinder?.model || gear?.grinder?.name || gear?.grinder_model ||
                          (typeof gear?.grinder === "string" ? gear.grinder : "")) || "—"
                      )
                }
              </span>
            </div>
          </div>

          <div className="row" style={{ gap: 8 }}>
            <button className="btn secondary" onClick={resetToSuggested}>Reset to suggested</button>
            <button className="btn" onClick={startBrew}>Start Brew</button>
          </div>
        </header>
      </section>

      {/* Transparency */}
      {explain && (explain.summary || (explain.changes && explain.changes.length > 0)) && (
        <section className="card">
          <h2>Why these changes?</h2>
          {explain.summary && <p className="form-label" style={{ marginTop: 6 }}>{explain.summary}</p>}
          {Array.isArray(explain.changes) && explain.changes.length > 0 && (
            <ul className="list-disc" style={{ paddingLeft: 18, marginTop: 6 }}>
              {explain.changes.map((c, i) => (
                <li key={i} className="form-label">
                  <b>{c.field}</b>: {String(c.from ?? "—")} → {String(c.to ?? "—")}
                  {c.reason ? ` — ${c.reason}` : ""}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {/* Topline trio */}
      <section className="card">
        <h2>Topline</h2>
        <div className="row" style={{ gap: 12, marginTop: 8 }}>
          <div className="col"><FieldNumber label="Dose (g)" value={edited.dose} onChange={setDose} /></div>
          <div className="col"><FieldText label="Ratio (1:n or n)" value={edited.ratio || ""} onChange={setRatioText} help='Accepts “1:15” or just “15”' /></div>
          <div className="col"><FieldNumber label="Total water (g)" value={edited.total_water} onChange={setTotalWater} /></div>
          <div className="col"><FieldNumber label="Temperature (°C)" value={edited.temperature_c} onChange={(v) => setEdited({ ...edited, temperature_c: v ?? undefined })} /></div>
          <div className="col">
            <FieldText
              label="Grind (free text)"
              value={edited.grind_text || ""}
              onChange={(v) => setEdited(prev => ({ ...prev, grind_text: v || undefined }))}
            />
          </div>
        </div>
        <p className="form-label" style={{ marginTop: 8 }}>
          Changing <b>Dose</b> or <b>Ratio</b> recalculates <b>Total water</b>. Changing <b>Total</b> recalculates <b>Ratio</b>.
        </p>
      </section>

      {/* Timeline */}
      <section className="card">
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
          <h2>Timeline</h2>
          <span className="form-label" style={{ opacity: .8, fontSize: 12 }}>
            Orange = Bloom, Blue = Pours, Gray = Drawdown
          </span>
        </div>

        <div className="relative" style={{ marginTop: 8 }}>
          <div className="flex" style={{ height: 12, borderRadius: 6, overflow: "hidden", border: "1px solid rgba(255,255,255,.08)" }}>
            {previewTimeline.segs.map((seg, i) => {
              const widthPct = ((seg.end_s - seg.start_s) / (previewTimeline.total_s || 1)) * 100;
              const bg =
                seg.type === "bloom" ? "#ff9f43" :
                seg.type === "pour"  ? "#3a86ff" :
                                        "#9aa0a6";
              return (
                <div
                  key={i}
                  title={`${seg.label}: ${mmss(seg.start_s)}–${mmss(seg.end_s)}`}
                  style={{ width: `${widthPct}%`, background: bg }}
                />
              );
            })}
          </div>

          <div
            className="absolute inset-0 pointer-events-none"
            style={{
              backgroundImage: "linear-gradient(to right, rgba(255,255,255,.06) 1px, transparent 1px)",
              backgroundSize: `${100 / Math.max(1, Math.ceil(previewTimeline.total_s / 10))}% 100%`,
              borderRadius: 6
            }}
          />
        </div>

        <div className="row" style={{ justifyContent: "space-between", marginTop: 6, fontSize: 12, opacity: .8 }}>
          <span>0:00</span>
          <span>{mmss(previewTimeline.total_s)}</span>
        </div>
      </section>

      {/* Bloom */}
      <section className="card">
        <h2>Bloom</h2>
        <div className="row" style={{ gap: 12, marginTop: 8 }}>
          <div className="col">
            <FieldNumber
              label="Bloom to (g)"
              value={
                edited.bloom_water ??
                edited.steps?.find((s) => (s?.label || "").toLowerCase().includes("bloom"))?.water_to
              }
              onChange={setBloomWater}
            />
          </div>
          <div className="col">
            <FieldText
              label="Label"
              value={edited.steps?.find((s) => (s?.label || "").toLowerCase().includes("bloom"))?.label || "Bloom"}
              onChange={(v) =>
                setEdited((prev) => {
                  const steps = [...(prev.steps || [])];
                  const idx = steps.findIndex((s) => (s?.label || "").toLowerCase().includes("bloom"));
                  if (idx >= 0) steps[idx] = { ...(steps[idx] || {}), label: v };
                  return { ...prev, steps };
                })
              }
            />
          </div>
          <div className="col">
            <FieldText
              label="Name"
              value={edited.brew_name || ""}
              onChange={(v) => setEdited({ ...edited, brew_name: v })}
            />
          </div>
        </div>
        <p className="form-label" style={{ marginTop: 8 }}>
          Ends at <b>{
            edited.bloom_water ??
            edited.steps?.find((s) => (s?.label || "").toLowerCase().includes("bloom"))?.water_to ?? 0
          } g</b>
        </p>
      </section>

      {/* Pours */}
      <section className="card">
        <h2>Pours</h2>
        <div className="col" style={{ gap: 12, marginTop: 8 }}>
          {(edited.steps || [])
            .filter((s) => !((s?.label || "").toLowerCase().includes("bloom")))
            .map((s, i) => {
              const globalIndex = (edited.steps || []).findIndex((x) => x === s);
              const prevTo = (() => {
                const all = edited.steps || [];
                const prev = all[globalIndex - 1];
                return prev?.water_to ?? (
                  edited.bloom_water ??
                  all.find((x) => (x?.label || "").toLowerCase().includes("bloom"))?.water_to ?? 0
                );
              })();
              const endsAt = s.water_to ?? 0;
              const addThisStep = Math.max(0, endsAt - prevTo);

              return (
                <div key={s.id || globalIndex} className="card" style={{ padding: 12 }}>
                  <div className="row" style={{ gap: 12, alignItems: "flex-end" }}>
                    <div className="col">
                      <FieldText
                        label="Label"
                        value={s.label || `Pour ${i + 1}`}
                        onChange={(v) => {
                          setEdited((prev) => {
                            const steps = [...(prev.steps || [])];
                            steps[globalIndex] = { ...(steps[globalIndex] || {}), label: v };
                            return { ...prev, steps };
                          });
                        }}
                      />
                    </div>

                    <div className="col">
                      <FieldNumber
                        label="Water to (g)"
                        value={s.water_to}
                        onChange={(v) => setStepWater(globalIndex, v)}
                      />
                    </div>

                    <div className="row" style={{ gap: 8, marginLeft: "auto", alignItems: "center" }}>
                      <span className="form-label">
                        Ends at <b>{endsAt} g</b>
                        {addThisStep > 0 ? <span> (this pour: +{addThisStep} g)</span> : null}
                      </span>
                      <button
                        className="btn secondary"
                        onClick={() =>
                          setEdited((prev) => {
                            const steps = [...(prev.steps || [])];
                            steps.splice(globalIndex, 1);
                            return { ...prev, steps };
                          })
                        }
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}

          <button
            className="btn secondary"
            disabled={atPourLimit}
            title={atPourLimit ? `Max ${POUR_LIMIT} pours reached` : "Add another pour"}
            onClick={() => {
              setEdited((prev) => {
                const steps = [...(prev.steps || [])];
                const poursNow = steps.filter(
                  (s) => !((s?.label || "").toLowerCase().includes("bloom"))
                ).length;
                if (poursNow >= POUR_LIMIT) return prev;
                const nextIndex = poursNow + 1;
                steps.push({
                  id: `pour_${Date.now()}`,
                  label: `Pour ${nextIndex}`,
                  water_to: prev.total_water,
                });
                return { ...prev, steps };
              });
            }}
          >
            + Add pour {nonBloomCount ? `(${nonBloomCount}/${POUR_LIMIT})` : ""}
          </button>
        </div>
      </section>
    </main>
  );
}

/* ------------------------------ field helpers --------------------------- */

function FieldNumber({
  label,
  value,
  onChange,
}: {
  label: string;
  value?: number;
  onChange: (v: number | undefined) => void;
}) {
  return (
    <label className="text-sm">
      <div className="opacity-60 mb-1">{label}</div>
      <input
        type="number"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value === "" ? undefined : Number(e.target.value))}
        className="w-full border rounded-md px-2 py-1"
      />
    </label>
  );
}

function FieldText({
  label,
  value,
  onChange,
  help,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  help?: string;
}) {
  return (
    <label className="text-sm">
      <div className="opacity-60 mb-1">{label}</div>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full border rounded-md px-2 py-1"
      />
      {help && <div className="text-xs opacity-60 mt-1">{help}</div>}
    </label>
  );
}
