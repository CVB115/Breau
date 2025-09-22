import React, { useMemo } from "react";

export default function StarRating({
  value, onChange, max = 5, step = 0.5, size = 28, id
}: { value: number; onChange: (v: number) => void; max?: number; step?: 0.5 | 1; size?: number; id?: string }) {
  const stars = useMemo(() => Array.from({ length: max }, (_, i) => i + 1), [max]);

  function pctFromClientX(e: React.MouseEvent<HTMLDivElement>) {
    const rect = (e.currentTarget as HTMLDivElement).getBoundingClientRect();
    const pct = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
    return pct;
  }
  function snap(v: number) {
    const snapped = Math.round(v / step) * step;
    return Math.min(max, Math.max(0, snapped));
  }

  return (
    <div
      id={id}
      role="slider"
      aria-label="Overall rating"
      aria-valuemin={0} aria-valuemax={max} aria-valuenow={value}
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "ArrowRight" || e.key === "ArrowUp") onChange(Math.min(max, value + step));
        if (e.key === "ArrowLeft"  || e.key === "ArrowDown") onChange(Math.max(0, value - step));
      }}
      onClick={(e) => {
        const pct = pctFromClientX(e);
        onChange(snap(pct * max));
      }}
      style={{ display:"inline-flex", gap:4, cursor:"pointer" }}
    >
      {stars.map(i => {
        const full = i <= Math.floor(value);
        const half = !full && i - value === 0.5;
        return (
          <div key={i} style={{ position:"relative", width:size, height:size }}>
            {/* base outline */}
            <StarOutline size={size} opacity={0.28} />
            {/* fill */}
            {full && <StarFill size={size} />}
            {half && (
              <div style={{ width:"50%", overflow:"hidden", position:"absolute", inset:0 }}>
                <StarFill size={size} />
              </div>
            )}
          </div>
        );
      })}
      <span style={{ marginLeft:8, opacity:.85 }}>{value.toFixed(1)} / {max}</span>
    </div>
  );
}

function StarFill({ size }: { size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" style={{ fill:"#3a86ff" }}>
      <path d="M12 17.27 18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/>
    </svg>
  );
}
function StarOutline({ size, opacity=1 }: { size:number; opacity?:number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" style={{ fill:"none", stroke:"#eaeaea", opacity }}>
      <path d="M22 9.24l-7.19-.62L12 2 9.19 8.62 2 9.24l5.46 4.73L5.82 21 12 17.27 18.18 21l-1.64-7.03L22 9.24z"
            strokeWidth="1.5"/>
    </svg>
  );
}
