import { useEffect, useState } from "react";
import { API } from "@api/endpoints";
import { fetchSuggestion } from "@api/suggest";
import { useToast } from "@context/ToastProvider";

export default function DevTools() {
  const [base, setBase] = useState(API.base);
  const [pingMs, setPingMs] = useState<number | null>(null);
  const [ok, setOk] = useState<boolean | null>(null);
  const [mode, setMode] = useState<"auto" | "goals_text" | "goals_array">("auto");
  const [sampleText, setSampleText] = useState("more florality, less body");
  const [last, setLast] = useState<any>(null);
  const { toast } = useToast();

  useEffect(() => {
    const ls = localStorage.getItem("suggest_mode") as any;
    if (ls === "goals_text" || ls === "goals_array" || ls === "auto") setMode(ls);
  }, []);

  function saveBase() {
    API.setBase(base.trim());
    toast("API base saved.", "success");
  }

  async function ping() {
    const urls = [`${API.base}/health`, `${API.base}/`];
    const start = performance.now();
    let success = false;
    for (const u of urls) {
      try {
        const r = await fetch(u, { method: "GET" });
        success = r.ok;
        break;
      } catch { /* try next */ }
    }
    setPingMs(Math.round(performance.now() - start));
    setOk(success);
  }

  function saveMode(v: "auto" | "goals_text" | "goals_array") {
    setMode(v);
    localStorage.setItem("suggest_mode", v);
    toast(`Suggest mode: ${v}`, "success");
  }

  async function testSuggest() {
    try {
      const res = await fetchSuggestion({ goals_text: sampleText });
      setLast(res);
      toast("Suggest OK", "success");
    } catch (e: any) {
      setLast({ error: e?.message || String(e) });
      toast("Suggest error", "error");
    }
  }

  return (
    <main className="page">
      <div className="card col">
        <h2>Developer Tools</h2>
        <p style={{ opacity: 0.8, marginTop: -6 }}>Edit API base, choose request mode, and send a test suggest.</p>

        <label className="col">
          <span>API Base URL</span>
          <input value={base} onChange={(e) => setBase(e.target.value)} placeholder="http://localhost:8000" />
          <div className="row" style={{ gap: 8 }}>
            <button className="btn" onClick={saveBase}>Save</button>
            <button className="btn secondary" onClick={ping}>Ping</button>
            <span style={{ opacity: 0.8 }}>
              {ok == null ? "" : ok ? `Online · ${pingMs}ms` : "Offline"}
            </span>
          </div>
        </label>

        <div className="card col">
          <h3>Suggest request mode</h3>
          <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
            <button className={`btn ${mode === "auto" ? "" : "secondary"}`} onClick={() => saveMode("auto")}>Auto</button>
            <button className={`btn ${mode === "goals_text" ? "" : "secondary"}`} onClick={() => saveMode("goals_text")}>goals_text</button>
            <button className={`btn ${mode === "goals_array" ? "" : "secondary"}`} onClick={() => saveMode("goals_array")}>goals[]</button>
          </div>
          <small style={{ opacity: 0.7 }}>
            If your backend expects <code>goals</code> (array) instead of <code>goals_text</code>, pick <b>goals[]</b>. Otherwise use Auto.
          </small>
        </div>

        <div className="card col">
          <h3>Test /brew/suggest</h3>
          <label className="col">
            <span>Goals text</span>
            <input value={sampleText} onChange={(e) => setSampleText(e.target.value)} />
          </label>
          <button className="btn" onClick={testSuggest}>Send test</button>
          {last && (
            <pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(last, null, 2)}</pre>
          )}
        </div>
      </div>
    </main>
  );
}
