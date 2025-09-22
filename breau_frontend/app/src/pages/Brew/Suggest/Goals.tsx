// src/pages/brew/suggest/Goals.tsx
import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useSearchParams, Link } from "react-router-dom";
import { useUser } from "@context/UserProvider";
import { useToast } from "@context/ToastProvider";
import useBeansLibrary from "@hooks/useBeansLibrary";
import { suggest } from "@api/suggest";
import { api } from "@api/client";
import { API } from "@api/endpoints";


// ---- Types --------------------------------------------------------------
type Bean = { id: string | number; name?: string; roaster?: string; origin?: string };
type GearCombo = { id?: string; label?: string; brewer?: any; grinder?: any; filter?: any; water?: any };
type TasteGoals = {
  strength?: "light" | "medium" | "strong";
  acidity?: "low" | "medium" | "high";
  body?: "light" | "medium" | "heavy";
  sweetness?: "low" | "medium" | "high";
  notes?: string;
};
type GoalsPreset = { id: string; name: string; goals: TasteGoals };

// ---- Helpers ------------------------------------------------------------
function getLocalActiveGear(): GearCombo | null {
  try {
    const a = localStorage.getItem("active_gear");
    const b = localStorage.getItem("unsynced_active_gear");
    return (a && JSON.parse(a)) || (b && JSON.parse(b)) || null;
  } catch {
    return null;
  }
}
function loadGoalPresets(userId: string): GoalsPreset[] {
  try {
    const raw = localStorage.getItem(`breau.goalPresets.${userId}`);
    const list = raw ? JSON.parse(raw) : [];
    return Array.isArray(list) ? list : [];
  } catch {
    return [];
  }
}
function goalsToText(g: TasteGoals): string {
  const parts: string[] = [];
  const add = (label?: string) => label && parts.push(label);
  if (g.strength) add(`${g.strength} strength`);
  if (g.body) add(`${g.body} body`);
  if (g.acidity) add(`${g.acidity} acidity`);
  if (g.sweetness) add(`${g.sweetness} sweetness`);
  const base = parts.join(", ");
  const notes = g.notes?.trim() ? `; notes: ${g.notes.trim()}` : "";
  return (base + notes).trim();
}

// ------------------------------------------------------------------------
export default function Goals() {
  const nav = useNavigate();
  const { state } = useLocation() as {
  state?: {
    bean?: Bean;
    goals_text?: string;
    // NEW: lineage / provenance for Adjust & Brew
    reference_session_id?: string;
    prior_recipe?: any;
    source?: "summary-adjust" | "goals-normal";
  };
};
  const [params] = useSearchParams();
  const { userId } = useUser();
  const { toast } = useToast();

  // Beans (unified with Beans page)
  const beansLib = useBeansLibrary() as any;
  const beans: Bean[] = (beansLib?.items ?? []) as any[];

  // Seed bean from nav/query if provided
  const beanFromState = state?.bean;
  const beanIdFromQuery = params.get("bean_id") || undefined;
  const [beanId, setBeanId] = useState<string | undefined>(
    (beanFromState?.id && String(beanFromState.id)) || (beanIdFromQuery || undefined)
  );
  const selectedBean = useMemo(
    () => beans.find((b) => String(b.id) === String(beanId)) || beanFromState || undefined,
    [beans, beanId, beanFromState]
  );

  // Active gear
  const [activeGear, setActiveGear] = useState<GearCombo | null>(null);
  const [loading, setLoading] = useState(true);

  // Goals input + presets picker
  const [goalsText, setGoalsText] = useState<string>("");
  const [pickerOpen, setPickerOpen] = useState(false);
  const [presets, setPresets] = useState<GoalsPreset[]>([]);

  // Seed text on mount (custom prompt if no state provided)
  useEffect(() => {
    setGoalsText(state?.goals_text || "slightly brighter, less bitterness");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Load presets whenever the picker opens
  useEffect(() => {
    if (pickerOpen) {
      setPresets(loadGoalPresets(userId));
    }
  }, [pickerOpen, userId]);

  // Load active gear (server → local)
  useEffect(() => {
    let cancel = false;
    (async () => {
      setLoading(true);
      try {
        const gearPath =
          (API as any).profileActiveGear
            ? (API as any).profileActiveGear(userId)
            : `/api/profile/${encodeURIComponent(userId)}/active/gear`;
        const res = await api.get<{ gear?: any }>(gearPath);
        if (!cancel && res?.gear) {
          setActiveGear(res.gear);
        } else if (!cancel) {
          setActiveGear(getLocalActiveGear());
        }
      } catch {
        if (!cancel) setActiveGear(getLocalActiveGear());
      } finally {
        if (!cancel) setLoading(false);
      }
    })();
    return () => { cancel = true; };
  }, [userId]);

    // Submit → backend suggest
    async function onSubmit() {
      if (!activeGear) {
        toast("Pick a gear combo in Profile → Gear first.", "error");
        return;
      }
      try {
        const payload: any = { user_id: userId, goals_text: goalsText };
        if (selectedBean?.id != null) {
          payload.bean_id = String(selectedBean.id);
          payload.bean = selectedBean;
        }
        payload.gear = activeGear;

        if (state?.reference_session_id) payload.reference_session_id = state.reference_session_id;
        if (state?.prior_recipe)        payload.prior_recipe = state.prior_recipe;

        // ⬇️ expect backend to return { recipe, explain, predicted_notes }
        const res = await suggest(payload as any);
        console.log("[Suggest grind]", res?.recipe?.grind, res?.recipe);
        const { recipe, explain, predicted_notes } = (res || {}) as any;
        
        const goalsArr = goalsText?.trim()
        ? [{ raw: goalsText.trim() }]
        : [] as any[];
       
        nav("/brew/suggest/preview", {
          state: {
            goals_text: goalsText,
            goals: goalsArr, // ✅ pass structured goals forward
            bean_id: selectedBean?.id != null ? String(selectedBean.id) : undefined,
            bean: selectedBean || null,
            recipe,
            predicted_notes,
            gear: activeGear || null,
            explain,
            source: state?.source || "goals-normal",
            reference_session_id: state?.reference_session_id,
            prior_recipe: state?.prior_recipe,
          },
        });
      } catch (e: any) {
        toast(`Suggest failed: ${e?.message || "unknown"}`, "error");
      }
    }


  return (
    <main className="page">
      {/* ---- Choose gear & bean ---------------------------------------------- */}
      <div className="card col">
        <h2>Choose gear &amp; bean</h2>

        {/* Active Gear */}
        <div className="card row" style={{ justifyContent: "space-between", alignItems: "center" }}>
          <div className="col">
            <div><b>Active gear</b></div>
            {loading ? (
              <div className="skeleton" style={{ width: 160 }} />
            ) : activeGear ? (
              <div style={{ opacity: 0.9 }}>{activeGear.label || "Custom combo selected"}</div>
            ) : (
              <div style={{ color: "#ffb86b" }}>No active combo. Please set one.</div>
            )}
          </div>
          <Link className="btn secondary" to="/profile/gear">Change</Link>
        </div>

        {/* Bean picker */}
        <label className="col">
          <span>Bean</span>
          <select
            value={beanId || ""}
            onChange={(e) => setBeanId(e.target.value || undefined)}
          >
            <option value="">
              {beanFromState?.name ? `(keep) ${beanFromState.name}` : "Select a bean"}
            </option>
            {beans.map((b) => (
              <option key={String(b.id)} value={String(b.id)}>
                {b.name || "Unnamed"} {b.roaster ? `• ${b.roaster}` : ""}
              </option>
            ))}
          </select>
          <div className="row" style={{ gap: 8 }}>
            <Link className="btn secondary" to="/profile/beans">Manage beans</Link>
            <Link className="btn secondary" to="/profile/beans?scan=1">Scan label</Link>
          </div>
        </label>
      </div>

      {/* ---- Goals ----------------------------------------------------------- */}
      <div className="card col">
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
          <h2>What are you aiming for?</h2>
          <button className="btn secondary" onClick={() => setPickerOpen(true)}>
            Choose saved goals
          </button>
        </div>

        {selectedBean && (
          <div className="card">
            <strong>Bean:</strong> {selectedBean.name || "Unnamed"}
            {selectedBean.roaster ? ` • ${selectedBean.roaster}` : ""}
          </div>
        )}

        <label className="col">
          <span>Goals (plain English)</span>
          <textarea
            rows={4}
            value={goalsText}
            onChange={(e) => setGoalsText(e.target.value)}
            placeholder="e.g., more florality, less body"
          />
        </label>

        <div className="row" style={{ gap: 8 }}>
          <button className="btn" onClick={onSubmit} disabled={loading}>
            Generate suggestion
          </button>
        </div>
      </div>

      {/* ---- Saved goals picker (modal) ------------------------------------- */}
      {pickerOpen && (
        <div className="net-overlay" onClick={() => setPickerOpen(false)}>
          <div
            className="net-body"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: 560, width: "96vw" }}
          >
            <div className="card col">
              <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
                <h3>Select saved Taste &amp; Goals</h3>
                <button className="btn secondary" onClick={() => setPickerOpen(false)}>Close</button>
              </div>

              {presets.length === 0 && (
                <div style={{ opacity: 0.8 }}>
                  No saved goals yet. Create some in <b>Profile → Taste &amp; Goals</b>.
                </div>
              )}

              <ul className="col" style={{ gap: 8, marginTop: 6 }}>
                {presets.map((p) => {
                  const preview = goalsToText(p.goals);
                  return (
                    <li key={p.id} className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
                      <div className="col">
                        <div style={{ fontWeight: 600 }}>{p.name}</div>
                        <div style={{ fontSize: 13, opacity: 0.75 }}>{preview || "—"}</div>
                      </div>
                      <button
                        className="btn"
                        onClick={() => {
                          setGoalsText(preview);
                          setPickerOpen(false);
                        }}
                      >
                        Use
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
