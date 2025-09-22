// src/pages/Brew/Suggest/Guide.tsx
import React, { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { API } from "@api";
import useProfile from "@hooks/useProfile";
import useRoundPref from "@hooks/useRoundPref";
import useBrewSession from "@hooks/useBrewSession";
import FloatingMic from "@components/FloatingMic";
import useBrewHistory from "@hooks/useBrewHistory";
/* --------------------------------- types --------------------------------- */
type Step = {
  id?: string;
  label?: string;               // "Bloom" or "Pour N"
  water_to?: number;            // absolute target (g) after this step
  pour_style?: "center" | "spiral" | "pulse";
  note?: string;
  type?: "bloom" | "pour";
};

type Recipe = {
  brew_name?: string;
  dose?: number;
  ratio?: string | number;
  total_water?: number;
  temperature_c?: number;
  grind_text?:string;
  steps?: Step[];
};

type NavState = {
  recipe?: Recipe;
  bean_id?: string;
  bean?: any;
  brew_name?: string;
  mode?: "manual" | "suggested";
  source?: string;
  reference_session_id?: string;
  gear?: any;
  goals?: any[];
};

// reasonable defaults if no times came from Preview
const TIMING = { BLOOM_S: 30, POUR_S: 20, DRAWDOWN_MAX_S: 30 };

function mmss(total: number) {
  const m = Math.floor(total / 60);
  const s = Math.round(total % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

function addPlanTimes(recipe: any) {
  const r = { ...(recipe || {}), steps: [...(recipe?.steps || [])] };
  const isBloom = (s: any) => (s.label || "").toLowerCase().includes("bloom");
  const bloomIdx = r.steps.findIndex(isBloom);
  const bloom = bloomIdx >= 0 ? r.steps[bloomIdx] : null;
  const pours = r.steps.filter((s: any) => !isBloom(s))
    .sort((a: any, b: any) => (a.water_to ?? 0) - (b.water_to ?? 0));
  const ordered = bloom ? [bloom, ...pours] : pours;

  let t = 0;
  for (const s of ordered) {
    const has = typeof s.plan_start_s === "number" && typeof s.plan_end_s === "number";
    if (!has) {
      const dur = isBloom(s) ? TIMING.BLOOM_S : TIMING.POUR_S;
      s.plan_start_s = t;
      s.plan_end_s = t + dur;
      t += dur;
    } else {
      t = Math.max(t, s.plan_end_s);
    }
  }
  (r as any).__plan_drawdown = { start_s: t, end_s: t + TIMING.DRAWDOWN_MAX_S };
  return r;
}

function buildTimeline(recipeWithPlan: any) {
  const segs: Array<{ type: "bloom" | "pour" | "drawdown"; start_s: number; end_s: number; label: string }> = [];
  for (const s of recipeWithPlan?.steps || []) {
    const type = (s.label || "").toLowerCase().includes("bloom") ? "bloom" : "pour";
    segs.push({
      type,
      start_s: s.plan_start_s ?? 0,
      end_s: s.plan_end_s ?? (type === "bloom" ? TIMING.BLOOM_S : TIMING.POUR_S),
      label: s.label || (type === "bloom" ? "Bloom" : "Pour"),
    });
  }
  if (recipeWithPlan?.__plan_drawdown) {
    const d = recipeWithPlan.__plan_drawdown;
    segs.push({ type: "drawdown", start_s: d.start_s, end_s: d.end_s, label: "Drawdown" });
  }
  const total_s = segs.length ? Math.max(...segs.map(s => s.end_s)) : TIMING.BLOOM_S + TIMING.DRAWDOWN_MAX_S;
  return { segs, total_s };
}

/* ------------------------------ STT (minimal) ---------------------------- */
function useSpeechControls(opts: {
  enabled: boolean;
  onCommand: (cmd: "start" | "next" | "back" | "end" | "pause" | "resume") => void;
}) {
  const { enabled, onCommand } = opts;
  const recRef = useRef<any>(null);
  const [supported] = useState(
    typeof window !== "undefined" &&
      (("SpeechRecognition" in window) || ("webkitSpeechRecognition" in window))
  );
  const [listening, setListening] = useState(false);

  useEffect(() => {
    if (!supported || !enabled) return;
    const SR: any = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const rec = new SR();
    rec.lang = "en-US";
    rec.continuous = true;
    rec.interimResults = false;
    rec.onresult = (e: any) => {
      const text = (e.results[e.results.length - 1][0].transcript || "").trim().toLowerCase();
      // simple contains matching
      if (text.includes("start")) onCommand("start");
      else if (text.includes("next")) onCommand("next");
      else if (text.includes("back")) onCommand("back");
      else if (text.includes("finish") || text.includes("end") || text.includes("done")) onCommand("end");
      else if (text.includes("pause")) onCommand("pause");
      else if (text.includes("resume") || text.includes("continue")) onCommand("resume");
    };
    rec.onerror = () => {}; // soft-fail
    rec.onend = () => setListening(false);
    recRef.current = rec;
    return () => {
      try { rec.stop(); } catch {}
      recRef.current = null;
    };
  }, [enabled, onCommand, supported]);

  const start = () => {
    if (!supported || !enabled || listening) return;
    try {
      recRef.current?.start();
      setListening(true);
    } catch {}
  };
  const stop = () => {
    if (!listening) return;
    try {
      recRef.current?.stop();
    } catch {}
    setListening(false);
  };

  return { supported, listening, start, stop };
}

/* --------------------------------- TTS ----------------------------------- */
function speak(text: string) {
  try {
    const u = new SpeechSynthesisUtterance(text);
    window.speechSynthesis.speak(u);
  } catch {}
}

/* --------------------------------- page ---------------------------------- */
export default function Guide() {
  const nav = useNavigate();
  const loc = useLocation();
  const { recipe: incoming, bean, brew_name: nameOverride, mode, source, reference_session_id, gear, goals } =
  (loc.state || {}) as NavState;
    
  // prefs → roundG
  const { prefs } = useRoundPref();
  const roundG = useMemo(() => {
    const step = Math.max(0.01, Number(prefs.gramStep ?? 1));
    return (v: number) => Math.round(Number(v) / step) * step;
  }, [prefs.gramStep]);

  // user/session hooks
  const { data: profile } = useProfile();
  const { current, start, finish: finishSession } = useBrewSession();
  const { patch } = useBrewHistory() as any; // NEW
  const [serverSessionId, setServerSessionId] = useState<string | null>(null);

  // normalize recipe & steps (ensure Bloom first)
  const recipe: Recipe = useMemo(() => {
    const r = incoming || {};
    let steps = Array.isArray(r.steps) ? [...r.steps] : [];
    if (steps.length === 0) {
      steps = [
        { id: "bloom", label: "Bloom", water_to: 30, type: "bloom", pour_style: "center" },
        { id: "pour_1", label: "Pour 1", water_to: r.total_water || 225, type: "pour", pour_style: "spiral" },
      ];
    }
    steps = steps.map((s, i) => {
      const isBloom = s.type === "bloom" || (s.label || "").toLowerCase().includes("bloom") || i === 0;
      return { ...s, type: isBloom ? "bloom" : "pour" };
    });
    return {
      brew_name: r.brew_name || nameOverride || "Suggested brew",
      dose: r.dose,
      ratio: r.ratio as any,
      total_water: r.total_water,
      temperature_c: r.temperature_c ?? 96,
      grind_text: (r as any)?.grind_text,
      steps,
    };
  }, [incoming, nameOverride]);

  // stage index
  const [idx, setIdx] = useState(0);

  // timer / preroll
  const [preroll, setPreroll] = useState(0); // 0 idle, else 3..1
  const [running, setRunning] = useState(false);
  const [paused, setPaused] = useState(false);
  const [elapsedMs, setElapsedMs] = useState(0);
  const startRef = useRef<number | null>(null);
  const tickRef = useRef<number | null>(null);
  const prerollRef = useRef<number | null>(null);

  // planned steps + timeline (time-based)
  const planned = useMemo(() => addPlanTimes(recipe), [recipe]);
  const steps = planned?.steps || [];
  const active = steps[idx] || {};
  const timeline = useMemo(() => buildTimeline(planned), [planned]);

  // derived seconds for the moving needle
  const elapsedSec = Math.max(0, elapsedMs / 1000);

  // UX toggles
  const [showHelp, setShowHelp] = useState(false);
  const [sttOn, setSttOn] = useState(false);
  const [ttsOn, setTtsOn] = useState(false);

  // STT
  const { supported: sttSupported, listening, start: sttStart, stop: sttStop } = useSpeechControls({
    enabled: sttOn,
    onCommand: (cmd) => {
      if (cmd === "start") onStart();
      else if (cmd === "next") onNext();
      else if (cmd === "back") onBack();
      else if (cmd === "pause") setPaused(true);
      else if (cmd === "resume") setPaused(false);
      else if (cmd === "end") onFinish();
    },
  });

  // start local session on mount and try server session (best-effort)
  useEffect(() => {
    let cancelled = false;

    // ensure we have a local session (tolerant payload; type-loose)
    if (!current?.id) {
      start({
        status: "brewing",
        recipe: { ...recipe },
        settings: {
          doseGrams: recipe.dose,
          ratio: recipe.ratio,
          totalWater: recipe.total_water,
          waterTempC: recipe.temperature_c,
        },
        summary: { brew_name: recipe.brew_name },
        meta: {
          mode: mode ?? "suggested",
          source: source ?? "ui",
          goals,                                 // ✅ keep goals locally
          recipe_snapshot: { ...recipe, bean, gear }, // ✅ ensure Summary has steps/bean/gear
        },
      } as any);
    }

    // best-effort server start (do not block UI)
    (async () => {
      try {
        const res = await API.startSession({
          user_id: profile?.userId || "default-user",
          mode: mode ?? "suggested",
          source: source ?? "ui",
          bean,
          gear,                        // optional, sent if provided
          goals,                       // optional, sent if provided
          reference_session_id,        // optional, for Adjust & Brew lineage
          recipe: {
            brew_name: recipe.brew_name,
            dose_g: recipe.dose,
            ratio: recipe.ratio,
            water_g: recipe.total_water,
            temperature_c: recipe.temperature_c,
            grind_text: recipe.grind_text,    // ✅ persist grind so Summary shows it
            steps: recipe.steps?.map((s) => ({
              type: s.type,
              label: s.label,
              water_to_g: s.water_to,
              pour_style: s.pour_style,
              note: s.note,
            })),
          },
        });
        if (!cancelled) setServerSessionId(res?.session_id ?? null);
      } catch {
        // offline allowed
      }
    })();

    return () => {
      cancelled = true;
      stopTimers();
      sttStop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // mount once

  function stopTimers() {
    if (tickRef.current) {
      window.clearInterval(tickRef.current);
      tickRef.current = null;
    }
    if (prerollRef.current) {
      window.clearInterval(prerollRef.current);
      prerollRef.current = null;
    }
  }

  const onStart = () => {
    if (running || preroll > 0) return;
    setPreroll(3);
    prerollRef.current = window.setInterval(() => {
      setPreroll((p) => {
        if (p <= 1) {
          window.clearInterval(prerollRef.current!);
          prerollRef.current = null;
          startRef.current = Date.now();
          setRunning(true);
          setPaused(false);
          tickRef.current = window.setInterval(() => {
            if (startRef.current != null && !paused) {
              setElapsedMs(Date.now() - startRef.current);
            }
          }, 200) as unknown as number;
          // speak first step on start
          if (ttsOn) speakStep(idx);
          return 0;
        }
        return p - 1;
      });
    }, 1000) as unknown as number;
  };

  const onPauseToggle = () => setPaused((p) => !p);

  // speak current step
  function speakStep(i: number) {
    const s = planned.steps?.[i];
    if (!s) return;
    const label = s.label || (s.type === "bloom" ? "Bloom" : `Pour ${i}`);
    const tgt = s.water_to != null ? `${roundG(s.water_to)} grams` : "";
    const style = s.pour_style ? `${s.pour_style} pour` : "";
    const temp = typeof recipe.temperature_c === "number" ? `${Math.round(recipe.temperature_c)} degrees` : "";
    const msg = [label, tgt && `to ${tgt}`, style, temp].filter(Boolean).join(", ");
    speak(msg);
  }

  // step nav helpers
  const atFirst = idx <= 0;
  const atLast = idx >= ((recipe.steps?.length || 1) - 1);

  const onBack = () => {
    if (atFirst) return;
    setIdx((i) => {
      const nextI = Math.max(0, i - 1);
      if (ttsOn) speakStep(nextI);
      return nextI;
    });
  };

  const onNext = async () => {
    if (atLast || !running || paused) return;
    await markCurrentDone(false);
    setIdx((i) => {
      const nextI = Math.min((recipe.steps?.length || 1) - 1, i + 1);
      if (ttsOn) speakStep(nextI);
      return nextI;
    });
  };

  // send a step to server (called when user marks done or onNext)
  async function markCurrentDone(isExplicitButton: boolean) {
    if (!running || paused) return;
    const step = recipe.steps?.[idx];
    if (!step) return;

    // post step if we have a real server session (skip if offline)
    if (serverSessionId && !String(serverSessionId).startsWith("local-")) {
      try {
        // Canonical payload:
        //  - Bloom: { type:"bloom", water_g, at_ms, style }
        //  - Pour:  { type:"pour",  target_g, at_ms, style }
        await API.step({
          session_id: serverSessionId!,
          step:
            (step.type || "pour") === "bloom"
              ? {
                  type: "bloom",
                  water_g: step.water_to != null ? roundG(Number(step.water_to)) : undefined,
                  at_ms: Date.now(),
                  style: step.pour_style || "center",
                }
              : {
                  type: "pour",
                  target_g: step.water_to != null ? roundG(Number(step.water_to)) : undefined,
                  at_ms: Date.now(),
                  style: step.pour_style || "spiral",
                },
        });
      } catch {
        // ignore; user can still finish offline
      }
    }

    // If user pressed the explicit “Mark step done” on the last card, we still won't auto-finish;
    // they must press Finish (per spec). No-op here besides the API call.
    if (isExplicitButton) return;
  }

  async function onFinish() {
    stopTimers();
    setRunning(false);
    setPaused(false);

    // Local finish → pushes to history via hook and clears current
    const localId = current?.id || null;
    finishSession({
      duration_ms: elapsedMs,
      brew_name: recipe.brew_name,
    } as any);

    // Go collect rating; pass the **server** session id (fallback to local if needed)
    const ensuredId = serverSessionId || localId || null; // prefer server when available
    if ((mode ?? "suggested") === "manual") {
      // Brew again flow → skip Rate
      nav("/brew/assess", { state: { session_id: ensuredId, brew_name: recipe.brew_name } });
    } else {
      // Standard / Adjust & Brew → ask for rating
      nav("/brew/suggest/rate", { state: { session_id: ensuredId, brew_name: recipe.brew_name } });
    }
  }

   const total = recipe.total_water;
  const elapsedS = Math.max(0, Math.round(elapsedMs / 100) / 10).toFixed(1);


/* --------------------------------- UI ---------------------------------- */
  return (
    <main className="max-w-3xl mx-auto p-4">
      {/* Header (dark, Log-like) */}
      <section className="rounded-xl border border-white/10 bg-neutral-900/70 backdrop-blur px-4 py-3 mb-4 shadow">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h1 className="text-xl sm:text-2xl font-semibold">
              {recipe.brew_name || "Suggested brew"}
            </h1>

            <div className="mt-2 grid grid-cols-2 sm:grid-cols-5 gap-2 text-sm">
              <div>💧 Water: <b>{total ?? "—"}</b> g</div>
              <div>⚖️ Dose: <b>{recipe.dose ?? "—"}</b> g</div>
              <div>📐 Ratio: <b>{recipe.ratio ?? "—"}</b></div>
              <div>🌡️ Temp: <b>{recipe.temperature_c ?? "—"}</b> °C</div>
              <div>🪵 Grind: <b>{recipe.grind_text || "—"}</b></div>
            </div>

            <div className="text-xs sm:text-sm mt-2 opacity-80">
              Timer: {elapsedS}s {paused && running ? <em>(paused)</em> : null}
            </div>
          </div>

          <div className="flex flex-col items-end gap-2">
            <div className="flex gap-2">
              {!running && preroll === 0 && (
                <button className="px-3 py-2 rounded-md bg-blue-600 text-white" onClick={onStart}>
                  Start
                </button>
              )}
              {!running && preroll > 0 && (
                <div className="px-3 py-2 rounded-md border">Starting… {preroll}</div>
              )}
              {running && (
                <button className="px-3 py-2 rounded-md border" onClick={onPauseToggle}>
                  {paused ? "Resume" : "Pause"}
                </button>
              )}
            </div>

            <div className="flex gap-2">
              <button
                className="px-2 py-1 rounded-md border text-sm"
                onClick={() => setShowHelp((v) => !v)}
                title="Voice commands"
              >
                ?
              </button>
              <button
                className={`px-2 py-1 rounded-md text-sm ${ttsOn ? "bg-neutral-800 text-white" : "border"}`}
                onClick={() => setTtsOn((v) => !v)}
                title="Read steps aloud"
              >
                🔊 TTS
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Single active step card */}
      <section className="mx-auto max-w-xl rounded-xl border border-white/10 bg-neutral-900 p-4 shadow mb-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold">
            {active?.label || (active?.type === "bloom" ? "Bloom" : `Pour ${idx}`)}
          </h2>
          <div className="text-sm opacity-70">
            Step {idx + 1} / {recipe.steps?.length || 1}
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Field label="Target to (g)" value={active?.water_to != null ? `${roundG(active?.water_to)}` : "—"} />
          <Field label="Pour style" value={active?.pour_style || (active?.type === "bloom" ? "center" : "spiral")} />
          <Field label="Temperature" value={`${recipe.temperature_c ?? 96} °C`} />
          <Field label="Time" value={`${mmss(active?.plan_start_s ?? 0)} – ${mmss(active?.plan_end_s ?? 0)}`} />
        </div>

        {active?.note ? (
          <div className="mt-3 text-sm opacity-80">
            <b>Note:</b> {active.note}
          </div>
        ) : null}

        <div className="mt-4 flex items-center justify-between">
          <div className="flex gap-2">
            <button
              className="px-4 py-2 rounded-md border disabled:opacity-50"
              onClick={onBack}
              disabled={atFirst}
            >
              ← Back
            </button>

            {!atLast ? (
              <button
                className="px-4 py-2 rounded-md bg-blue-600 text-white disabled:opacity-50"
                disabled={!running || paused}
                onClick={onNext}
              >
                Next →
              </button>
            ) : (
              <button className="px-4 py-2 rounded-md bg-blue-600 text-white" onClick={onFinish}>
                Finish
              </button>
            )}
          </div>
        </div>
      </section>

      {/* Timeline (time-based, with playhead) */}
      <section className="rounded-xl border border-white/10 bg-neutral-900 p-4 mb-16">
        <div className="flex items-center justify-between mb-2">
          <h2 className="font-semibold">Timeline</h2>
          <span className="text-xs opacity-70">Orange = Bloom, Blue = Pours, Gray = Drawdown</span>
        </div>

        <div className="relative">
          <div className="flex h-4 rounded-md overflow-hidden border border-white/10 bg-neutral-800">
            {timeline.segs.map((seg, i) => {
              const widthPct = ((seg.end_s - seg.start_s) / (timeline.total_s || 1)) * 100;
              const bg = seg.type === "bloom" ? "#ff9f43" : seg.type === "pour" ? "#3a86ff" : "#9aa0a6";
              return (
                <div
                  key={i}
                  title={`${seg.label}: ${mmss(seg.start_s)}–${mmss(seg.end_s)}`}
                  style={{ width: `${widthPct}%`, background: bg, opacity: idx === i ? 1 : 0.85 }}
                />
              );
            })}
          </div>

          {/* faint grid */}
          <div
            className="absolute inset-0 pointer-events-none rounded-md"
            style={{
              backgroundImage: "linear-gradient(to right, rgba(255,255,255,.06) 1px, transparent 1px)",
              backgroundSize: `${100 / Math.max(1, Math.ceil((timeline.total_s || 1) / 10))}% 100%`,
            }}
          />

          {/* playhead */}
          <div
            className="absolute top-0 bottom-0"
            style={{
              left: `${Math.max(0, Math.min(100, (elapsedSec / (timeline.total_s || 1)) * 100))}%`,
              width: 2,
              background: "#fff",
              boxShadow: "0 0 6px rgba(255,255,255,.6)",
              transform: "translateX(-1px)",
            }}
          />
        </div>

        <div className="flex justify-between text-xs opacity-70 mt-2">
          <span>0:00</span>
          <span>{mmss(timeline.total_s)}</span>
        </div>
      </section>

      {/* Dictate pill (same component as Log) */}
      <FloatingMic
        onFinal={(utt: any) => {
          const t = String(utt || "").toLowerCase();
          if (!t) return;
          if (t.includes("start")) onStart();
          else if (t.includes("pause")) setPaused(true);
          else if (t.includes("resume") || t.includes("continue")) setPaused(false);
          else if (t.includes("next")) onNext();
          else if (t.includes("back")) onBack();
          else if (t.includes("finish") || t.includes("end") || t.includes("done")) onFinish();
        }}
      />

      {/* Help popover */}
      {showHelp && (
        <div className="mt-3 rounded-lg border border-white/10 p-3 bg-neutral-900 text-sm">
          <div className="font-medium mb-1">Voice commands</div>
          <ul className="list-disc ml-5 space-y-1 opacity-80">
            <li><b>start</b> — countdown then start the timer</li>
            <li><b>next</b> — go to next phase</li>
            <li><b>back</b> — go to previous phase</li>
            <li><b>pause</b> / <b>resume</b> — control timer</li>
            <li><b>end</b> / <b>finish</b> — finish and go to rating</li>
          </ul>
        </div>
      )}
    </main>
  );

  /* Field: non-editable, dark style */
  function Field({ label, value }: { label: string; value: React.ReactNode }) {
    return (
      <label className="text-sm">
        <div className="opacity-60 mb-1">{label}</div>
        <div className="px-3 py-2 rounded-lg bg-neutral-800 border border-white/10">{value}</div>
      </label>
    );
  }


}


