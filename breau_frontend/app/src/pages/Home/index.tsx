// src/pages/Home/index.tsx
import { useEffect, useState } from "react";
import { api } from "@api/client";
import { API } from "@api/endpoints";
import { useUser } from "@context/UserProvider";
import { Link } from "react-router-dom";

type HistItem = {
  id: string;
  created_utc?: number;
  status?: string;
  rating?: number;
  summary?: {
    bean?: string;
    roaster?: string;
    brewer?: string;
    dose_g?: number;
    water_g?: number;
    ratio?: string;
  };
};

export default function Home() {
  const { userId } = useUser();
  const [last, setLast] = useState<HistItem | null>(null);
  const [recent, setRecent] = useState<HistItem[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancel = false;
    (async () => {
      setErr(null);
      try {
        const list = await api.get<{ sessions: HistItem[] }>(API.history(userId, 5));
        if (cancel) return;
        setRecent(list.sessions || []);
        setLast(list.sessions?.[0] || null);
      } catch (e: any) {
        if (!cancel) setErr(e?.message || "Failed to load home");
      }
    })();
    return () => { cancel = true; };
  }, [userId]);

  return (
    <main className="page">
      <section className="section">
        <h1>Welcome back, {userId} 👋</h1>
        <div style={{ opacity: 0.7 }}>Keep your streak going!</div>
        <div className="card row" style={{ justifyContent: "space-between" }}>
          <div><b>🔥 Brew Streak:</b> 3 days</div>
          <Link className="btn secondary" to="/profile/taste-goals">Taste Profile</Link>
        </div>
      </section>

      <div className="card col">
        <h2>Smart Suggestions</h2>
        <div style={{ opacity: 0.85 }}>
          Not sure what to brew? Try something new based on your taste.
        </div>
        <Link className="btn" to="/brew/suggest">Get a Suggestion</Link>
      </div>

      <div className="card col">
        <h2>Active Brew</h2>
        {err && <div style={{ color: "#ff6b6b" }}>{err}</div>}
        {last && last.status === "in_progress" ? (
          <div>
            Brewing now — <b>{last.summary?.bean || "Unknown bean"}</b>
            {last.summary?.roaster ? ` • ${last.summary.roaster}` : ""} —{" "}
            <Link to={`/brew/manual/guide/${encodeURIComponent(last.id)}`}>resume</Link>
          </div>
        ) : (
          <div>Nothing brewing at the moment.</div>
        )}
      </div>

      <div className="card col">
        <h2>Last Brew Recap</h2>
        {last && last.status !== "in_progress" ? (
          <Recap item={last} />
        ) : (
          <div>No brews yet. Start one to see recaps here.</div>
        )}
      </div>

      <div className="card col">
        <h2>Recent Brews</h2>
        {recent.length ? (
          <div className="col" style={{ gap: 6 }}>
            {recent.map((it) => (
              <div key={it.id} className="card row" style={{ justifyContent: "space-between" }}>
                <div>
                  <b>{it.summary?.bean || "Unnamed"}</b>
                  {it.summary?.roaster ? ` — ${it.summary.roaster}` : ""}
                  {it.summary?.brewer ? ` • ${it.summary.brewer}` : ""}
                </div>
                <Link className="btn secondary" to={`/history/${encodeURIComponent(it.id)}`}>Open</Link>
              </div>
            ))}
          </div>
        ) : (
          <div>Nothing yet.</div>
        )}
      </div>
    </main>
  );
}

function Recap({ item }: { item: HistItem }) {
  const s = item.summary || {};
  return (
    <div>
      <div><b>{s.bean || "Bean"}</b>{s.roaster ? ` — ${s.roaster}` : ""}</div>
      <div style={{ opacity: 0.85 }}>
        {[s.brewer, s.ratio, s.dose_g && `${s.dose_g}g`, s.water_g && `${s.water_g}g water`]
          .filter(Boolean)
          .join(" • ")}
      </div>
      {typeof item.rating === "number" && <div>Rating: {item.rating}/5</div>}
    </div>
  );
}
