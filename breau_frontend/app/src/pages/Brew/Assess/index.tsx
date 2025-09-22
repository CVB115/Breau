// src/pages/Brew/Assess/index.tsx
import React, { useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import useBrewHistory from "@hooks/useBrewHistory";


/* ---------- tiny http helper ---------- */
async function postJSON(path: string, body: any) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text().catch(() => res.statusText));
  try { return await res.json(); } catch { return null; }
}


function resolveLocalIdOrSelf(id?: string | null, historyArr: any[] = []) {
  if (!id) return id ?? null;
  const arr = Array.isArray(historyArr) ? historyArr : [];
  const hit = arr.find((x: any) =>
    x.id === id ||
    x.session_id === id ||
    x.server_session_id === id ||
    (Array.isArray(x.aliases) && x.aliases.includes(id))
  );
  return hit?.id || id;
}



type NavState = {
  session_id: string;
  // optional incoming name to prefill (from Guide/Log/Setup)
  brew_name?: string;
  type?: "manual" | "suggested";
};

const TRAITS = ["acidity", "sweetness", "bitterness", "body", "clarity"] as const;

/* ---------- StarRating (0–5, 0.5 steps) ---------- */
function StarRating({
  value, onChange, step = 0.5, size = 24, max = 5,
}: { value: number; onChange: (v: number) => void; step?: 0.5 | 1; size?: number; max?: number }) {
  const stars = Array.from({ length: max }, (_, i) => i + 1);
  const set = (v: number) => onChange(Math.max(0, Math.min(max, v)));

  return (
    <div className="row" style={{ gap: 6 }} aria-label="Overall rating">
      {stars.map((n) => {
        const filled = value >= n;
        const half = !filled && value >= n - 0.5;
        return (
          <button
            key={n}
            type="button"
            className="btn secondary"
            style={{
              padding: 0, width: size + 6, height: size + 6, display: "grid", placeItems: "center",
              borderRadius: 8,
            }}
            onClick={(e) => {
              const rect = (e.currentTarget as HTMLButtonElement).getBoundingClientRect();
              const leftHalf = (e.clientX - rect.left) < rect.width / 2;
              if (step === 0.5) set(leftHalf ? n - 0.5 : n);
              else set(n);
            }}
            onKeyDown={(e) => {
              if (e.key === "ArrowLeft") set(value - step);
              if (e.key === "ArrowRight") set(value + step);
            }}
            aria-pressed={filled || half}
            title={`${value.toFixed(1)} / ${max}`}
          >
            <svg width={size} height={size} viewBox="0 0 24 24">
              <path d="M12 2l3.09 6.26L22 9.27l-5 4.88L18.18 22 12 18.56 5.82 22 7 14.15l-5-4.88 6.91-1.01L12 2z"
                    fill="none" stroke="#9aa0a6" strokeWidth="1.2"/>
              {filled && (
                <path d="M12 2l3.09 6.26L22 9.27l-5 4.88L18.18 22 12 18.56 5.82 22 7 14.15l-5-4.88 6.91-1.01L12 2z"
                      fill="#3a86ff"/>
              )}
              {half && (
                <>
                  <clipPath id={`half-${n}`}>
                    <rect x="0" y="0" width="12" height="24"/>
                  </clipPath>
                  <path d="M12 2l3.09 6.26L22 9.27l-5 4.88L18.18 22 12 18.56 5.82 22 7 14.15l-5-4.88 6.91-1.01L12 2z"
                        fill="#3a86ff" clipPath={`url(#half-${n})`}/>
                </>
              )}
            </svg>
          </button>
        );
      })}
    </div>
  );
}

/* ---------- Rectangular slider with pips (0.1 + 1.0) ---------- */
function SnapSlider({
  value, onChange, min = 0, max = 5, step = 0.1, majorStep = 1, label,
}: {
  value: number; onChange: (v: number) => void;
  min?: number; max?: number; step?: number; majorStep?: number; label?: string;
}) {
  const pct = (value - min) / (max - min);

  // pip spacing in %
  const thin = (step / (max - min)) * 100;
  const thick = (majorStep / (max - min)) * 100;

  return (
    <div className="col" style={{ gap: 6 }}>
      {label && <div className="form-label">{label}</div>}

      <div className="col" style={{ position: "relative", gap: 0 }}>
        {/* track */}
        <div
          style={{
            height: 10,
            width: "100%",
            background: "#151821",
            border: "1px solid #242731",
            borderRadius: 6,
            position: "relative",
            overflow: "hidden",
          }}
        >
          {/* pips: thin (0.1) + thick (1.0) */}
          <div
            style={{
              position: "absolute", inset: 0,
              backgroundImage: `
                repeating-linear-gradient(90deg,
                  rgba(255,255,255,0.10) 0, rgba(255,255,255,0.10) 1px,
                  transparent 1px, transparent ${thin}%),
                repeating-linear-gradient(90deg,
                  rgba(255,255,255,0.22) 0, rgba(255,255,255,0.22) 2px,
                  transparent 2px, transparent ${thick}%)
              `,
            }}
          />
          {/* fill */}
          <div
            style={{
              position: "absolute", top: 0, left: 0, bottom: 0,
              width: `${pct * 100}%`,
              background: "#3a86ff",
              opacity: 0.35,
            }}
          />
        </div>

        {/* invisible native range to handle input & snapping */}
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => {
            const v = Math.round(parseFloat(e.target.value) * 10) / 10;
            onChange(v);
          }}
          style={{
            position: "absolute", inset: 0, width: "100%", height: 10,
            opacity: 0, cursor: "pointer",
          }}
          aria-label={label || "intensity"}
        />

        {/* thumb */}
        <div
          style={{
            position: "absolute",
            top: -6,
            left: `calc(${pct * 100}% - 10px)`,
            width: 20,
            height: 20,
            background: "#fbbf24",
            border: "2px solid #0b0e14",
            borderRadius: 10,
            boxShadow: "0 1px 3px rgba(0,0,0,0.5)",
            pointerEvents: "none",
          }}
        />
      </div>

      <div className="row" style={{ justifyContent: "space-between", fontSize: 12, opacity: 0.8 }}>
        <span>Low</span><span>Med</span><span>High</span>
      </div>
    </div>
  );
}

/* --------------------------------- Page ---------------------------------- */
export default function Assess() {
  const nav = useNavigate();
  const { state } = useLocation();
  const { session_id, brew_name: incomingName } = (state || {}) as NavState;
  
  const { sessions: history, patch } = useBrewHistory() as any;


  // NEW: user-editable brew name (lands in Summary header)
  const [brewName, setBrewName] = useState<string>(incomingName || "");

  const [overall, setOverall] = useState<number>(4.5);
  const [traits, setTraits] = useState<Record<string, number>>(
    () => Object.fromEntries(TRAITS.map((t) => [t, 2.5])) as Record<string, number>
  );
  const [traitNotes, setTraitNotes] = useState<Record<string, string>>(
    () => Object.fromEntries(TRAITS.map((t) => [t, ""])) as Record<string, string>
  );
  const [notes, setNotes] = useState<string>("");
  const [comments, setComments] = useState<string>("");

  const payload = useMemo(
    () => ({
      overall_rating: overall,
      ...Object.fromEntries(Object.entries(traits)),
      notes: notes.split(",").map((s) => s.trim()).filter(Boolean),
      comments,
      trait_comments: traitNotes,
    }),
    [overall, traits, notes, comments, traitNotes]
  );

  async function submit() {
    try {
      // 1) Optional: send trait breakdown to your feedback endpoint
      if (session_id && !String(session_id).startsWith("local-")) {
        try {
          await postJSON(`/api/feedback/${encodeURIComponent(session_id)}`, payload);
        } catch (e) {
          // non-fatal
          console.warn("feedback send failed", e);
        }

        // 2) Canonical finish: integer rating, optional notes (join notes+comments)
        const intRating = Math.round(overall); // server expects INT
        const mergedNotes =
          [brewName && `(Brew name: ${brewName})`, notes && `Notes: ${notes}`, comments && `Comments: ${comments}`]
            .filter(Boolean)
            .join(" • ");

        try {
          await postJSON(`/api/brew/finish`, {
            session_id,
            rating: intRating,
            notes: mergedNotes || undefined,
          });
        } catch (e) {
          console.warn("finish send failed", e);
        }
      }
    } finally {
      // 3) Patch local history: set feedback and updated brew_name for Summary
      if (session_id) {
        const fb = {
          ...payload,
          // keep both granular traits and the int rating we sent server-side
          overall_rating_int: Math.round(overall),
        };
        patch(session_id, {
          feedback: fb,
          summary: { brew_name: brewName }, // <-- store it so Summary can read it
        } as any);
      }
      
      // 4) Go to Summary with the best-matching LOCAL id
      const navId = resolveLocalIdOrSelf(session_id,history);
      nav("/brew/summary", { state: { session_id: navId, brew_name: brewName } });
    }
  }

  return (
    <main className="page">
      {/* Name card */}
      <section className="card col" style={{ gap: 10 }}>
        <h2>Name your brew</h2>
        <div className="row" style={{ gap: 10, alignItems: "center" }}>
          <input
            placeholder="e.g. Two pours, 1:15 V60"
            value={brewName}
            onChange={(e) => setBrewName(e.target.value)}
            style={{ flex: 1 }}
          />
          <small className="form-label" style={{ whiteSpace: "nowrap" }}>
            (Optional — shows in Summary & History)
          </small>
        </div>
      </section>

      {/* Overall */}
      <section className="card">
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
          <h2>Overall</h2>
          <div className="form-label">{overall.toFixed(1)} / 5</div>
        </div>
        <StarRating value={overall} onChange={setOverall} />
      </section>

      {/* Stacked trait cards */}
      {TRAITS.map((t) => (
        <section key={t} className="card col" style={{ gap: 10 }}>
          <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
            <h3 style={{ textTransform: "capitalize" }}>{t}</h3>
            <div className="form-label">{traits[t].toFixed(1)}</div>
          </div>

          <SnapSlider
            value={traits[t]}
            onChange={(v) => setTraits((prev) => ({ ...prev, [t]: v }))}
            min={0}
            max={5}
            step={0.1}
            majorStep={1}
            label={`${t[0].toUpperCase() + t.slice(1)} intensity`}
          />

          <label className="col">
            <span className="form-label" style={{ textTransform: "capitalize" }}>
              {t} comments (optional)
            </span>
            <textarea
              rows={3}
              value={traitNotes[t]}
              onChange={(e) => setTraitNotes((p) => ({ ...p, [t]: e.target.value }))}
              style={{ width: "100%" }}
            />
          </label>
        </section>
      ))}

      {/* Notes + General comments */}
      <section className="card col" style={{ gap: 12 }}>
        <div className="row" style={{ gap: 12, alignItems: "flex-start" }}>
          <label className="col" style={{ flex: 1 }}>
            <span className="form-label">Notes (comma separated)</span>
            <input
              placeholder="apricot, jasmine, cocoa…"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </label>
          <label className="col" style={{ flex: 1 }}>
            <span className="form-label">General comments</span>
            <textarea
              rows={4}
              placeholder="Anything you noticed about the cup."
              value={comments}
              onChange={(e) => setComments(e.target.value)}
            />
          </label>
        </div>

        <div className="row" style={{ gap: 8 }}>
          <button className="btn" onClick={submit}>Save &amp; finish</button>
          <button className="btn secondary" onClick={() => nav(-1)}>Back</button>
        </div>
      </section>
    </main>
  );
}
