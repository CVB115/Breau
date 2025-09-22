import { Link, useNavigate } from "react-router-dom";

export default function BrewIndex() {
  const nav = useNavigate();
  return (
    <main className="page">
      <div className="card col">
        <h2>Suggested brew</h2>
        <p style={{ opacity: 0.85, marginTop: -6 }}>
          AI-assisted recipe from your bean, gear & taste goals.
        </p>
        <div className="row" style={{ gap: 8 }}>
          <button className="btn" onClick={() => nav("/brew/suggest")}>Start</button>
          <Link to="/profile/taste-goals" className="btn secondary">Manage goals</Link>
        </div>
      </div>

      <div className="card col">
        <h2>Manual brew</h2>
        <p style={{ opacity: 0.85, marginTop: -6 }}>
          Enter dose/water/temp; follow a simple 3-step guide.
        </p>
        <div className="row" style={{ gap: 8 }}>
          <button className="btn" onClick={() => nav("/brew/manual")}>Setup</button>
        </div>
      </div>

      <div className="card col">
        <h2>History</h2>
        <p style={{ opacity: 0.85, marginTop: -6 }}>
          Review, repeat, or tweak a previous brew.
        </p>
        <div className="row" style={{ gap: 8 }}>
          <Link to="/history" className="btn">Open history</Link>
        </div>
      </div>
    </main>
  );
}
