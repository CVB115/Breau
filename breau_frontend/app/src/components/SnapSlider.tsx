import React from "react";

export default function SnapSlider({
  label, value, onChange, min=1, max=5, step=0.1, id
}: { label: string; value: number; onChange:(v:number)=>void; min?:number; max?:number; step?:number; id?:string }) {
  function clamp(v:number){ return Math.max(min, Math.min(max, v)); }
  function snap(v:number){
    return Math.round(v/step)*step;
  }
  return (
    <div className="col" style={{ gap:6 }}>
      <div className="row" style={{ justifyContent:"space-between" }}>
        <span className="form-label">{label}</span>
        <span style={{ opacity:.85 }}>{value.toFixed(1)}</span>
      </div>
      <input
        id={id}
        type="range"
        min={min} max={max} step={step}
        value={value}
        onChange={(e)=> onChange(clamp(snap(parseFloat(e.target.value))))}
      />
      <div className="row" style={{ justifyContent:"space-between", fontSize:12, opacity:.7 }}>
        <span>Low</span><span>Med</span><span>High</span>
      </div>
    </div>
  );
}
