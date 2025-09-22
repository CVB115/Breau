// src/pages/Brew/Suggest/Rate.tsx
import React, { useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import useBrewHistory from "@hooks/useBrewHistory";
import { useToast } from "@context/ToastProvider";

// Navigation state coming from Guide → Rate
type NavState = { session_id: string; brew_name?: string };

// Fallback POST helper (works with Vite dev proxy: /api/*)
async function postJSON(path: string, body: any) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const msg = await res.text().catch(() => res.statusText);
    throw new Error(msg || "Request failed");
  }
  try {
    return await res.json();
  } catch {
    return {};
  }
}

export default function Rate() {
  const nav = useNavigate();
  const { state } = useLocation() as { state?: NavState };
  const { patch } = useBrewHistory();
  const { toast } = useToast();

  const session_id = state?.session_id;
  const brew_name = state?.brew_name || "";

  const [rating, setRating] = useState<number>(0);
  const [text, setText] = useState<string>("");

  const canPost = useMemo(() => !!session_id && rating > 0, [session_id, rating]);

  async function submit() {
    if (!canPost) return;

    const suggest_comment = text.trim() || undefined;
    const suggest_rating = Math.round(rating);

    // Local mirror patch in the exact keys Summary reads
    const feedbackPatch = {
      feedback: {
        suggest_rating,
        ...(suggest_comment ? { suggest_comment } : {}),
      },
    };

    try {
      // 1) Canonical finish (server may record generic rating/notes)
      await postJSON("/api/brew/finish", {
        session_id,
        rating: suggest_rating,
        ...(suggest_comment ? { notes: suggest_comment } : {}),
      });

      // 2) Richer feedback endpoint using suggest_* fields (if present in backend)
      try {
        await postJSON("/api/feedback", {
          session_id,
          suggest_rating,
          suggest_comment,
        });
      } catch {
        // non-fatal; we still patch locally
      }

      // 3) Local (offline-friendly) — patch in mirror/history
      patch(session_id!, feedbackPatch);

      toast("Thanks! Your rating was saved.", "success");

      // 4) Go to existing Summary (so “Suggestion result” shows stars + text)
      nav("/brew/assess", { state: { session_id, brew_name } });
    } catch (e: any) {
      toast(`Failed to submit: ${e?.message || "Unknown error"}`, "error");
    }
  }

  return (
    <main className="max-w-xl mx-auto p-4">
      <h1 className="text-2xl font-semibold mb-2">How was the recommendation?</h1>
      {brew_name && <p className="opacity-70 mb-4">{brew_name}</p>}

      <div className="border rounded-xl p-4 bg-white space-y-4">
        <section>
          <h2 className="font-medium mb-2">Rate it</h2>
          <div className="flex gap-2">
            {[1, 2, 3, 4, 5].map((n) => (
              <button
                key={n}
                className={`px-3 py-2 rounded-md border ${rating === n ? "bg-black text-white" : ""}`}
                onClick={() => setRating(n)}
                aria-pressed={rating === n}
              >
                {n}
              </button>
            ))}
          </div>
        </section>

        <section>
          <h2 className="font-medium mb-2">Tell us more (optional)</h2>
          <p className="text-sm opacity-70 mb-2">
            What felt missing or what would you like more of next time?
          </p>
          <textarea
            className="w-full border rounded-md p-3 min-h-[120px]"
            placeholder="e.g., a touch more florality, slightly less bitterness..."
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </section>

        <div className="flex items-center gap-2">
          <button className="px-4 py-2 rounded-md bg-black text-white" onClick={submit} disabled={!canPost}>
            Submit
          </button>
          <button
            className="px-4 py-2 rounded-md border"
            onClick={() => nav("/brew/assess", { state: { session_id } })}
          >
            Skip
          </button>
        </div>
      </div>
    </main>
  );
}
