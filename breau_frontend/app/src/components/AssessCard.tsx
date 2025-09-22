import React from "react";
import SnapSlider from "./SnapSlider";

export function AssessCard({
  title, value, onChange, note, onNoteChange,
}: {
  title: string;
  value: number; onChange:(v:number)=>void;
  note?: string; onNoteChange:(v:string)=>void;
}) {
  return (
    <div className="card" style={{ padding:16 }}>
      <h3 style={{ marginBottom:8 }}>{title}</h3>
      <SnapSlider label={`${title} intensity`} value={value} onChange={onChange} />
      <label className="col" style={{ marginTop:12 }}>
        <span className="form-label">{title} comments (optional)</span>
        <textarea rows={3} value={note || ""} onChange={(e)=>onNoteChange(e.target.value)} />
      </label>
    </div>
  );
}
