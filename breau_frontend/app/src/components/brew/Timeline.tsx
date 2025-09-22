import React from "react";

export type TimelineBlock = {
  label: string;            // e.g. "Bloom 60g", "Pour to 180g"
  startMs: number;          // inclusive
  endMs: number;            // exclusive
  tone?: "bloom" | "pour" | "end";
};

type Props = {
  durationMs: number;       // total span (e.g., last event or now)
  playheadMs?: number;      // current time marker
  blocks: TimelineBlock[];  // shaded segments
  height?: number;          // px
};

export default function Timeline({
  durationMs,
  playheadMs = 0,
  blocks,
  height = 56,
}: Props) {
  const clamp = (v: number) => Math.max(0, Math.min(v, durationMs));
  const pct = (ms: number) => (durationMs <= 0 ? 0 : (ms / durationMs) * 100);

  return (
    <div style={{
      border: "1px solid #242731",
      borderRadius: 12,
      padding: 8,
      background: "#0f1114",
    }}>
      {/* mm:ss ruler */}
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, opacity: 0.7, marginBottom: 6 }}>
        <span>0:00</span>
        <span>{formatMs(durationMs)}</span>
      </div>

      <div style={{ position: "relative", height, background: "#0b0d11", borderRadius: 8, overflow: "hidden" }}>
        {/* Blocks */}
        {blocks.map((b, i) => {
          const s = clamp(b.startMs), e = clamp(b.endMs);
          const left = pct(s);
          const width = Math.max(0, pct(e) - pct(s));
          const color =
            b.tone === "bloom" ? "rgba(43,122,82,0.25)" :
            b.tone === "end"   ? "rgba(220,80,80,0.25)" :
                                 "rgba(80,130,220,0.25)";
          return (
            <div key={i} style={{
              position: "absolute", left: `${left}%`, width: `${width}%`,
              top: 0, bottom: 0, background: color, borderRight: "1px solid #242731"
            }} title={b.label}/>
          );
        })}

        {/* Playhead */}
        <div style={{
          position: "absolute",
          left: `${pct(clamp(playheadMs))}%`,
          top: 0, bottom: 0,
          width: 2,
          background: "#ffffff",
          opacity: 0.9,
          boxShadow: "0 0 6px rgba(255,255,255,0.5)"
        }} />
      </div>

      {/* Labels */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8, fontSize: 12, opacity: 0.8 }}>
        {blocks.map((b, i) => (
          <div key={i} style={{ background: "#0b0d11", border: "1px solid #242731", borderRadius: 8, padding: "4px 8px" }}>
            {b.label} · {formatMs(b.startMs)}–{formatMs(b.endMs)}
          </div>
        ))}
      </div>
    </div>
  );
}

function formatMs(ms: number) {
  const s = Math.max(0, Math.round(ms / 1000));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${r.toString().padStart(2, "0")}`;
}
