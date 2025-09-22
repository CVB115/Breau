// src/pages/Profile/EditProfile.tsx
import { useEffect, useMemo, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useUser } from "@context/UserProvider";
import { api } from "@api/client";
import { API } from "@api/endpoints";

type RoundTime = {
  enabled: boolean;
  step_s: 5 | 10 | 15;
};

type Preferences = {
  units: "metric" | "imperial";
  smart_suggest: boolean;
  learning_overlay: boolean;
  stt_enabled: boolean;
  tts_enabled: boolean;
  round_pours_to: 5 | 10 | "none";
  // NEW
  round_time: RoundTime;
};

type ProfileModel = {
  user_id: string;
  name?: string;
  preferences: Preferences;
  updated_at?: string;
};

const DEFAULT_PREFS: Preferences = {
  units: "metric",
  smart_suggest: true,
  learning_overlay: false,
  stt_enabled: true,
  tts_enabled: false,
  round_pours_to: 10,
  // NEW default
  round_time: { enabled: true, step_s: 5 },
};

export default function EditProfile() {
  const nav = useNavigate();
  const { userId, setUserId } = useUser() as { userId: string; setUserId?: (s: string) => void };

  const [name, setName] = useState<string>("");
  const [idDraft, setIdDraft] = useState<string>(userId || "local");
  const [prefs, setPrefs] = useState<Preferences>(DEFAULT_PREFS);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  // Load from local first for instant paint
  useEffect(() => {
    try {
      const raw = localStorage.getItem("breau.profile");
      if (raw) {
        const p = JSON.parse(raw) as ProfileModel;
        setName(p?.name || "");
        setIdDraft(p?.user_id || userId || "local");
        setPrefs({ ...DEFAULT_PREFS, ...(p?.preferences || {}) });
        setLoading(false);
      }
    } catch {
      // ignore
    }
  }, [userId]);

  // Hydrate from API in background
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get(API.profile(userId));
        if (cancelled || !res) return;
        const p = res as Partial<ProfileModel>;
        if (p?.name !== undefined) setName(p.name || "");
        if (p?.user_id) setIdDraft(p.user_id);
        if (p?.preferences) {
          setPrefs((prev) => ({
            ...prev,
            ...p.preferences!,
            round_time: { ...prev.round_time, ...(p.preferences as any).round_time },
          }));
        }
      } catch {
        // offline-first: okay to fail
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [userId]);

  const initials = useMemo(
    () =>
      (name || "A B")
        .trim()
        .split(" ")
        .map((w) => w[0])
        .join("")
        .slice(0, 2)
        .toUpperCase(),
    [name]
  );

  const onSave = async () => {
    const payload: ProfileModel = {
      user_id: idDraft.trim() || "local",
      name: name.trim(),
      preferences: prefs,
      updated_at: new Date().toISOString(),
    };

    setSaving(true);
    try {
      // optimistic: write local first
      localStorage.setItem("breau.profile", JSON.stringify(payload));

      // also set simple keys used by rounding hooks so the app reflects immediately
      try {
        localStorage.setItem("breau.pref.round_time_enabled", prefs.round_time.enabled ? "true" : "false");
        localStorage.setItem("breau.pref.round_time_s", String(prefs.round_time.step_s));
        // expose a tiny global getter so hooks can read the mirror without imports (optional, safe)
        (window as any).breauGetUserMirror = () => ({
          user_id: payload.user_id,
          settings: {
            round_pours: {
              step_g: prefs.round_pours_to === "none" ? 1 : prefs.round_pours_to,
            },
            round_time: { ...prefs.round_time },
          },
          preferences: payload.preferences,
          name: payload.name,
        });
      } catch {}

      // post to server
      await api.post(API.profile(payload.user_id), {
        name: payload.name,
        preferences: payload.preferences,
      });

      // if user_id changed, update provider if available
      if (payload.user_id !== userId && typeof setUserId === "function") {
        setUserId(payload.user_id);
      }

      nav("/profile");
    } catch {
      alert("Could not save to server right now. Your local changes were saved.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <main className="page">
        <div className="card">
          <div style={{ opacity: 0.7 }}>Loading profile…</div>
        </div>
      </main>
    );
  }

  return (
    <main className="page">
      <div className="row" style={{ gap: 8, marginBottom: 12 }}>
        <Link to="/profile" className="btn secondary">← Back</Link>
        <div className="spacer" />
        <button className="btn secondary" onClick={() => nav("/profile/export-reset")}>Export</button>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="row" style={{ gap: 12, alignItems: "center" }}>
          <div className="avatar large">{initials}</div>
          <div className="col" style={{ gap: 8 }}>
            <div className="row" style={{ gap: 12 }}>
              <div className="col">
                <label className="label">Name</label>
                <input
                  className="input"
                  placeholder="Your name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </div>
              <div className="col" style={{ maxWidth: 220 }}>
                <label className="label">User ID</label>
                <input
                  className="input"
                  placeholder="local"
                  value={idDraft}
                  onChange={(e) => setIdDraft(e.target.value)}
                />
              </div>
            </div>
            <div className="hint">Your User ID scopes beans, gear and history on this device.</div>
          </div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h2 style={{ marginTop: 0 }}>Preferences</h2>

        {/* Units */}
        <div className="row prefs">
          <div className="label">Units</div>
          <div className="row" role="radiogroup" aria-label="Units">
            <label className="radio">
              <input
                type="radio"
                name="units"
                checked={prefs.units === "metric"}
                onChange={() => setPrefs({ ...prefs, units: "metric" })}
              />
              <span>Metric</span>
            </label>
            <label className="radio">
              <input
                type="radio"
                name="units"
                checked={prefs.units === "imperial"}
                onChange={() => setPrefs({ ...prefs, units: "imperial" })}
              />
              <span>Imperial</span>
            </label>
          </div>
        </div>

        {/* Smart & Learning */}
        <div className="row prefs">
          <div className="label">Smart suggestions</div>
          <label className="switch">
            <input
              type="checkbox"
              checked={prefs.smart_suggest}
              onChange={(e) => setPrefs({ ...prefs, smart_suggest: e.target.checked })}
            />
            <span />
          </label>
        </div>

        <div className="row prefs">
          <div className="label">Learning overlay</div>
          <label className="switch">
            <input
              type="checkbox"
              checked={prefs.learning_overlay}
              onChange={(e) => setPrefs({ ...prefs, learning_overlay: e.target.checked })}
            />
            <span />
          </label>
        </div>

        {/* Voice */}
        <div className="row prefs">
          <div className="label">Voice: STT</div>
          <label className="switch">
            <input
              type="checkbox"
              checked={prefs.stt_enabled}
              onChange={(e) => setPrefs({ ...prefs, stt_enabled: e.target.checked })}
            />
            <span />
          </label>
        </div>

        <div className="row prefs">
          <div className="label">Voice: TTS</div>
          <label className="switch">
            <input
              type="checkbox"
              checked={prefs.tts_enabled}
              onChange={(e) => setPrefs({ ...prefs, tts_enabled: e.target.checked })}
            />
            <span />
          </label>
        </div>

        {/* Pour rounding */}
        <div className="row prefs">
          <div className="label">Round pours to</div>
          <div className="row" role="radiogroup" aria-label="Round pours">
            <label className="radio">
              <input
                type="radio"
                name="round"
                checked={prefs.round_pours_to === 10}
                onChange={() => setPrefs({ ...prefs, round_pours_to: 10 })}
              />
              <span>10 g</span>
            </label>
            <label className="radio">
              <input
                type="radio"
                name="round"
                checked={prefs.round_pours_to === 5}
                onChange={() => setPrefs({ ...prefs, round_pours_to: 5 })}
              />
              <span>5 g</span>
            </label>
            <label className="radio">
              <input
                type="radio"
                name="round"
                checked={prefs.round_pours_to === "none"}
                onChange={() => setPrefs({ ...prefs, round_pours_to: "none" })}
              />
              <span>None</span>
            </label>
          </div>
        </div>

        {/* NEW: Time rounding */}
        <div className="row prefs">
          <div className="label">Time rounding</div>
          <div className="col" style={{ gap: 8 }}>
            <label className="row" style={{ gap: 8, alignItems: "center" }}>
              <input
                type="checkbox"
                checked={prefs.round_time.enabled}
                onChange={(e) =>
                  setPrefs({ ...prefs, round_time: { ...prefs.round_time, enabled: e.target.checked } })
                }
              />
              <span>Enable rounding for bloom/pour “until/by” and timers</span>
            </label>
            <label className="row" style={{ gap: 8, alignItems: "center" }}>
              <span>Step</span>
              <select
                className="input"
                value={prefs.round_time.step_s}
                onChange={(e) =>
                  setPrefs({
                    ...prefs,
                    round_time: { ...prefs.round_time, step_s: Number(e.target.value) as 5 | 10 | 15 },
                  })
                }
              >
                <option value={5}>5 seconds</option>
                <option value={10}>10 seconds</option>
                <option value={15}>15 seconds</option>
              </select>
            </label>
            <div className="hint">Applies across Preview, Guide, Log and Finish payloads.</div>
          </div>
        </div>
      </div>

      <div className="row" style={{ gap: 8 }}>
        <Link to="/profile" className="btn secondary">Cancel</Link>
        <div className="spacer" />
        <button className="btn" onClick={onSave} disabled={saving}>
          {saving ? "Saving…" : "Save changes"}
        </button>
      </div>
    </main>
  );
}
