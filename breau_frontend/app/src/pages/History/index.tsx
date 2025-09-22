// src/pages/History/index.tsx
import React from "react";
import { useNavigate } from "react-router-dom";
import useBrewHistory from "@hooks/useBrewHistory";
import useProfile from "@hooks/useProfile";

export default function HistoryPage() {
  const nav = useNavigate();
  const { data: profile } = useProfile();   // canonical identity
  const { sessions } = useBrewHistory();    // already scoped per userId

  // sort most-recent first (createdAt/updatedAt; fall back to 0)
  const list = [...sessions].sort(
    (a, b) => (b.updatedAt ?? b.createdAt ?? 0) - (a.updatedAt ?? a.createdAt ?? 0)
  );

  return (
    <main className="max-w-4xl mx-auto p-4">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold">History</h1>
        <div className="text-sm opacity-70">
          {profile?.name || profile?.userId || "local"}
        </div>
      </div>

      {list.length === 0 ? (
        <p className="opacity-70">No brews yet.</p>
      ) : (
        <ul className="space-y-3">
          {list.map((rec) => {
            const title =
              rec?.summary?.name ||
              rec?.recipe?.name ||
              (rec?.status === "finished" ? "Finished brew" : "Manual brew");

            const type =
              rec?.summary?.type ||
              rec?.recipe?.type ||
              (rec?.recipe ? "suggested" : "manual");

            const cup = rec?.summary?.cup ?? rec?.cup ?? "—";

            const when = new Date(rec.updatedAt ?? rec.createdAt ?? Date.now());
            const whenStr = isNaN(when.getTime()) ? "" : when.toLocaleString();

            return (
              <li
                key={rec.id}
                className="flex items-center justify-between rounded-lg bg-neutral-800/40 px-4 py-3"
              >
                <div className="min-w-0">
                  <div className="font-medium truncate">{title}</div>
                  <div className="text-sm opacity-70 truncate">
                    {rec.id} · {type} {whenStr ? `· ${whenStr}` : ""}
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <div className="text-sm opacity-70">Cup: {cup}</div>

                  <button
                    className="px-3 py-1.5 rounded-md bg-blue-600 hover:bg-blue-500 text-white text-sm"
                    onClick={() =>
                      // Pass only the session id; Summary will load details
                      nav("/brew/summary", { state: { session_id: rec.id } })
                    }
                  >
                    Open summary
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      <div className="mt-6">
        <button
          className="px-4 py-2 rounded-md bg-neutral-700 hover:bg-neutral-600 text-white"
          onClick={() => nav("/")}
        >
          Home
        </button>
      </div>
    </main>
  );
}
