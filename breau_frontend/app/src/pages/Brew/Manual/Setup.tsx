// src/pages/Brew/Manual/Setup.tsx
import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import useBeansLibrary from "@hooks/useBeansLibrary";
import { useActiveGear } from "@context/ActiveBeanGearProvider";
import { useUser } from "@context/UserProvider";
import { readMirror, mirrorKey } from "@utils/localMirror";

/* --------------------------- math / ratio helpers --------------------------- */

const isPos = (n: number) => Number.isFinite(n) && n > 0;
const toNum = (s: string) => {
  const n = parseFloat(s);
  return isPos(n) ? n : NaN;
};

/** parse "1:15", "1-15", "15", "15.0" -> { ok, r, text } */
function parseRatio(text: string): { ok: boolean; r?: number; text: string } {
  const t = (text || "").trim();
  if (!t) return { ok: false, text: "" };
  if (t.includes(":") || t.includes("/")) {
    const [a, b] = t.replace("/", ":").split(":");
    const aN = parseFloat(a);
    const bN = parseFloat(b);
    if (isPos(aN) && isPos(bN)) return { ok: true, r: bN / aN, text: `1:${(bN / aN).toFixed(2).replace(/\.00$/, "")}` };
    return { ok: false, text: t };
  }
  const r = parseFloat(t);
  if (isPos(r)) return { ok: true, r, text: `1:${String(r)}` };
  return { ok: false, text: t };
}

/** Given any two, compute the third. Returns string values for inputs. */
function recomputeTrio(doseS: string, ratioS: string, waterS: string, changed: "dose" | "ratio" | "water") {
  const haveD = isPos(toNum(doseS));
  const haveW = isPos(toNum(waterS));
  const pr = parseRatio(ratioS);
  const haveR = !!pr.ok;
  const dose = haveD ? toNum(doseS) : NaN;
  const water = haveW ? toNum(waterS) : NaN;
  const r = haveR ? (pr.r as number) : NaN;

  let nextDose = doseS;
  let nextRatio = ratioS;
  let nextWater = waterS;

  if (changed === "dose") {
    if (haveR) nextWater = Number.isFinite(dose) ? String(Math.round(dose * r)) : "";
    else if (haveW && Number.isFinite(dose)) nextRatio = `1:${(water / dose).toFixed(2).replace(/\.00$/, "")}`;
  } else if (changed === "ratio") {
    if (haveD && pr.ok) nextWater = String(Math.round(dose * (pr.r as number)));
    else if (haveW && pr.ok) nextDose = (water / (pr.r as number)).toFixed(1).replace(/\.0$/, "");
  } else if (changed === "water") {
    if (haveD) nextRatio = `1:${(water / dose).toFixed(2).replace(/\.00$/, "")}`;
    else if (haveR && Number.isFinite(r)) nextDose = (water / r).toFixed(1).replace(/\.0$/, "");
  }

  return { dose: nextDose, ratio: nextRatio, water: nextWater };
}

/* ------------------------ grinder scale / µm estimation ------------------------ */

type GrindScale = { type: "numbers"; unit?: string; min: number; max: number; step: number };

function extractGrindScale(grinder: any): GrindScale | null {
  const g = grinder || {};
  const s = g.grind_scale ?? g.scale ?? g.marks ?? g.steps ?? g.grindScale ?? g.dial ?? null;
  if (!s) return null;

  const min = Number(s.min ?? 0);
  const max = Number(s.max ?? 40);
  const step = Number(s.step ?? 1);
  const unit = String(s.unit ?? s.units ?? "marks");
  if (!Number.isFinite(min) || !Number.isFinite(max) || min >= max) return null;
  return { type: "numbers", unit, min, max, step: Number.isFinite(step) && step > 0 ? step : 1 };
}

function lerp(x: number, x0: number, y0: number, x1: number, y1: number) {
  if (x1 === x0) return y0;
  return y0 + ((x - x0) * (y1 - y0)) / (x1 - x0);
}

/**
 * Try common calibration shapes:
 * - calibration.table / points / micron_map / clicks_to_micron: [{setting, micron}] or [setting, micron]
 * - calibration.um_per_mark (+ optional zero_um)
 */
function estimateMicron(grinder: any, setting: number | undefined): number | undefined {
  if (setting == null || !Number.isFinite(setting)) return undefined;
  const g = grinder || {};
  const cal = g.calibration ?? g.cal ?? g.grind_calibration ?? {};

  // 1) Table of points → linear interpolation
  const table = cal.table ?? cal.points ?? g.micron_map ?? g.clicks_to_micron ?? g.clicksToMicron ?? null;
  if (Array.isArray(table) && table.length) {
    const pts = table
      .map((p: any) =>
        Array.isArray(p)
          ? { s: Number(p[0]), u: Number(p[1]) }
          : { s: Number(p.setting ?? p.s ?? p.mark ?? p.value), u: Number(p.micron ?? p.um ?? p.u) }
      )
      .filter((p) => Number.isFinite(p.s) && Number.isFinite(p.u))
      .sort((a, b) => a.s - b.s);

    if (pts.length) {
      let lo = pts[0];
      let hi = pts[pts.length - 1];
      for (let i = 0; i < pts.length - 1; i++) {
        if (setting >= pts[i].s && setting <= pts[i + 1].s) {
          lo = pts[i];
          hi = pts[i + 1];
          break;
        }
      }
      return Math.round(lerp(setting, lo.s, lo.u, hi.s, hi.u));
    }
  }

  // 2) Linear: um_per_mark (+ zero_um)
  const per = Number(cal.um_per_mark ?? g.um_per_mark ?? g.micron_per_click ?? NaN);
  const zero = Number(cal.zero_um ?? g.zero_um ?? 0);
  if (Number.isFinite(per) && per > 0) return Math.round(zero + setting * per);

  return undefined;
}

/* --------------------------- gear snapshot (fallback) --------------------------- */

function useActiveGearSnapshot() {
  const { userId } = useUser();
  const { active: ctx } = useActiveGear();

  const [fallback, setFallback] = useState<any>(null);
  useEffect(() => {
    try {
      const fromMirror = readMirror(mirrorKey.gearActive(userId), null as any);
      if (fromMirror) setFallback(fromMirror);
    } catch {
      try {
        const raw = localStorage.getItem(`breau.activeGear.${userId}`);
        if (raw) setFallback(JSON.parse(raw));
      } catch {}
    }
  }, [userId]);

  const src = ctx || fallback || {};
  const brewer = src?.brewer?.name ?? src?.brewer_name ?? src?.brewer ?? null;
  const grinderBrand = src?.grinder?.brand ?? src?.grinder_brand ?? null;
  const grinderModel = src?.grinder?.model ?? src?.grinder_model ?? null;
  const grinder =
    grinderBrand && grinderModel
      ? `${grinderBrand} ${grinderModel}`
      : src?.grinder?.name ?? src?.grinder ?? null;
  const water = src?.water?.name ?? src?.water_name ?? src?.water ?? null;

  const display = [brewer, grinder, water].filter(Boolean).join(" • ") || "—";

  return {
    display,
    brewer,
    grinder,
    grinder_brand: grinderBrand ?? undefined,
    grinder_model: grinderModel ?? undefined,
    water,
    raw: typeof src === "object" ? src : undefined,
  };
}

/* -------------------------------- component -------------------------------- */

export default function ManualSetup() {
  const nav = useNavigate();
  const gearSnapshot = useActiveGearSnapshot();
  const { items: beans } = useBeansLibrary();

  const [dose, setDose] = useState("");
  const [ratio, setRatio] = useState("");
  const [water, setWater] = useState("");
  const [grind, setGrind] = useState("");
  const [beanId, setBeanId] = useState<string>("");

  // Grinder-aware grind UI
  const grinderRaw = useMemo(() => gearSnapshot.raw?.grinder ?? null, [gearSnapshot.raw]);
  const grindScale = useMemo(() => extractGrindScale(grinderRaw), [grinderRaw]);
  const [grindSetting, setGrindSetting] = useState<number | "">("");
  const grindUnit = grindScale?.unit ?? "marks";
  const micron = useMemo(
    () => (typeof grindSetting === "number" ? estimateMicron(grinderRaw, grindSetting) : undefined),
    [grinderRaw, grindSetting]
  );
  const autoGrindLabel = useMemo(() => {
    const base = gearSnapshot.grinder ? `${gearSnapshot.grinder}` : "Grinder";
    const marks = typeof grindSetting === "number" ? `${grindSetting} ${grindUnit}` : (grind || "").trim();
    const um = micron != null ? ` (~${micron} µm)` : "";
    return marks ? `${base} ≈ ${marks}${um}` : "";
  }, [gearSnapshot.grinder, grindSetting, grindUnit, micron, grind]);
  const grindPlaceholder = useMemo(
    () =>
      gearSnapshot.grinder
        ? `e.g., "22 clicks on ${gearSnapshot.grinder}"`
        : `e.g., "22 clicks"`,
    [gearSnapshot.grinder]
  );
  const autoLabelPlaceholder = useMemo(() => autoGrindLabel || grindPlaceholder, [autoGrindLabel, grindPlaceholder]);

  function onDose(v: string) {
    const next = recomputeTrio(v, ratio, water, "dose");
    setDose(next.dose);
    setRatio(next.ratio);
    setWater(next.water);
  }
  function onRatio(v: string) {
    const next = recomputeTrio(dose, v, water, "ratio");
    setDose(next.dose);
    setRatio(next.ratio);
    setWater(next.water);
  }
  function onWater(v: string) {
    const next = recomputeTrio(dose, ratio, v, "water");
    setDose(next.dose);
    setRatio(next.ratio);
    setWater(next.water);
  }

  const validDose = isPos(toNum(dose));
  const validRatio = parseRatio(ratio).ok;
  const validWater = isPos(toNum(water));
  const validCount = [validDose, validRatio, validWater].filter(Boolean).length;

  // pick bean snapshot for later summary (non-blocking)
  const beanSnapshot = useMemo(() => {
    const b = (beans ?? []).find((x) => String(x.id) === String(beanId));
    if (!b) return null;
    return {
      id: b.id,
      name: b.name ?? null,
      roaster: b.roaster ?? null,
      origin: b.origin ?? null,
      variety: b.variety ?? null,
      process: b.process ?? null,
    };
  }, [beanId, beans]);

  function start() {
    const three = recomputeTrio(dose, ratio, water, "dose");

    // Build a friendly label if user didn’t type one
    const settingNum = typeof grindSetting === "number" ? grindSetting : undefined;
    const label = (grind && grind.trim()) || (settingNum != null ? autoGrindLabel : "");

    nav("/brew/manual/log", {
      state: {
        bean_id: beanId || null,
        bean_snapshot: beanSnapshot,
        gear_snapshot: gearSnapshot,
        setup: {
          dose: three.dose,
          ratio: three.ratio,
          total: three.water, // Log expects "total"

          // keep legacy text field for compatibility
          grind: label,

          // NEW: structured fields so Log → useBrewSession.finish() → Summary can render perfectly
          grind_label: label || undefined,
          grind_setting: settingNum,
          grind_target_micron: micron,
          grind_scale: grindScale || undefined,
        },
      },
    });
  }

  return (
    <main className="max-w-5xl mx-auto p-4">
      <div className="card col">
        <h2>Manual Setup</h2>
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
          <div className="col" style={{ gap: 4 }}>
            <div className="text-sm opacity-80">Active gear</div>
            <div>{gearSnapshot.display}</div>
          </div>
          <button className="btn" onClick={() => nav("/profile/gear")}>Change</button>
        </div>
      </div>

      <section className="card col" style={{ marginTop: 12 }}>
        <h3>1) Pick a bean</h3>
        <select
          className="input"
          value={beanId}
          onChange={(e) => setBeanId(e.target.value)}
        >
          <option value="">{beans?.length ? "Select a bean" : "No beans yet"}</option>
          {(beans ?? []).map((b) => (
            <option key={b.id} value={String(b.id)}>
              {b.name || "Unnamed"} {b.roaster ? `• ${b.roaster}` : ""} {b.origin ? `• ${b.origin}` : ""}
            </option>
          ))}
        </select>

        <div className="row" style={{ gap: 8, marginTop: 8 }}>
          <button className="btn" onClick={() => nav("/profile/beans")}>Manage beans</button>
          <button className="btn" onClick={() => nav("/profile/beans?scan=1")}>Scan label</button>
        </div>
      </section>

      <section className="card col" style={{ marginTop: 12 }}>
        <h3>2) Recipe</h3>

        <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
          <label className="col" style={{ flex: 1, minWidth: 220 }}>
            <span className="form-label">Dose (g)</span>
            <input
              className="input"
              placeholder="e.g., 20"
              inputMode="decimal"
              value={dose}
              onChange={(e) => onDose(e.target.value)}
            />
          </label>

          <label className="col" style={{ flex: 1, minWidth: 220 }}>
            <span className="form-label">Ratio</span>
            <input
              className="input"
              placeholder="e.g., 1:15"
              value={ratio}
              onChange={(e) => onRatio(e.target.value)}
            />
          </label>

          <label className="col" style={{ flex: 1, minWidth: 220 }}>
            <span className="form-label">Water (g)</span>
            <input
              className="input"
              placeholder="e.g., 300"
              inputMode="decimal"
              value={water}
              onChange={(e) => onWater(e.target.value)}
            />
          </label>
        </div>

        {/* Grind (smart when grinder has a numeric scale) */}
        <div className="col" style={{ marginTop: 10 }}>
          <span className="form-label">Grind</span>

          {grindScale ? (
            <>
              <div className="row" style={{ gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
                <label className="col" style={{ minWidth: 180 }}>
                  <span className="form-label">Setting ({grindUnit})</span>
                  <input
                    className="input"
                    type="number"
                    min={grindScale.min}
                    max={grindScale.max}
                    step={grindScale.step}
                    value={grindSetting === "" ? "" : String(grindSetting)}
                    placeholder={`${grindScale.min} - ${grindScale.max}`}
                    onChange={(e) => {
                      const v = e.target.value === "" ? "" : Number(e.target.value);
                      setGrindSetting(v === "" ? "" : Number.isFinite(v) ? v : "");
                    }}
                  />
                </label>

                <label className="col" style={{ flex: 1, minWidth: 260 }}>
                  <span className="form-label">Quick adjust</span>
                  <input
                    className="input"
                    type="range"
                    min={grindScale.min}
                    max={grindScale.max}
                    step={grindScale.step}
                    value={grindSetting === "" ? grindScale.min : Number(grindSetting)}
                    onChange={(e) => setGrindSetting(Number(e.target.value))}
                  />
                  <div className="text-sm opacity-80" style={{ marginTop: 6 }}>
                    Estimated: <b>{micron ?? "—"}</b>{micron != null ? " µm" : ""}
                  </div>
                </label>
              </div>

              <label className="col" style={{ marginTop: 8 }}>
                <span className="form-label">Grind label (optional)</span>
                <input
                  className="input"
                  placeholder={autoLabelPlaceholder}
                  value={grind}
                  onChange={(e) => setGrind(e.target.value)}
                />
                <div className="text-xs opacity-70" style={{ marginTop: 4 }}>
                  Suggested: {autoGrindLabel || "—"}
                </div>
              </label>
            </>
          ) : (
            // Fallback: free text only
            <label className="col">
              <input
                className="input"
                placeholder={grindPlaceholder}
                value={grind}
                onChange={(e) => setGrind(e.target.value)}
              />
              <div className="text-xs opacity-70" style={{ marginTop: 4 }}>
                Tip: choose a grinder in Profile to unlock a clickable scale and µm estimate.
              </div>
            </label>
          )}
        </div>
      </section>

      <div className="row" style={{ gap: 8, marginTop: 12 }}>
        <button
          className="btn btn-primary"
          onClick={start}
          disabled={validCount < 2}
        >
          Start manual brew
        </button>
      </div>
    </main>
  );
}
