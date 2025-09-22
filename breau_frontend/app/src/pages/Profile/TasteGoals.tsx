// src/pages/Profile/TasteGoals.tsx
import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useUser } from "@context/UserProvider";
import { readMirror, writeMirror } from "@utils/localMirror";

// --- Types ---------------------------------------------------------------
type TasteGoals = {
  strength: "light" | "medium" | "strong";
  body: "light" | "medium" | "heavy";
  acidity: "low" | "medium" | "high";
  sweetness: "low" | "medium" | "high";
  notes: string; // comma-separated
};

type GoalsPreset = {
  id: string;
  name: string;
  goals: TasteGoals;
  created_at?: string;
  updated_at?: string;
};

// NL rendering used by the Goals picker and backend prompt
function goalsToText(g: Partial<TasteGoals>): string {
  const parts: string[] = [];
  if (g.strength) parts.push(`${g.strength} strength`);
  if (g.body) parts.push(`${g.body} body`);
  if (g.acidity) parts.push(`${g.acidity} acidity`);
  if (g.sweetness) parts.push(`${g.sweetness} sweetness`);
  const base = parts.join(", ");
  const notes = g.notes?.trim() ? `; notes: ${g.notes.trim()}` : "";
  return (base + notes).trim();
}

function uid() {
  return (
    globalThis.crypto?.randomUUID?.() ??
    `id-${Date.now()}-${Math.random().toString(36).slice(2)}`
  );
}

export default function TasteGoalsPage() {
  const { userId } = useUser();
  const nav = useNavigate();

  // Presets library
  const KEY = useMemo(() => `breau.goalPresets.${userId}`, [userId]);
  const [presets, setPresets] = useState<GoalsPreset[]>([]);

  // Add/Edit panel state
  const [panelOpen, setPanelOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [formName, setFormName] = useState("");
  const [formGoals, setFormGoals] = useState<TasteGoals>({
    strength: "medium",
    body: "medium",
    acidity: "medium",
    sweetness: "medium",
    notes: "",
  });

  // Load/Save helpers (local-first)
  function loadPresets() {
    try {
      const fromMirror = readMirror<GoalsPreset[]>(KEY, null as any);
      if (Array.isArray(fromMirror)) {
        setPresets(fromMirror);
        return;
      }
    } catch {}
    try {
      const raw = localStorage.getItem(KEY);
      const arr = raw ? JSON.parse(raw) : [];
      setPresets(Array.isArray(arr) ? arr : []);
    } catch {
      setPresets([]);
    }
  }
  function savePresets(next: GoalsPreset[]) {
    setPresets(next);
    try {
      writeMirror(KEY, next);
    } catch {
      localStorage.setItem(KEY, JSON.stringify(next));
    }
  }

  useEffect(() => {
    loadPresets();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [KEY]);

  const total = presets.length;

  // UI helpers
  function openNew() {
    setEditId(null);
    setFormName("");
    setFormGoals({
      strength: "medium",
      body: "medium",
      acidity: "medium",
      sweetness: "medium",
      notes: "",
    });
    setPanelOpen(true);
  }
  function openEdit(p: GoalsPreset) {
    setEditId(p.id);
    setFormName(p.name);
    setFormGoals({ ...p.goals });
    setPanelOpen(true);
  }
  function onChange<K extends keyof TasteGoals>(k: K, v: TasteGoals[K]) {
    setFormGoals((g) => ({ ...g, [k]: v }));
  }
  function savePreset() {
    const name = formName.trim() || "Untitled preset";
    const now = new Date().toISOString();
    if (editId) {
      savePresets(
        presets.map((p) =>
          p.id === editId ? { ...p, name, goals: { ...formGoals }, updated_at: now } : p
        )
      );
    } else {
      const item: GoalsPreset = {
        id: uid(),
        name,
        goals: { ...formGoals },
        created_at: now,
        updated_at: now,
      };
      savePresets([item, ...presets]);
    }
    setPanelOpen(false);
    setEditId(null);
  }
  function removePreset(id: string) {
    if (!confirm("Delete this preset?")) return;
    savePresets(presets.filter((p) => p.id !== id));
  }

  // ---- IMPORTANT: Route to the existing Goals route
  // We navigate to /brew/suggest (not /brew/suggest/goals) and pass the NL text in state.
  function useInSuggested(preset: GoalsPreset) {
    const preview = goalsToText(preset.goals);
    nav("/brew/suggest", { state: { goals_text: preview } });
  }

  return (
    <main className="page">
      {/* Header */}
      <div className="card col">
        <h2>Taste &amp; Goals</h2>
        <div className="row" style={{ gap: 8 }}>
          <button className="btn" onClick={openNew}>New preset</button>
          <div className="spacer" />
          <span style={{ fontSize: 12, opacity: 0.8 }}>
            {total} preset{total === 1 ? "" : "s"}
          </span>
        </div>
      </div>

      {/* Presets inventory */}
      <div className="card col">
        {presets.length === 0 && (
          <span style={{ opacity: 0.8 }}>No presets yet. Create one to get started.</span>
        )}

        <div className="col" style={{ gap: 10 }}>
          {presets.map((p) => {
            const preview = goalsToText(p.goals);
            return (
              <div
                key={p.id}
                className="row"
                style={{ justifyContent: "space-between", padding: "6px 0", alignItems: "center" }}
              >
                <div className="col" style={{ gap: 2 }}>
                  <strong>{p.name}</strong>
                  <div style={{ fontSize: 12, opacity: 0.75 }}>{preview || "—"}</div>
                </div>

                <div className="row" style={{ gap: 8 }}>
                  <button className="btn secondary" onClick={() => openEdit(p)}>
                    Edit
                  </button>
                  <button className="btn secondary" onClick={() => removePreset(p.id)}>
                    Delete
                  </button>
                  <button className="btn" onClick={() => useInSuggested(p)}>
                    Use in Suggested
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Add/Edit panel */}
      {panelOpen && (
        <div className="card col">
          <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
            <h3>{editId ? "Edit preset" : "New preset"}</h3>
            <button
              className="btn secondary"
              onClick={() => {
                setPanelOpen(false);
                setEditId(null);
              }}
            >
              Close
            </button>
          </div>

          {/* Name */}
          <label className="col">
            <span className="form-label">Preset name</span>
            <input
              placeholder="e.g., Bright & Juicy"
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
            />
          </label>

          {/* Row 1: Strength + Body */}
          <div className="row" style={{ gap: 8 }}>
            <label className="col" style={{ flex: 1 }}>
              <span className="form-label">Strength</span>
              <select
                value={formGoals.strength}
                onChange={(e) => onChange("strength", e.target.value as TasteGoals["strength"])}
              >
                <option value="light">Light</option>
                <option value="medium">Medium</option>
                <option value="strong">Strong</option>
              </select>
            </label>

            <label className="col" style={{ flex: 1 }}>
              <span className="form-label">Body</span>
              <select
                value={formGoals.body}
                onChange={(e) => onChange("body", e.target.value as TasteGoals["body"])}
              >
                <option value="light">Light</option>
                <option value="medium">Medium</option>
                <option value="heavy">Heavy</option>
              </select>
            </label>
          </div>

          {/* Row 2: Acidity + Sweetness */}
          <div className="row" style={{ gap: 8 }}>
            <label className="col" style={{ flex: 1 }}>
              <span className="form-label">Acidity</span>
              <select
                value={formGoals.acidity}
                onChange={(e) => onChange("acidity", e.target.value as TasteGoals["acidity"])}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </label>

            <label className="col" style={{ flex: 1 }}>
              <span className="form-label">Sweetness</span>
              <select
                value={formGoals.sweetness}
                onChange={(e) => onChange("sweetness", e.target.value as TasteGoals["sweetness"])}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </label>
          </div>

          {/* Notes */}
          <label className="col">
            <span className="form-label">Flavor notes (comma-separated)</span>
            <input
              placeholder="peach, jasmine, bergamot"
              value={formGoals.notes}
              onChange={(e) => onChange("notes", e.target.value)}
            />
          </label>

          <div className="row" style={{ gap: 8 }}>
            <button className="btn" onClick={savePreset}>
              {editId ? "Save changes" : "Create preset"}
            </button>
            <button
              className="btn secondary"
              onClick={() => {
                setPanelOpen(false);
                setEditId(null);
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </main>
  );
}
