import { useState } from "react";
import { useUser } from "@context/UserProvider";
import { useToast } from "@context/ToastProvider";
import { api } from "@api/client";
import { API } from "@api/endpoints";
import { mirrorKey, readMirror } from "../../utils/localMirror";

export default function ExportReset() {
  const { userId } = useUser();
  const { toast } = useToast();
  const [exporting, setExporting] = useState(false);

  async function onExport() {
    setExporting(true);
    try {
      const [profile, history] = await Promise.all([
        api.get(API.profile(userId)),
        api.get(API.history(userId, 1000)),
      ]);

      const local = {
        profile_mirror: readMirror(mirrorKey.profile(), null),
        beans_mirror: readMirror(mirrorKey.beans(userId), []),
        active_gear_mirror: readMirror(mirrorKey.gearActive(userId), null),
        history_mirror: readMirror(mirrorKey.history(userId), []),
        saved_goals: readMirror("saved_goals", null),
        voice_enabled: localStorage.getItem("voice_enabled"),
      };

      const blob = new Blob([JSON.stringify({ profile, history, local }, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `breau-export-${userId}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast("Export ready.", "success");
    } catch {
      toast("Export failed.", "error");
    } finally {
      setExporting(false);
    }
  }

  function onReset() {
    [
      mirrorKey.profile(),
      mirrorKey.beans(userId),
      mirrorKey.gearActive(userId),
      mirrorKey.history(userId),
      "saved_goals",
      "voice_enabled",
    ].forEach((k) => localStorage.removeItem(k));
    toast("Local settings & mirrors cleared.", "success");
  }

  return (
    <main className="page">
      <div className="card col">
        <h2>Export & Reset</h2>
        <div className="row" style={{ gap: 8 }}>
          <button className="btn" onClick={onExport} disabled={exporting}>
            {exporting ? "Exporting…" : "Export JSON"}
          </button>
          <button className="btn secondary" onClick={onReset}>Clear local</button>
        </div>
      </div>
    </main>
  );
}
