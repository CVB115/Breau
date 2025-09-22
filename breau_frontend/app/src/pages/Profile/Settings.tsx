import { useEffect, useState } from "react";
import { useUser } from "@context/UserProvider";
import useProfile from "@hooks/useProfile";
import { canSpeak, canListen } from "@lib/voice";
import { useToast } from "@context/ToastProvider";

export default function Settings() {
  const { userId } = useUser(); // ok to keep; used for mirrors/keys elsewhere if needed
  const { data: profile, save } = useProfile(); // ✅ FIX: no arg — hook reads user from context
  const [units, setUnits] = useState<"metric" | "imperial">("metric");
  const [smart, setSmart] = useState<boolean>(true);
  const [overlay, setOverlay] = useState<boolean>(true);
  const [voice, setVoice] = useState<boolean>(false);
  const { toast } = useToast();

  const synthOK = canSpeak();
  const recogOK = canListen();

  useEffect(() => {
    if (!profile) return;
    setUnits((profile.settings?.units as any) || "metric");
    setSmart(!!profile.settings?.smart_suggestions);
    setOverlay(!!profile.settings?.learning_overlay);
    setVoice(localStorage.getItem("voice_enabled") === "1");
  }, [profile]);

  async function onSave() {
    // ✅ FIX: cast to any to satisfy your save() typing
    await save({
      settings: { units, smart_suggestions: smart, learning_overlay: overlay },
    } as any);
    localStorage.setItem("voice_enabled", voice ? "1" : "0");
    toast("Settings saved.", "success");
  }

  return (
    <main className="page">
      <div className="card col">
        <h2>Settings</h2>

        <label className="col">
          <span>Units</span>
          <select value={units} onChange={(e) => setUnits(e.target.value as any)}>
            <option value="metric">Metric (g, °C)</option>
            <option value="imperial">Imperial (oz, °F)</option>
          </select>
        </label>

        <label className="row">
          <input type="checkbox" checked={smart} onChange={(e) => setSmart(e.target.checked)} />
          <span>Smart suggestions</span>
        </label>

        <label className="row">
          <input type="checkbox" checked={overlay} onChange={(e) => setOverlay(e.target.checked)} />
          <span>Learning overlay</span>
        </label>

        <div className="card col">
          <h3>Voice</h3>
          <p style={{ opacity: 0.8, margin: 0 }}>
            TTS: {synthOK ? "available" : "not supported"} · STT: {recogOK ? "available" : "not supported"}
          </p>
          <label className="row">
            <input
              type="checkbox"
              checked={voice}
              onChange={(e) => setVoice(e.target.checked)}
              disabled={!synthOK}
            />
            <span>Enable voice (speak steps & voice commands)</span>
          </label>
        </div>

        <div className="row" style={{ gap: 8 }}>
          <button className="btn" onClick={onSave}>Save</button>
        </div>
      </div>
    </main>
  );
}
