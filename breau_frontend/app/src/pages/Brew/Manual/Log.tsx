// src/pages/Brew/Manual/Log.tsx
import React, { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { API } from "@api";
import useProfile from "@hooks/useProfile";
import useRoundPref from "@hooks/useRoundPref";
import useBrewSession from "@hooks/useBrewSession";
import FloatingMic from "@components/FloatingMic";
import { parseBrewCommand } from "@utils/parseBrewCommand";
import { useToast } from "@context/ToastProvider";
import useBrewHistory from "@hooks/useBrewHistory";

/* ----------------------------- helpers & types ----------------------------- */
const clamp = (n: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, n));
const isPos = (n: any) => Number.isFinite(n) && n > 0;
const toNum = (s?: string | number | null) => {
  if (typeof s === "number") return isPos(s) ? s : NaN;
  const n = s == null ? NaN : parseFloat(String(s).trim());
  return isPos(n) ? n : NaN;
};
function parseRatio(text?: string | null) {
  const m = String(text ?? "").trim().match(/^(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)$/);
  if (!m) return { ok: false, factor: NaN, pretty: String(text ?? "") };
  const a = parseFloat(m[1]);
  const b = parseFloat(m[2]);
  if (!isPos(a) || !isPos(b)) return { ok: false, factor: NaN, pretty: String(text ?? "") };
  return { ok: true, factor: b / a, pretty: `1:${Math.round(b / a)}` };
}
function mmssToMs(s: string | undefined) {
  if (!s) return NaN;
  const m = s.trim().match(/^(\d+):(\d{1,2})$/);
  if (!m) return NaN;
  const mm = parseInt(m[1], 10);
  const ss = parseInt(m[2], 10);
  if (Number.isNaN(mm) || Number.isNaN(ss)) return NaN;
  return mm * 60000 + ss * 1000;
}
function msToMMSS(ms: number) {
  const t = Math.max(0, Math.round(ms / 1000));
  const mm = Math.floor(t / 60);
  const ss = t % 60;
  return `${mm}:${String(ss).padStart(2, "0")}`;
}
// normalize free-typed input like "040", "105", "1230" → "0:40", "1:05", "12:30"
function normalizeMMSSInput(raw: string): string {
  const s = (raw || "").trim();
  // already mm:ss → pad seconds
  const colon = s.match(/^(\d{1,2}):(\d{1,2})$/);
  if (colon) {
    const mm = parseInt(colon[1], 10);
    const ss = clamp(parseInt(colon[2], 10), 0, 59);
    return `${mm}:${String(ss).padStart(2, "0")}`;
  }
  // bare mmss 3-4 digits
  const bare = s.match(/^(\d{3,4})$/);
  if (bare) {
    const rawd = bare[1];
    const mm = parseInt(rawd.slice(0, -2), 10);
    const ss = clamp(parseInt(rawd.slice(-2), 10), 0, 59);
    return `${mm}:${String(ss).padStart(2, "0")}`;
  }
  return s;
}

// pretty "1:15" style from dose/total, rounded whole-numbers
function prettyRatioFrom(dose?: number, total?: number) {
  if (!Number.isFinite(dose as any) || !Number.isFinite(total as any) || !dose || dose <= 0) return null;
  const r = total! / dose!;
  const whole = Math.round(r);
  return `1:${whole}`;
}

function setBloomPlanField(
  field: "plan_start" | "plan_end",
  raw: string,
  setBloom: React.Dispatch<React.SetStateAction<Card>>
) {
  const v = normalizeMMSSInput(raw);
  setBloom((prev) => ({ ...prev, [field]: v }));
}

function setPourPlanField(
  index: number,
  field: "plan_start" | "plan_end",
  raw: string,
  setPours: React.Dispatch<React.SetStateAction<Card[]>>
) {
  const v = normalizeMMSSInput(raw);
  setPours((prev) => {
    const next = [...prev];
    next[index] = { ...next[index], [field]: v };
    return next;
  });
}

type StepLike = {
  id: string;
  label?: string;
  type?: "bloom" | "pour";
  water_to?: number;
  pour_style?: string;
  plan_start?: string; // "0:40"
  plan_end?: string;   // "1:10"
  temperature_c?: number; // or temp_c/temp_C will be mapped below
  temp_c?: number;
  temp_C?: number;
  kettle_temp_c?: number;
  note?: string;
};

function prettyRatio(r?: string | number | null) {
  if (r == null || r === "") return undefined;
  const n = typeof r === "string" ? parseFloat(r) : Number(r);
  if (!Number.isFinite(n) || n <= 0) return undefined;
  return `1:${String(n).replace(/\.0+$/, "")}`;
}

function normalizeStepForSnapshot(s: StepLike) {
  return {
    id: s.id,
    label: s.label || (s.id === "bloom" ? "Bloom" : s.label || s.id),
    type: (s.type as any) || "pour",
    water_to: Number.isFinite(s.water_to as any) ? Number(s.water_to) : undefined,
    pour_style: s.pour_style || undefined,
    plan_start: s.plan_start || "",
    plan_end: s.plan_end || "",
    // accept any temp key the editor produced
    temperature_c:
      s.temperature_c ?? s.temp_c ?? s.kettle_temp_c ?? s.temp_C ?? undefined,
    note: s.note || undefined,
  };
}

function buildPlanTimelineFromSteps(steps: StepLike[]) {
  return steps.map((st, i) => ({
    id: st.id,
    label: st.label || (st.id === "bloom" ? "Bloom" : st.id),
    type: (st.type as any) || "pour",
    plan_start: st.plan_start || (i === 0 ? "0:00" : ""),
    plan_end: st.plan_end || "",
    to_g: Number.isFinite(st.water_to as any) ? Number(st.water_to) : undefined,
    style: st.pour_style || undefined,
    temp_c: st.temperature_c ?? st.temp_c ?? st.kettle_temp_c ?? st.temp_C,
  }));
}

/* ------------------------------- nav payload ------------------------------- */
type NavState = {
  bean_id?: string | null;
  setup?: {
    dose?: string;
    ratio?: string;
    total?: string;
    grind?: string;
    temperature_c?: number;
  };
  bean_snapshot?: {
    id?: string;
    name?: string;
    roaster?: string;
    origin?: string;
    variety?: string;
    process?: string;
  };
  gear_snapshot?: {
    display?: string;
    brewer?: string;
    grinder?: string;
    grinder_brand?: string;
    grinder_model?: string;
    water?: string;
    raw?: any;
  };
};

type Card = {
  id: string;
  label: string;
  // per‑step additions (NOT cumulative)
  water_g?: number;
  temp_C?: number;
  pour_style?: "center" | "spiral" | "pulse";
  agitation?: { method?: string; intensity?: "gentle" | "moderate" | "high" };
  note?: string;

  // optional planned schedule
  plan_start?: string; // "m:ss"
  plan_end?: string;   // "m:ss"
};

type Segment = {
  type: "bloom" | "pour" | "drawdown";
  label: string;
  start_ms: number;
  end_ms: number | null; // null while running
  cum_g?: number; // cumulative water at end (for bloom/pour)
  style?: Card["pour_style"];
  agitation?: Card["agitation"];
  note?: string;
};

/* ------------------------ voice-target/undo helpers ------------------------ */
type VoiceTarget = { kind: "bloom" | "pour"; idx?: number };
const undoStack = { current: [] as Array<() => void> };
function pushUndo(fn: () => void) { undoStack.current.push(fn); }
export function undoLastVoice() {
  const fn = undoStack.current.pop();
  if (fn) fn();
}

/* -------------------------------- component -------------------------------- */
export default function ManualLog() {
  const [showHelp, setShowHelp] = useState(false);
  const nav = useNavigate();
  const loc = useLocation();
  const state = (loc.state || {}) as NavState;
  const { patch } = useBrewHistory();
  const { data: profile } = useProfile();
  const { toast } = useToast();
  const { prefs } = useRoundPref();
  const { start, step, finish, getSessionId } = useBrewSession();

  // normalize incoming setup
  const dose_g = toNum(state.setup?.dose);
  const setupTotal = toNum(state.setup?.total);
  const ratioP = parseRatio(state.setup?.ratio);
  const ratio_num = ratioP.ok ? ratioP.factor : NaN;
  const ratio_str = state.setup?.ratio || "";
  const bean_id = state.bean_id || null;
  const grind_text = (state.setup?.grind || "").trim();


  // ★ snapshots from Setup (immutable)
  const bean_snapshot = state.bean_snapshot || null;
  const gear_snapshot = state.gear_snapshot || null;

  const temperature_c = Number.isFinite(state.setup?.temperature_c as any)
    ? (state.setup?.temperature_c as number)
    : 96;

  const brew_name = "Manual brew";

  // gram rounding preference
  const roundG = useMemo(() => {
    const st = Math.max(0.01, Number(prefs.gramStep ?? 1));
    return (v: number) => Math.round(v / st) * st;
  }, [prefs.gramStep]);

  // target total
  const [targetTotal, setTargetTotal] = useState<number>(
    isPos(setupTotal) ? setupTotal : 300
  );

  // plan cards (water_g is per step; we derive endsAt cumulatives)
  const [bloom, setBloom] = useState<Card>({
    id: "bloom",
    label: "Bloom",
    water_g: 30,
    temp_C: Math.min(96, temperature_c),
    pour_style: "center",
    plan_start: "",
    plan_end: "",
  });
  const [pours, setPours] = useState<Card[]>([
    {
      id: "p1",
      label: "Pour 1",
      water_g: targetTotal - (bloom.water_g ?? 0),
      temp_C: Math.min(96, temperature_c),
      pour_style: "spiral",
      plan_start: "",
      plan_end: "",
    },
  ]);

  // derived cumulatives
  const endsAtBloom = roundG(bloom.water_g ?? 0);
  const endsAtPour = (i: number) => {
    const prev = endsAtBloom + pours.slice(0, i).reduce((s, p) => s + (p.water_g ?? 0), 0);
    return roundG(prev + (pours[i].water_g ?? 0));
  };

  // runtime
  const [preroll, setPreroll] = useState(0);
  const [running, setRunning] = useState(false);
  const [paused, setPaused] = useState(false);
  const [elapsedMs, setElapsedMs] = useState(0);
  const prerollTimer = useRef<number | null>(null);
  const tickTimer = useRef<number | null>(null);

  // brew start epoch for server at_ms
  const brewStartMs = useRef<number | null>(null);

  // which step is active
  const [stage, setStage] = useState<"bloom" | number>("bloom");
  const [activeStartedAt, setActiveStartedAt] = useState<number | null>(null);

  // best‑effort server session id
  const [serverSessionId, setServerSessionId] = useState<string | null>(null);

  // ensure we have setup, otherwise go back
  useEffect(() => {
    if (!state?.setup) nav("/brew/manual");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ---------------- water redistribution & clamps (mitigations) ------------- */
  function clampGrams(g: number) {
    const pouredSoFar =
      endsAtBloom + pours.reduce((s, p) => s + (p.water_g ?? 0), 0);
    const remaining = Math.max(0, targetTotal - pouredSoFar);
    if (remaining <= 0) return roundG(Math.max(0, g));
    return roundG(Math.max(0, Math.min(g, remaining)));
  }

  // Distribute remaining water_g across future pours so that last ends at targetTotal
  function redistributeFrom(index: number) {
    setPours((prev) => {
      const safeBloom = endsAtBloom;
      const doneUpTo = stage === "bloom" ? 0 : (typeof stage === "number" ? endsAtPour(stage) : 0);
      const anchor = Math.max(doneUpTo, safeBloom);

      const startAt = Math.max(0, index + 1);
      const lockedCum = anchor + prev.slice(0, startAt).reduce((s, p) => s + (p.water_g ?? 0), 0);
      const remainingTotal = Math.max(0, targetTotal - lockedCum);
      const k = prev.length - startAt;
      if (k <= 0) return prev;

      const even = remainingTotal / k;
      const next = [...prev];
      for (let i = 0; i < k; i++) {
        next[startAt + i] = { ...next[startAt + i], water_g: roundG(even) };
      }

      // nudge last pour to land exactly at target (remove rounding drift)
      const drift =
        targetTotal - (safeBloom + next.reduce((s, p) => s + (p.water_g ?? 0), 0));
      next[next.length - 1] = {
        ...next[next.length - 1],
        water_g: roundG((next[next.length - 1].water_g ?? 0) + drift),
      };
      return next;
    });
  }

  // change in target → redistribute future pours
  useEffect(() => {
    redistributeFrom(typeof stage === "number" ? stage : -1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetTotal, bloom.water_g]);

  /* --------------------------------- timers -------------------------------- */
  useEffect(() => {
    if (preroll <= 0 || prerollTimer.current != null) return;
    prerollTimer.current = window.setInterval(() => {
      setPreroll((s) => {
        if (s <= 1) {
          window.clearInterval(prerollTimer.current!);
          prerollTimer.current = null;
          brewStartMs.current = Date.now();
          setRunning(true);
          setPaused(false);
          setActiveStartedAt(0);
          openSegment("bloom", "Bloom", 0);
          return 0;
        }
        return s - 1;
      });
    }, 1000) as unknown as number;
    return () => {
      if (prerollTimer.current) {
        window.clearInterval(prerollTimer.current);
        prerollTimer.current = null;
      }
    };
  }, [preroll]);

  useEffect(() => {
    if (!running || paused) {
      if (tickTimer.current) {
        window.clearInterval(tickTimer.current);
        tickTimer.current = null;
      }
      return;
    }
    if (tickTimer.current) return;
    tickTimer.current = window.setInterval(() => {
      if (brewStartMs.current != null) setElapsedMs(Date.now() - brewStartMs.current);
    }, 200) as unknown as number;
    return () => {
      if (tickTimer.current) {
        window.clearInterval(tickTimer.current);
        tickTimer.current = null;
      }
    };
  }, [running, paused]);

  /* ------------------------------ session start ----------------------------- */
  useEffect(() => {
    let cancelled = false;

    (async () => {
      await start({
        mode: "manual",
        source: "ui",
        bean: bean_snapshot || (bean_id ? { id: bean_id } : undefined),
        gear: gear_snapshot || undefined,
        recipe: {
          brew_name,
          dose: isPos(dose_g) ? dose_g : undefined,
          ratio: isPos(ratio_num) ? ratio_num : undefined,
          ratio_str,
          total_water: targetTotal,
          temperature_c: Math.min(96, temperature_c),
          steps: [
            { id: "bloom", label: "Bloom", type: "bloom", water_to: endsAtBloom, pour_style: bloom.pour_style, plan_start: bloom.plan_start, plan_end: bloom.plan_end },
            ...pours.map((p, i) => ({
              id: p.id,
              label: p.label,
              type: "pour" as const,
              water_to: endsAtPour(i),
              pour_style: p.pour_style,
              plan_start: p.plan_start,
              plan_end: p.plan_end,
            })),
          ],
        },
      } as any);

      try {
        const res = await API.startSession({
          user_id: profile?.userId || "default-user",
          mode: "manual",
          source: "ui",
          bean_id: bean_id || undefined,
          recipe: {
            brew_name,
            dose_g: isPos(dose_g) ? dose_g : undefined,
            ratio: isPos(ratio_num) ? ratio_num : undefined,
            ratio_str,
            water_g: targetTotal,
            temperature_c: Math.min(96, temperature_c),
            grind_text, 
            steps: [
              { id: "bloom", label: "Bloom", type: "bloom", water_to: endsAtBloom, pour_style: bloom.pour_style, plan_start: bloom.plan_start, plan_end: bloom.plan_end },
              ...pours.map((p, i) => ({
                id: p.id,
                label: p.label,
                type: "pour" as const,
                water_to: endsAtPour(i),
                pour_style: p.pour_style,
                plan_start: p.plan_start,
                plan_end: p.plan_end,
              })),
            ],
            // ★ mirror snapshots to server copy (when available)
            bean: bean_snapshot || (bean_id ? { id: bean_id } : undefined),
            gear: gear_snapshot || undefined,
          },
        });
        if (!cancelled) setServerSessionId(res?.session_id ?? null);
      } catch {
        /* offline/422 ok */
      }
    })();

    return () => {
      cancelled = true;
      if (prerollTimer.current) window.clearInterval(prerollTimer.current);
      if (tickTimer.current) window.clearInterval(tickTimer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ------------------------- timeline & step logging ------------------------ */
  const [segments, setSegments] = useState<Segment[]>([]);

  function openSegment(type: Segment["type"], label: string, start_ms: number) {
    setSegments((prev) => [...prev, { type, label, start_ms, end_ms: null }]);
  }
  function closeRunningSegment(patch?: Partial<Segment>) {
    setSegments((prev) => {
      const next = [...prev];
      const idx = next.findIndex((s) => s.end_ms === null);
      if (idx >= 0) next[idx] = { ...next[idx], end_ms: elapsedMs, ...(patch || {}) };
      return next;
    });
  }

  function startActiveStep(atMs?: number) {
    if (activeStartedAt != null) return;
    const startMs = Number.isFinite(atMs) ? (atMs as number) : elapsedMs;
    setActiveStartedAt(startMs);
    if (stage === "bloom") openSegment("bloom", "Bloom", startMs);
    else if (typeof stage === "number") openSegment("pour", pours[stage].label, startMs);
  }

  async function logDone(card: Card, type: "bloom" | "pour", endOverrideMs?: number) {
    // cumulative target after this step
    const cum =
      type === "bloom"
        ? endsAtBloom
        : typeof stage === "number"
        ? endsAtPour(stage)
        : undefined;

    // local elapsed end for timeline
    const end_ms = Number.isFinite(endOverrideMs) ? (endOverrideMs as number) : elapsedMs;

    // compute **epoch** at_ms for server (brew start epoch + elapsed end)
    const atEpoch = (brewStartMs.current ?? Date.now()) + end_ms;

    // 1) Post CANONICAL step to server (best-effort)
    if (serverSessionId && !String(serverSessionId).startsWith("local-")) {
      try {
        await API.step({
          session_id: serverSessionId,
          step:
            type === "bloom"
              ? {
                  type: "bloom",
                  water_g: Number(cum) || 0,
                  at_ms: atEpoch,
                  style: card.pour_style || "center",
                }
              : {
                  type: "pour",
                  target_g: Number(cum) || 0,
                  at_ms: atEpoch,
                  style: card.pour_style || "spiral",
                },
        });
      } catch {
        /* ignore offline errors */
      }
    }

    // 2) Record local step event & segment (drives pretty timeline)
    await step({
      type,
      at_ms: end_ms,               // local elapsed for client-only timeline
      water_to: cum,
      temp_C: card.temp_C,
      pour_style: card.pour_style,
      agitation: card.agitation,
      note: card.note,
    } as any);

    closeRunningSegment({
      cum_g: cum,
      note: card.note,
      agitation: card.agitation,
      style: card.pour_style,
    });
    setActiveStartedAt(null);
  }
  function buildPlannedSegments(): Segment[] {
    const out: Segment[] = [];

    const bStart = mmssToMs(bloom.plan_start || "");
    const bEnd   = mmssToMs(bloom.plan_end   || "");
    if (Number.isFinite(bStart) && Number.isFinite(bEnd) && (bEnd as number) > (bStart as number)) {
      out.push({
        type: "bloom",
        label: "Bloom",
        start_ms: bStart as number,
        end_ms: bEnd as number,
        cum_g: endsAtBloom,
        style: bloom.pour_style,
        agitation: bloom.agitation,
        note: bloom.note,
      });
    }

    pours.forEach((p, i) => {
      const pStart = mmssToMs(p.plan_start || "");
      const pEnd   = mmssToMs(p.plan_end   || "");
      if (Number.isFinite(pStart) && Number.isFinite(pEnd) && (pEnd as number) > (pStart as number)) {
        out.push({
          type: "pour",
          label: p.label,
          start_ms: pStart as number,
          end_ms: pEnd as number,
          cum_g: endsAtPour(i),
          style: p.pour_style,
          agitation: p.agitation,
          note: p.note,
        });
      }
    });

    // If user only filled some times, keep whatever is valid; if none valid, return []
    return out;
  }

  async function onFinish(early = false) {
    setRunning(false);
    setPaused(false);
    closeRunningSegment();

    // 1) Prefer actual recorded segments; if none, synthesize from plan inputs
    const haveActual = segments.length > 0;
    const base: Segment[] = haveActual
      ? segments.map((s) => ({ ...s, end_ms: s.end_ms ?? elapsedMs }))
      : buildPlannedSegments();

    // 2) Add a drawdown bar if there is at least one segment and it makes sense
    let finalTimeline: Segment[] = base;
    if (base.length > 0) {
      const last = base[base.length - 1];
      const ddStart = last.end_ms!;
      const ddEnd = haveActual ? elapsedMs : Math.max(ddStart, ddStart + 1); // >= 1ms wide
      finalTimeline = [
        ...base,
        { type: "drawdown", label: "Drawdown", start_ms: ddStart, end_ms: ddEnd } as Segment,
      ];
    }

    // 3) Build summary (timeline only; do NOT nest recipe here)
    const summary = {
      brew_name,
      target_total_g: targetTotal,
      timeline: finalTimeline.map((s) => ({
        type: s.type,
        label: s.label,
        start_ms: s.start_ms,
        end_ms: s.end_ms!,
        cum_g: s.cum_g,
        style: s.style,
        agitation: s.agitation,
        note: s.note,
      })),
    };

    // 4) Build recipe_snapshot separately so steps always reach Summary
    const recipe_snapshot = {
      brew_name,
      dose: isPos(dose_g) ? dose_g : undefined,
      ratio: isPos(ratio_num) ? ratioP.pretty : ratio_str,
      total_water: targetTotal,
      temperature_c,
      // (optional) include richer grind fields if you have them available:
      // grind_label, grind_setting, grind_target_micron, grind_scale,
      grind_text,
      bean: bean_snapshot || (bean_id ? { id: bean_id } : null),
      gear: gear_snapshot || null,
      steps: [
        {
          id: "bloom",
          label: "Bloom",
          type: "bloom",
          water_to: endsAtBloom,
          pour_style: bloom.pour_style,
          kettle_temp_c: bloom.temp_C,
          note: bloom.note,
          plan_start: bloom.plan_start,
          plan_end: bloom.plan_end,
        },
        ...pours.map((p, i) => ({
          id: p.id,
          label: p.label,
          type: "pour" as const,
          water_to: endsAtPour(i),
          pour_style: p.pour_style,
          kettle_temp_c: p.temp_C,
          note: p.note,
          plan_start: p.plan_start,
          plan_end: p.plan_end,
        })),
      ],
    };

    // 5) Ensure there is a LOCAL session id (if user never pressed Start)
    let sid = getSessionId?.() as string | undefined;

      if (!sid) {
        // Build the minimal recipe shape that start(...) expects
        const recipeForStart = {
    brew_name,
    dose: isPos(dose_g) ? dose_g : undefined,
    total_water: targetTotal,
    // keep a numeric ratio if available; keep display string too
    ratio: isPos(ratio_num) ? ratio_num : undefined,
    ratio_str: isPos(ratio_num) ? ratioP.pretty : ratio_str,
    temperature_c,
    // IMPORTANT: steps must use temp_C (not kettle_temp_c)
    steps: [
      {
        id: "bloom",
        label: "Bloom",
        type: "bloom" as const,
        water_to: endsAtBloom,
        pour_style: bloom.pour_style,
        temp_C: bloom.temp_C,             // ✅ correct field name for start(...)
        note: bloom.note,
        plan_start: bloom.plan_start,
        plan_end: bloom.plan_end,
      },
      ...pours.map((p, i) => ({
        id: p.id,
        label: p.label,
        type: "pour" as const,
        water_to: endsAtPour(i),
        pour_style: p.pour_style,
        temp_C: p.temp_C,                 
        note: p.note,
        plan_start: p.plan_start,
        plan_end: p.plan_end,
      })),
    ],
  };

      // Create a local session row (server may still 404 later; that's fine)
        const localId = await start({
          mode: "manual",
          bean: bean_snapshot || (bean_id ? { id: bean_id } : null),
          activeGearSnapshot: gear_snapshot || null, 
          recipe: recipeForStart,                    
          source: "ui",
        });

      sid = localId;

    }

    const finishId = await finish({ duration_ms: elapsedMs, summary, recipe_snapshot });

      // Resolve ids — we PREFER the LOCAL id for navigation (so Summary always finds it)
      const localId = sid || getSessionId?.() || null;
      const serverId = finishId || null;
      const ensuredId = localId || serverId; // we will navigate with this

      // 1) Write into the LOCAL row and link the server id (primary source for Summary)
      if (localId) {
        patch(localId, {
          summary: { ...summary, recipe_snapshot }, // 👈 embed snapshot inside summary
          recipe_snapshot,                           // optional duplicate for debug
          server_session_id: serverId || undefined,  // bidirectional linking
          aliases: serverId ? [serverId] : undefined,
        });
      }

      // 2) Also mirror into the SERVER-ID row (belt & suspenders):
      if (serverId && serverId !== localId) {
        patch(serverId, {
          summary: { ...summary, recipe_snapshot },
          recipe_snapshot,
          server_session_id: serverId,
          aliases: localId ? [localId] : undefined,
        });
      }

      // 3) Navigate using the LOCAL id if we have it (this is what fixes "local entry: null")
      nav("/brew/assess", { state: { session_id: ensuredId, type: "manual" } });




  }
  
  /* --------------------------------- STT/NLP -------------------------------- */

  const NUMBER_WORDS: Record<string, number> = {
    zero: 0, oh: 0, one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9,
    ten: 10, eleven: 11, twelve: 12, thirteen: 13, fourteen: 14, fifteen: 15, sixteen: 16,
    seventeen: 17, eighteen: 18, nineteen: 19,
    twenty: 20, thirty: 30, forty: 40, fifty: 50, sixty: 60, seventy: 70, eighty: 80, ninety: 90,
  };

  function parseNumberWordish(seq: string): number | undefined {
    const s = seq.trim().toLowerCase();
    if (/^\d+(\.\d+)?$/.test(s)) return parseFloat(s);
    if (NUMBER_WORDS[s] != null) return NUMBER_WORDS[s];

    // hyphen form: twenty-five
    const hy = s.split("-");
    if (hy.length === 2 && NUMBER_WORDS[hy[0]] != null && NUMBER_WORDS[hy[1]] != null) {
      return NUMBER_WORDS[hy[0]] + NUMBER_WORDS[hy[1]];
    }

    // space form: thirty five
    const sp = s.split(/\s+/);
    if (sp.length === 2 && NUMBER_WORDS[sp[0]] != null && NUMBER_WORDS[sp[1]] != null) {
      return NUMBER_WORDS[sp[0]] + NUMBER_WORDS[sp[1]];
    }
    return undefined;
  }

  function parseFlexibleGrams(text: string): number | undefined {
    const t = text.toLowerCase();
    const unit = t.match(/([\d\.]+)\s*(g|gram|grams|ml)\b/);
    if (unit) return parseFloat(unit[1]);

    const wordUnit = t.match(/([a-z\- ]+)\s*(g|gram|grams|ml)\b/);
    if (wordUnit) {
      const v = parseNumberWordish(wordUnit[1]);
      if (Number.isFinite(v)) return v;
    }

    const bare = t.match(/\b(\d+(?:\.\d+)?)\b/);
    if (bare && /\b(water|grams?|ml|target|total)\b/.test(t)) return parseFloat(bare[1]);
    return undefined;
  }

  function parseFlexibleTimeMs(text: string): number | undefined {
    const t = text.toLowerCase();

    // mm:ss
    const colon = t.match(/(\d{1,2}):([0-5]\d)\b/);
    if (colon) return parseInt(colon[1], 10) * 60_000 + parseInt(colon[2], 10) * 1_000;

    // Xm Ys
    const xmYs = t.match(/(\d+)\s*m(?:in(?:ute)?s?)?\s*(\d+)\s*s(?:ec(?:ond)?s?)?/);
    if (xmYs) return parseInt(xmYs[1], 10) * 60_000 + parseInt(xmYs[2], 10) * 1_000;

    // X minutes
    const onlyM = t.match(/(\d+)\s*m(?:in(?:ute)?s?)?\b/);
    if (onlyM) return parseInt(onlyM[1], 10) * 60_000;

    // X seconds
    const onlyS = t.match(/(\d+)\s*s(?:ec(?:ond)?s?)?\b/);
    if (onlyS) return parseInt(onlyS[1], 10) * 1_000;

    // bare mmss “030”, “105”, “205”, “1230”
    const bare = t.match(/\b(\d{3,4})\b/);
    if (bare) {
      const raw = bare[1];
      const mm = parseInt(raw.slice(0, -2), 10);
      const ss = parseInt(raw.slice(-2), 10);
      if (mm >= 0 && ss >= 0 && ss < 60) return (mm * 60 + ss) * 1000;
    }

    // spoken “one oh five”
    const tokens = t.replace(/[^a-z0-9\s]/g, " ").split(/\s+/).filter(Boolean);
    const nums = tokens.map(parseNumberWordish).filter((v): v is number => Number.isFinite(v as number));
    if (nums.length >= 2 && nums[1] < 60) return (nums[0] * 60 + nums[1]) * 1000;
    if (nums.length === 1) {
      const s = nums[0];
      if (s <= 180) return s * 1000;
    }
    return undefined;
  }

  const ORD_LOCAL: Record<string, number> = { first: 1, second: 2, third: 3, fourth: 4, fifth: 5 };
  function ordToIndex(tok?: string) {
    if (!tok) return 0;
    const t = tok.toLowerCase();
    if (ORD_LOCAL[t]) return ORD_LOCAL[t] - 1;
    const n = parseInt(t, 10);
    return Number.isFinite(n) ? clamp(n - 1, 0, 4) : 0;
  }

  // ——— Canonical LocalEvent (field‑first) ———
  type LocalEvent =
    | { type: "control"; action: "start" | "pause" | "resume" | "next" | "done" | "finish" }
    | { type: "control_step"; action: "start" | "end"; kind?: "bloom" | "pour"; idx?: number }
    | { type: "set_field"; field: "plan_start_ms" | "plan_end_ms" | "water_g" | "pour_style" | "temp_C"; value: any; target?: VoiceTarget }
    | { type: "set_target"; grams: number }
    | { type: "dump_here" }
    | { type: "dump_last" }
    | { type: "add_pour" }
    | { type: "note"; text: string };

  // ——— Lightweight interpreter (English‑only, field‑first) ———
  function localInterpret(utt: string): LocalEvent[] {
    const out: LocalEvent[] = [];
    const txt = utt.toLowerCase().trim();

    // global controls
    if (/^(start)\b/.test(txt)) return [{ type: "control", action: "start" }];
    if (/^(pause|hold)\b/.test(txt)) return [{ type: "control", action: "pause" }];
    if (/^(resume|continue)\b/.test(txt)) return [{ type: "control", action: "resume" }];
    if (/^(next|proceed)\b/.test(txt)) return [{ type: "control", action: "next" }];
    if (/^(finish)\b/.test(txt)) return [{ type: "control", action: "finish" }];
    if (/^(done)\b/.test(txt)) return [{ type: "control", action: "done" }];

    // explicit target: bloom / pour N / "in pour N"
    let target: VoiceTarget | undefined;
    const bloomHit = /\bbloom\b/.test(txt);
    const explicitPour =
      txt.match(/\b(pour)\s+(first|second|third|fourth|fifth|\d+)\b/) ||
      txt.match(/\b(first|second|third|fourth|fifth|\d+)\s+(pour)\b/) ||
      txt.match(/\b(pour)\s+(\d+)\b/) ||
      txt.match(/\bin\s+(pour)\s+(first|second|third|fourth|fifth|\d+)\b/);

    if (bloomHit) {
      target = { kind: "bloom" };
    } else if (explicitPour) {
      const ord = (explicitPour[2] || explicitPour[1] || explicitPour[3] || "").toString();
      const idx = ordToIndex(ord);
      target = { kind: "pour", idx };
    }

    // step start/end (also tolerate "finish")
    const stepMatch =
      txt.match(/\b(start|end|finish)\s+(bloom|pour)(?:\s+(first|second|third|fourth|fifth|\d+))?\b/) ||
      txt.match(/\b(bloom|pour)(?:\s+(first|second|third|fourth|fifth|\d+))?\s+(start|end|finish)\b/);
    if (stepMatch) {
      const action = (stepMatch[1] || stepMatch[3] || "").replace("finish", "end") as "start" | "end";
      const kind = (stepMatch[2] || stepMatch[1] || "").includes("bloom") ? "bloom" : "pour";
      const idx = kind === "pour" ? ordToIndex(stepMatch[3]) : undefined;
      out.push({ type: "control_step", action, kind, idx });
    }

    // time assignment (start/end at X)
    const atMs = parseFlexibleTimeMs(txt);
    if (Number.isFinite(atMs)) {
      if (/\bstart\b/.test(txt))
        out.push({ type: "set_field", field: "plan_start_ms", value: atMs, target });
      if (/\b(end|finish)\b/.test(txt))
        out.push({ type: "set_field", field: "plan_end_ms", value: atMs, target });
    }

    // style
    if (/\bspiral\b/.test(txt)) out.push({ type: "set_field", field: "pour_style", value: "spiral", target });
    if (/\bcenter|centre\b/.test(txt)) out.push({ type: "set_field", field: "pour_style", value: "center", target });
    if (/\bpulse|pulsing\b/.test(txt)) out.push({ type: "set_field", field: "pour_style", value: "pulse", target });

    // temperature
    if (/\b(temp|temperature|kettle)\b/.test(txt)) {
      const num = (txt.match(/(\d{2,3})\b/) || [])[1];
      if (num) out.push({ type: "set_field", field: "temp_C", value: clamp(parseInt(num, 10), 60, 100), target });
    }

    // grams / target
    const grams = parseFlexibleGrams(txt);
    if (Number.isFinite(grams as any)) {
      if (/\b(target|total)\b/.test(txt)) {
        out.push({ type: "set_target", grams: grams! });
      } else if (/\bremaining\b/.test(txt) && /\b(this|current)\b/.test(txt) && /\bpour\b/.test(txt)) {
        out.push({ type: "dump_here" });
      }
      else {
        out.push({ type: "set_field", field: "water_g", value: grams!, target });
      }
    }

    // dump remaining to last pour
    if (/\b(dump|use)\b.*\b(remaining|rest)\b.*\b(last)\b.*\bpour\b/.test(txt)) {
      out.push({ type: "dump_last" });
    }

    // fallback to note
    if (out.length === 0) out.push({ type: "note", text: utt });
    return out;
  }

  // ——— Normalization: utils parse (step‑first) → field‑first ———
  type UtilsEvent =
    | { type: "control"; action: "start" | "pause" | "resume" | "next" | "done" | "finish" }
    | { type: "add_pour" }
    | { type: "set_target_total"; grams: number }
    | { type: "note"; text: string }
    | { type: "start_step"; step: "bloom" | "pour"; index?: number; at_ms?: number }
    | { type: "end_step"; step: "bloom" | "pour"; index?: number; at_ms?: number }
    | { type: "set_step_to"; step: "bloom" | "pour"; index?: number; water_to_g: number }
    | { type: "set_step_remaining"; step: "pour"; index?: number }
    | { type: "set_style"; step: "bloom" | "pour"; index?: number; style: "center"|"spiral"|"pulse" }
    | { type: "set_temp"; step: "bloom" | "pour"; index?: number; temp_C: number };

  function zIndexFromUtils(index?: number) {
    const n = Number(index);
    if (!Number.isFinite(n) || n <= 1) return 0;
    return Math.max(0, Math.floor(n - 1));
  }
  function targetFrom(step: "bloom" | "pour", idx?: number): VoiceTarget {
    return step === "bloom" ? { kind: "bloom" } : { kind: "pour", idx: zIndexFromUtils(idx) };
  }
  function perStepFromCumulative(step: "bloom" | "pour", idx0: number, to_g: number) {
    if (step === "bloom") return Math.max(0, roundG(to_g));
    const cumBefore = endsAtBloom + pours.slice(0, idx0).reduce((s, p) => s + (p.water_g ?? 0), 0);
    return Math.max(0, roundG(to_g - cumBefore));
    }
  function normalizeUtilsEvents(evs: UtilsEvent[]): LocalEvent[] {
    const out: LocalEvent[] = [];
    for (const ev of evs) {
      switch (ev.type) {
        case "control": out.push({ type: "control", action: ev.action }); break;
        case "add_pour": out.push({ type: "add_pour" }); break;
        case "set_target_total": out.push({ type: "set_target", grams: ev.grams }); break;
        case "note": out.push({ type: "note", text: ev.text }); break;

        case "start_step": {
          const tgt = targetFrom(ev.step, ev.index);
          out.push({ type: "control_step", action: "start", kind: ev.step, ...(tgt.kind === "pour" && typeof tgt.idx === "number" ? { idx: tgt.idx } : {}) });
          if (Number.isFinite(ev.at_ms)) out.push({ type: "set_field", field: "plan_start_ms", value: ev.at_ms as number, target: tgt });
          break;
        }
        case "end_step": {
          const tgt = targetFrom(ev.step, ev.index);
          out.push({ type: "control_step", action: "end", kind: ev.step, ...(tgt.kind === "pour" && typeof tgt.idx === "number" ? { idx: tgt.idx } : {}) });
          if (Number.isFinite(ev.at_ms)) out.push({ type: "set_field", field: "plan_end_ms", value: ev.at_ms as number, target: tgt });
          break;
        }

        case "set_step_to": {
          const idx0 = ev.step === "pour" ? zIndexFromUtils(ev.index) : 0;
          const per = perStepFromCumulative(ev.step, idx0, ev.water_to_g);
          out.push({ type: "set_field", field: "water_g", value: per, target: targetFrom(ev.step, ev.index) });
          break;
        }
        case "set_step_remaining": out.push({ type: "dump_here" }); break;
        case "set_style": out.push({ type: "set_field", field: "pour_style", value: ev.style, target: targetFrom(ev.step, ev.index) }); break;
        case "set_temp": out.push({ type: "set_field", field: "temp_C", value: clamp(ev.temp_C, 60, 100), target: targetFrom(ev.step, ev.index) }); break;
      }
    }
    return out;
  }

  // target-aware updater used by voice events
  function applyToTargetOrActive(update: Partial<Card>, target?: VoiceTarget) {
    if (target?.kind === "bloom") {
      const prev = bloom;
      pushUndo(() => setBloom(prev));
      setBloom((b) => ({ ...b, ...update }));
      return;
    }
    if (target?.kind === "pour" && typeof target.idx === "number") {
      const idx = target.idx;
      setPours((list) => {
        const next = [...list];
        const prev = next[idx];
        pushUndo(() => {
          setPours((l2) => {
            const n2 = [...l2];
            n2[idx] = prev;
            return n2;
          });
        });
        next[idx] = { ...next[idx], ...update };
        return next;
      });
      return;
    }
    applyToActive(update);
  }

  const handleFinalSTT = async (input: any) => {
    let utterance = "";
    let events: LocalEvent[] = [];

    if (typeof input === "string") {
      utterance = input.trim();
      if (!utterance) return;

      const primary = localInterpret(utterance);
      const utilsRaw = parseBrewCommand(utterance) as any[];
      const normalized = Array.isArray(utilsRaw) ? normalizeUtilsEvents(utilsRaw as any) : [];
      const seen = new Set<string>();
      events = [...primary, ...normalized].filter((e) => {
        const key = JSON.stringify(e);
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      });
    } else if (input && typeof input === "object") {
      events = Array.isArray(input) ? (input as LocalEvent[]) : [input as LocalEvent];
    } else {
      return;
    }

    if (!events.length) {
      if (utterance) {
        applyToActive({ note: utterance });
        toast("Note added", "success");
      }
      return;
    }

    const priority = (t: string) =>
      ({ set_field: 0, set_target: 0, add_pour: 1, control_step: 2, dump_here: 2, dump_last: 2, control: 3, note: 4 } as any)[t] ?? 5;
    (events as any[]).sort((a, b) => priority(a.type) - priority(b.type));

    let applied = false;

    for (const ev of events as any[]) {
      if (ev.type === "set_field") {
        if (ev.field === "water_g") {
          const v = clampGrams(Number(ev.value));
          applyToTargetOrActive({ water_g: roundG(v) }, ev.target);
          toast(`Water → ${roundG(v)}g`, "success");
        } else if (ev.field === "plan_start_ms" || ev.field === "plan_end_ms") {
          const key = ev.field === "plan_start_ms" ? "plan_start" : "plan_end";
          const s = msToMMSS(ev.value);
          if (ev.target?.kind === "bloom") {
            const prev = bloom[key as "plan_start" | "plan_end"];
            pushUndo(() => setBloom((b) => ({ ...b, [key]: prev })));
            setBloom((b) => ({ ...b, [key]: s }));
          } else if (ev.target?.kind === "pour" && typeof ev.target.idx === "number") {
            const i = ev.target.idx;
            const prev = pours[i]?.[key as "plan_start" | "plan_end"];
            pushUndo(() => setPours((list) => { const n = [...list]; n[i] = { ...n[i], [key]: prev }; return n; }));
            setPours((list) => { const n = [...list]; n[i] = { ...n[i], [key]: s }; return n; });
          } else {
            if (stage === "bloom") {
              const prev = bloom[key as any];
              pushUndo(() => setBloom((b) => ({ ...b, [key]: prev })));
              setBloom((b) => ({ ...b, [key]: s }));
            } else if (typeof stage === "number") {
              const prev = pours[stage]?.[key as any];
              pushUndo(() => setPours((list) => { const n = [...list]; n[stage] = { ...n[stage], [key]: prev }; return n; }));
              setPours((list) => { const n = [...list]; n[stage] = { ...n[stage], [key]: s }; return n; });
            }
          }
          toast(`${key.replace("plan_", "")} → ${s}`, "success");
        } else {
          applyToTargetOrActive({ [ev.field]: ev.value } as any, ev.target);
        }
        applied = true;

      } else if (ev.type === "set_target") {
        const v = toNum(ev.grams);
        if (isPos(v)) setTargetTotal(roundG(v));
        applied = true;

      } else if (ev.type === "dump_here") {
        if (typeof stage === "number") {
          const currentCumBefore = endsAtBloom + pours.slice(0, stage).reduce((s, p) => s + (p.water_g ?? 0), 0);
          const remain = Math.max(0, targetTotal - currentCumBefore);
          const prev = pours[stage]?.water_g;
          pushUndo(() => setPours((list) => { const n = [...list]; n[stage] = { ...n[stage], water_g: prev }; return n; }));
          setPours((list) => {
            const next = [...list];
            next[stage] = { ...next[stage], water_g: roundG(remain) };
            return next;
          });
          applied = true;
          toast(`This pour → remaining (${roundG(remain)}g)`, "success");
        }

      } else if (ev.type === "dump_last") {
        const lastIdx = pours.length - 1;
        const cumBeforeLast = endsAtBloom + pours.slice(0, lastIdx).reduce((s, p) => s + (p.water_g ?? 0), 0);
        const remain = Math.max(0, targetTotal - cumBeforeLast);
        const prev = pours[lastIdx]?.water_g;
        pushUndo(() => setPours((list) => { const n = [...list]; n[lastIdx] = { ...n[lastIdx], water_g: prev }; return n; }));
        setPours((list) => {
          const next = [...list];
          next[lastIdx] = { ...next[lastIdx], water_g: roundG(remain) };
          return next;
        });
        if (typeof stage === "number" && stage < lastIdx) setStage(lastIdx);
        applied = true;
        toast(`Last pour → remaining (${roundG(remain)}g)`, "success");

      } else if (ev.type === "note") {
        applyToActive({ note: ev.text });
        applied = true;

      } else if (ev.type === "control_step") {
        if (ev.kind === "bloom") setStage("bloom");
        if (ev.kind === "pour" && Number.isFinite(ev.idx)) setStage(ev.idx as number);

        const activeIdx = typeof stage === "number" ? stage : null;
        const atMsStart = mmssToMs((stage === "bloom" ? bloom.plan_start : activeIdx != null ? pours[activeIdx]?.plan_start : "") || "");
        const atMsEnd = mmssToMs((stage === "bloom" ? bloom.plan_end : activeIdx != null ? pours[activeIdx]?.plan_end : "") || "");

        if (ev.action === "start") {
          startActiveStep(Number.isFinite(atMsStart) ? atMsStart : undefined);
        } else if (ev.action === "end") {
          await logDone(stage === "bloom" ? bloom : pours[activeIdx as number], stage === "bloom" ? "bloom" : "pour", Number.isFinite(atMsEnd) ? atMsEnd : undefined);
          if (stage === "bloom") setStage(0);
          else if (typeof stage === "number" && stage < pours.length - 1) setStage(stage + 1);
        }
        applied = true;

      } else if (ev.type === "control") {
        if (ev.action === "start") setPreroll(3);
        else if (ev.action === "pause" || ev.action === "resume") setPaused((p) => !p);
        else if (ev.action === "next") {
          if (stage === "bloom") setStage(0);
          else if (typeof stage === "number") setStage(Math.min(stage + 1, pours.length - 1));
        } else if (ev.action === "done") await markActiveStepDone();
        else if (ev.action === "finish") await onFinish(true);
        applied = true;

      } else if (ev.type === "add_pour") {
        addPour();
        applied = true;
      }
    }

    if (applied) toast("Voice command applied", "success");
  };

  /* ----------------------------- field utils ----------------------------- */
  function applyToActive(fields: Partial<Card>) {
    const clean = (prev: Card) => {
      const out: Partial<Card> = { ...fields };
      if (out.water_g != null) {
        const v = Number(out.water_g);
        out.water_g = Number.isFinite(v) ? roundG(Math.max(0, v)) : prev.water_g;
      }
      if (out.temp_C != null) {
        const t = Number(out.temp_C);
        out.temp_C = Number.isFinite(t) ? clamp(t, 0, 96) : prev.temp_C;
      }
      if (typeof fields.note === "string") {
        const text = fields.note.trim();
        out.note = [prev.note, text].filter(Boolean).join(" ").trim();
      }
      return out;
    };

    if (stage === "bloom") setBloom((b) => ({ ...b, ...clean(b) }));
    else if (typeof stage === "number")
      setPours((list) => {
        const next = [...list];
        next[stage] = { ...next[stage], ...clean(next[stage]) };
        return next;
      });
    if (typeof stage === "number") redistributeFrom(stage);
  }

  async function markActiveStepDone() {
    if (stage === "bloom") {
      await logDone(bloom, "bloom", mmssToMs(bloom.plan_end || undefined));
      setStage(0);
      setActiveStartedAt(null);
    } else if (typeof stage === "number") {
      const card = pours[stage];
      await logDone(card, "pour", mmssToMs(card.plan_end || undefined));
      if (stage < pours.length - 1) {
        setStage(stage + 1);
        setActiveStartedAt(null);
      } else {
        await onFinish(true);
      }
    }
  }

  function addPour() {
    setPours((prev) => {
      if (prev.length >= 5) {
        toast("Max 5 pours reached", "info");
        return prev;
      }
      const idx = prev.length + 1;
      const next: Card[] = [
        ...prev,
        {
          id: `p${idx}`,
          label: `Pour ${idx}`,
          water_g: 0,
          temp_C: Math.min(96, temperature_c),
          pour_style: "spiral",
          plan_start: "",
          plan_end: "",
        },
      ];
      const lastLocked = Math.max(-1, typeof stage === "number" ? stage : -1);
      setTimeout(() => redistributeFrom(lastLocked), 0);
      return next;
    });
  }

  function removePour(i: number) {
    setPours((prev) => {
      if (prev.length <= 1) return prev;
      const next = prev.filter((_, k) => k !== i).map((p, k) => ({ ...p, id: `p${k + 1}`, label: `Pour ${k + 1}` }));
      setTimeout(() => redistributeFrom(Math.min(i - 1, typeof stage === "number" ? stage : -1)), 0);
      return next;
    });
  }

  /* ----------------------------------- UI ----------------------------------- */

  const elapsedS = Math.max(0, Math.round(elapsedMs / 100) / 10).toFixed(1);

  const baseWindowMs = 5 * 60 * 1000; // 5:00
  const maxPlannedEnd = Math.max(
    mmssToMs(bloom.plan_end || "") || 0,
    ...pours.map((p) => mmssToMs(p.plan_end || "") || 0)
  );
  const windowMs = Math.max(baseWindowMs, running ? elapsedMs + 30_000 : maxPlannedEnd || baseWindowMs);

  const plannedSegments: Segment[] = [
    ...(bloom.plan_start && bloom.plan_end
      ? [{ type: "bloom", label: "Bloom (plan)", start_ms: mmssToMs(bloom.plan_start)!, end_ms: mmssToMs(bloom.plan_end)!, cum_g: endsAtBloom } as Segment]
      : []),
    ...pours.flatMap((p, i) =>
      p.plan_start && p.plan_end
        ? [{ type: "pour", label: `${p.label} (plan)`, start_ms: mmssToMs(p.plan_start)!, end_ms: mmssToMs(p.plan_end)!, cum_g: endsAtPour(i) } as Segment]
        : []
    ),
  ];

  const segColor = (t: Segment["type"], planned?: boolean) => {
    if (planned) return t === "bloom" ? "rgba(255,159,67,.35)" : t === "pour" ? "rgba(58,134,255,.35)" : "rgba(154,160,166,.35)";
    return t === "bloom" ? "#ff9f43" : t === "pour" ? "#3a86ff" : "#9aa0a6";
  };

  return (
    <main className="page">
      {/* Header */}
      <div className="card">
        <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
          <div className="col" style={{ gap: 6 }}>
            <h1>{brew_name}</h1>
            <div className="row" style={{ flexWrap: "wrap", gap: 8, fontSize: 13, opacity: 0.9 }}>
              <div>💧 Water: <b>{targetTotal}</b> g</div>
              <div>⚖️ Dose: <b>{isPos(dose_g) ? dose_g : "-"}</b> g</div>
              <div>📐 Ratio: <b>{prettyRatioFrom(dose_g, targetTotal) || (ratioP.ok ? ratioP.pretty : ratio_str || "—")}</b></div>
              <button className="btn secondary" onClick={() => setShowHelp(true)} style={{ marginLeft: 8 }}>?</button>
            </div>
            <div style={{ fontSize: 12, opacity: 0.8 }}>
              Timer: {elapsedS}s {paused && running ? <em>(paused)</em> : null}
            </div>
          </div>

          <div className="col" style={{ alignItems: "flex-end", gap: 6 }}>
            <div className="row" style={{ gap: 6, alignItems: "center" }}>
              <span className="form-label">Target total</span>
              <input
                style={{ width: 92, textAlign: "right" }}
                type="number"
                value={targetTotal}
                onChange={(e) => setTargetTotal(roundG(Math.max(0, Number(e.target.value))))}
              />
              <span className="form-label">g</span>
            </div>
            <div className="row" style={{ gap: 8 }}>
              {!running && preroll === 0 && <button className="btn" onClick={() => setPreroll(3)}>Start</button>}
              {!running && preroll > 0 && <div className="btn secondary">Starting… {preroll}</div>}
              {running && <button className="btn secondary" onClick={() => setPaused((p) => !p)}>{paused ? "Resume" : "Pause"}</button>}
              <button className="btn secondary" onClick={() => onFinish(true)}>Finish now</button>
            </div>
          </div>
        </div>
      </div>

      {/* Plan */}
      <section className="card">
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
          <h2>Plan</h2>
          <button className="btn secondary" onClick={addPour}>+ Add pour</button>
        </div>

        <div className="grid-2col" style={{ marginTop: 12 }}>
          {/* Bloom card */}
          <div className="card">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <h3>Bloom</h3>
              <small className="form-label">Ends at <b>{endsAtBloom}g</b></small>
            </div>

            <div className="grid-2col">
              <FieldText
                label="Start (mm:ss)"
                value={bloom.plan_start || ""} onChange={(v) => setBloom({ ...bloom, plan_start: normalizeMMSSInput(v) })}
              />
              <FieldText
                label="End (mm:ss)"
                value={bloom.plan_end || ""} onChange={(v) => setBloom({ ...bloom, plan_end: normalizeMMSSInput(v) })}
              />
            </div>

            <div className="grid-2col">
              <FieldNumber label="Water (g)" value={bloom.water_g} onChange={(v) => setBloom({ ...bloom, water_g: v ?? 0 })} />
              <FieldSelect label="Pour style" value={bloom.pour_style} options={["center", "spiral", "pulse"]} onChange={(v) => setBloom({ ...bloom, pour_style: v as any })} />
            </div>

            <div className="grid-2col">
              <FieldTemp label="Kettle temp" value={bloom.temp_C} onChange={(v) => setBloom({ ...bloom, temp_C: v })} />
              <FieldText label="Note" value={bloom.note || ""} onChange={(v) => setBloom({ ...bloom, note: v })} />
            </div>

            <div className="row" style={{ gap: 8, marginTop: 8 }}>
              {running && stage === "bloom" && activeStartedAt == null && (
                <button className="btn secondary" onClick={() => startActiveStep(mmssToMs(bloom.plan_start || undefined))}>
                  Start Bloom
                </button>
              )}
              <button
                className="btn"
                disabled={!running || stage !== "bloom"}
                onClick={async () => {
                  const plannedEnd = mmssToMs(bloom.plan_end || "");
                  await logDone(bloom, "bloom", Number.isFinite(plannedEnd) ? plannedEnd : undefined);
                  setStage(0);
                }}
              >
                Mark Bloom done
              </button>
            </div>
          </div>

          {/* Pours */}
          {pours.map((p, i) => (
            <div key={p.id} className="card">
              <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
                <h3>{p.label}</h3>
                <small className="form-label">Ends at <b>{endsAtPour(i)}g</b></small>
              </div>

              <div className="grid-2col">
                <FieldText label="Start (mm:ss)" value={p.plan_start || ""} onChange={(v) => setPours(edit(pours, i, { plan_start: normalizeMMSSInput(v) }))} />
                <FieldText label="End (mm:ss)" value={p.plan_end || ""} onChange={(v) => setPours(edit(pours, i, { plan_end: normalizeMMSSInput(v) }))} />
              </div>

              <div className="grid-2col">
                <FieldNumber
                  label="Water (g)" value={p.water_g}
                  onChange={(v) => { setPours(edit(pours, i, { water_g: v ?? 0 })); redistributeFrom(i); }}
                />
                <FieldSelect label="Pour style" value={p.pour_style} options={["center", "spiral", "pulse"]} onChange={(v) => setPours(edit(pours, i, { pour_style: v as any }))} />
              </div>

              <div className="grid-2col">
                <FieldTemp label="Kettle temp" value={p.temp_C} onChange={(v) => setPours(edit(pours, i, { temp_C: v }))} />
                <FieldText label="Note" value={p.note || ""} onChange={(v) => setPours(edit(pours, i, { note: v }))} />
              </div>

              <div className="row" style={{ gap: 8, marginTop: 8 }}>
                {running && stage === i && activeStartedAt == null && (
                  <button className="btn secondary" onClick={() => startActiveStep(mmssToMs(p.plan_start || undefined))}>
                    Start {p.label}
                  </button>
                )}
                <button
                  className="btn"
                  disabled={!running || stage !== i}
                  onClick={async () => {
                    const plannedEnd = mmssToMs(p.plan_end || "");
                    await logDone(p, "pour", Number.isFinite(plannedEnd) ? plannedEnd : undefined);
                    if (i < pours.length - 1) setStage(i + 1);
                    else await onFinish(true);
                  }}
                >
                  Mark {p.label} done
                </button>
                <button className="btn secondary" onClick={() => removePour(i)}>Remove</button>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Timeline */}
      <section className="card">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2>Timeline</h2>
          <small className="form-label">Orange = Bloom, Blue = Pours, Gray = Drawdown</small>
        </div>

        <div
          className="timeline-shell"
          style={{
            border: "1px solid #242731",
            borderRadius: 10,
            background: "#0f1114",
            padding: 8,
            overflow: "hidden",
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
            {/* planned (faint) */}
            {plannedSegments.map((s, idx) => {
              if (!Number.isFinite(s.start_ms) || !Number.isFinite(s.end_ms!)) return null;
              const leftPct = clamp(((s.start_ms as number) / windowMs) * 100, 0, 100);
              const widthPct = clamp((((s.end_ms as number) - (s.start_ms as number)) / windowMs) * 100, 0.5, 100);
              return (
                <div
                  key={`plan-${idx}`}
                  title={`${s.label}`}
                  style={{
                    position: "absolute",
                    left: `${leftPct}%`,
                    top: 18,
                    height: 28,
                    width: `${widthPct}%`,
                    background: segColor(s.type, true),
                    border: "1px dashed rgba(255,255,255,.25)",
                    borderRadius: 6,
                  }}
                />
              );
            })}

            {/* actual (solid) */}
            {segments.map((s, idx) => {
              if (s.end_ms == null) return null;
              const leftPct = clamp((s.start_ms / windowMs) * 100, 0, 100);
              const widthPct = clamp(((s.end_ms - s.start_ms) / windowMs) * 100, 0.5, 100);
              return (
                <div
                  key={`act-${idx}`}
                  title={`${s.label} • ${msToMMSS(s.end_ms - s.start_ms)}`}
                  style={{
                    position: "absolute",
                    left: `${leftPct}%`,
                    top: 18,
                    height: 28,
                    width: `${widthPct}%`,
                    background: segColor(s.type, false),
                    borderRadius: 6,
                  }}
                />
              );
            })}

            {/* playhead */}
            <div
              style={{
                position: "absolute",
                left: `${clamp((elapsedMs / windowMs) * 100, 0, 100)}%`,
                top: 10,
                bottom: 10,
                width: 2,
                background: "#eaeaea",
                boxShadow: "0 0 6px rgba(255,255,255,0.5)",
              }}
            />
          </div>
          <div className="row" style={{ justifyContent: "space-between", opacity: 0.7, fontSize: 12, marginTop: 4 }}>
            <span>0:00</span>
            <span>{msToMMSS(windowMs)}</span>
          </div>
        </div>
      </section>

      {/* STT mic */}
      <FloatingMic onFinal={handleFinalSTT} />

      {/* Help modal */}
      {showHelp && (
        <div
          role="dialog"
          aria-modal="true"
          className="card"
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.6)",
            display: "grid",
            placeItems: "center",
            zIndex: 2000,
          }}
          onClick={() => setShowHelp(false)}
        >
          <div
            className="card"
            style={{
              width: "min(640px, 94vw)",
              maxHeight: "80vh",
              overflow: "auto",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="row" style={{ justifyContent: "space-between" }}>
              <h2>Voice command tips</h2>
              <button className="btn secondary" onClick={() => setShowHelp(false)}>Close</button>
            </div>

            <table className="form-table" style={{ fontSize: 14 }}>
              <thead>
                <tr><th style={{ width: "30%" }}>Target</th><th>Command</th></tr>
              </thead>
              <tbody>
                <tr><td><b>Start Bloom</b></td><td>“start bloom at 0:35”</td></tr>
                <tr><td><b>End Bloom</b></td><td>“end bloom at 0:50”</td></tr>
                <tr><td><b>Start Pour</b></td><td>“start second pour at 1:10”</td></tr>
                <tr><td><b>End Pour</b></td><td>“end pour 3 at 1:45”</td></tr>
                <tr><td><b>Water amount</b></td><td>“set water to 120 grams” • “water for third pour is 80g”</td></tr>
                <tr><td><b>Remaining water</b></td><td>“use remaining water this pour” • “dump rest in last pour”</td></tr>
                <tr><td><b>Pour style</b></td><td>“style spiral” • “style center” • “use pulse pour”</td></tr>
                <tr><td><b>Kettle temperature</b></td><td>“temperature 94 degrees” • “kettle temp 96”</td></tr>
                <tr><td><b>Notes</b></td><td>“note swirling motion at the start” • “note clarity improving”</td></tr>
                <tr><td><b>Start session</b></td><td>“start” — preroll + timer</td></tr>
                <tr><td><b>Pause/Resume</b></td><td>“pause” / “resume”</td></tr>
                <tr><td><b>Add pour</b></td><td>“add pour”</td></tr>
                <tr><td><b>Next step</b></td><td>“next” — advance</td></tr>
                <tr><td><b>Finish brew</b></td><td>“done” — finish current • “finish” — end brew</td></tr>
              </tbody>
            </table>

            <div className="form-label" style={{ marginTop: 12 }}>
              You can say: <i>“start third pour at 2:05”</i> or <i>“set spiral for pour 2”</i>.
              Ordinals “first/second/third” are supported.
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

/* ----------------------------- field components ---------------------------- */
function FieldNumber({
  label, value, onChange,
}: { label: string; value?: number; onChange: (v: number | undefined) => void }) {
  return (
    <label className="col">
      <span className="form-label">{label}</span>
      <input
        type="number"
        value={value ?? ""} onChange={(e) => onChange(e.target.value === "" ? undefined : Number(e.target.value))}
      />
    </label>
  );
}
function FieldText({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="col">
      <span className="form-label">{label}</span>
      <input
        value={value} onChange={(e) => onChange(e.target.value)}
        onBlur={(e) => {
          const fixed = normalizeMMSSInput(e.target.value);
          if (fixed !== e.target.value) onChange(fixed);
        }}
      />
    </label>
  );
}
function FieldSelect({
  label, value, options, onChange,
}: { label: string; value: any; options: string[]; onChange: (v: string) => void }) {
  return (
    <label className="col">
      <span className="form-label">{label}</span>
      <select value={value ?? ""} onChange={(e) => onChange(e.target.value)}>
        <option value="" disabled>Choose…</option>
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </label>
  );
}
function FieldTemp({ label, value, onChange }: { label: string; value?: number; onChange: (v: number | undefined) => void }) {
  const opts = Array.from({ length: 17 }, (_, i) => 80 + i); // 80..96
  return (
    <label className="col">
      <span className="form-label">{label}</span>
      <select value={(value ?? 96).toString()} onChange={(e) => onChange(Number(e.target.value))}>
        {opts.map((t) => <option key={t} value={t}>{t} °C</option>)}
      </select>
    </label>
  );
}
function edit<T extends object>(arr: T[], idx: number, patch: Partial<T>): T[] {
  const next = [...arr];
  next[idx] = { ...next[idx], ...patch };
  return next;
}
