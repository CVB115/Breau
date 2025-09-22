// src/pages/History/SessionDetail.tsx
import { useMemo } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import useBrewHistory from "@hooks/useBrewHistory";
import { useUser } from "@context/UserProvider";

function downloadJSON(filename: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export default function SessionDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const { userId } = useUser();
  const { sessions } = useBrewHistory();

  const detail = useMemo(
    () => sessions.find((s) => String(s.id) === String(id)),
    [sessions, id]
  );

  if (!detail) {
    return (
      <main className="p-4">
        <div className="max-w-3xl mx-auto">
          <h1 className="text-xl font-semibold mb-2">Session not found</h1>
          <p className="mb-4">
            We couldn’t find a session with id <code>{id}</code> for user{" "}
            <code>{userId}</code>.
          </p>
          <Link className="underline" to="/history">
            Back to History
          </Link>
        </div>
      </main>
    );
  }

  const title = detail.brew_name || detail.recipe?.name || `Brew ${detail.id}`;
  const filename = `breau-session-${detail.id}.json`;

  const exportSession = () => {
    downloadJSON(filename, detail);
  };

  const brewAgain = () => {
    nav("/brew/suggest/preview", {
      state: {
        source: "history-brew-again",
        recipe: detail?.recipe ?? {},
        bean: detail?.bean ?? null,
        gear: detail?.gear ?? null,
        historySession: {
          id: detail?.id,
          date: detail?.started_at || detail?.created_at,
        },
      },
    });
  };

  const adjustAndBrew = () => {
    nav("/brew/suggest", {
      state: {
        source: "history-adjust",
        prior_recipe: detail?.recipe ?? {},
        bean: detail?.bean ?? null,
        gear: detail?.gear ?? null,
        historySession: {
          id: detail?.id,
          date: detail?.started_at || detail?.created_at,
        },
      },
    });
  };

  return (
    <main className="p-4">
      <div className="max-w-3xl mx-auto space-y-4">
        <header className="flex items-center justify-between">
          <h1 className="text-xl font-semibold">{title}</h1>
          <Link to="/history" className="text-sm underline">
            Back
          </Link>
        </header>

        <section className="border rounded-xl p-4 bg-white">
          <h2 className="font-medium mb-2">Overview</h2>
          <div className="text-sm opacity-80">
            <div>
              <span className="font-medium">Session ID:</span> {detail.id}
            </div>
            <div>
              <span className="font-medium">User:</span> {userId}
            </div>
            <div>
              <span className="font-medium">When:</span>{" "}
              {detail.started_at || detail.created_at || "—"}
            </div>
          </div>
        </section>

        <section className="border rounded-xl p-4 bg-white">
          <h2 className="font-medium mb-2">Recipe</h2>
          <pre className="text-xs bg-gray-50 p-3 rounded overflow-auto">
            {JSON.stringify(detail.recipe ?? {}, null, 2)}
          </pre>
        </section>

        {!!detail.feedback && (
          <section className="border rounded-xl p-4 bg-white">
            <h2 className="font-medium mb-2">Feedback</h2>
            <pre className="text-xs bg-gray-50 p-3 rounded overflow-auto">
              {JSON.stringify(detail.feedback, null, 2)}
            </pre>
          </section>
        )}

        <div className="flex flex-wrap gap-2">
          <button className="px-4 py-2 rounded-md border" onClick={exportSession}>
            Export session (JSON)
          </button>
          <button
            className="px-4 py-2 rounded-md bg-black text-white disabled:opacity-40"
            disabled={!detail?.recipe}
            onClick={brewAgain}
          >
            Brew again (use this recipe)
          </button>
          <button
            className="px-4 py-2 rounded-md border disabled:opacity-40"
            disabled={!detail?.recipe}
            onClick={adjustAndBrew}
          >
            Adjust &amp; Brew (goal-based)
          </button>
          <button className="px-4 py-2 rounded-md border" onClick={() => nav(-1)}>
            Close
          </button>
        </div>
      </div>
    </main>
  );
}
