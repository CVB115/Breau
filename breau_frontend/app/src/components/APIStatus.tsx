import { useEffect, useMemo, useState } from "react";
import { API as APIEndpoints } from "@api/endpoints";

type Ping = { ok: boolean; ms: number | null; tried: string; at: number };

// Resolve API base robustly across different endpoint shapes/envs
function resolveApiBase() {
  // prefer endpoints object fields if present
  const fromEndpoints =
    // common patterns you might have in endpoints.ts
    (APIEndpoints as any)?.base ||
    (APIEndpoints as any)?.BASE ||
    (APIEndpoints as any)?.BASE_URL ||
    (APIEndpoints as any)?.Base ||
    null;

  // prefer Vite env if defined
  const fromEnv = (import.meta as any)?.env?.VITE_API_BASE || null;

  // fallback to same-origin /api
  return String(fromEndpoints || fromEnv || "/api").replace(/\/+$/, "");
}

const API_BASE = resolveApiBase();

async function pingOnce(): Promise<Ping> {
  const start = performance.now();
  const urls = [`${API_BASE}/health`, `${API_BASE}/`];

  for (const u of urls) {
    try {
      const res = await fetch(u, { method: "GET" });
      const ms = Math.round(performance.now() - start);
      return { ok: res.ok, ms, tried: u, at: Date.now() };
    } catch {
      // try next
    }
  }
  return { ok: false, ms: null, tried: urls[urls.length - 1], at: Date.now() };
}

export default function APIStatus({ intervalMs = 8000 }: { intervalMs?: number }) {
  const [ping, setPing] = useState<Ping | null>(null);

  useEffect(() => {
    let cancel = false;
    async function loop() {
      const p = await pingOnce();
      if (!cancel) setPing(p);
    }
    loop();
    const id = setInterval(loop, intervalMs);
    return () => { cancel = true; clearInterval(id); };
  }, [intervalMs]);

  const color = useMemo(() => {
    if (!ping) return "#555";
    if (!ping.ok) return "#ff5c5c";
    if ((ping.ms ?? 999) < 150) return "#2ecc71";
    if ((ping.ms ?? 999) < 400) return "#f1c40f";
    return "#ff8c42";
  }, [ping]);

  return (
    <div
      title={`Ping ${ping?.ms ?? "?"}ms • ${ping?.tried || API_BASE}`}
      style={{
        display: "inline-flex", alignItems: "center", gap: 8,
        border: "1px solid #1f2126", padding: "6px 8px", borderRadius: 999,
        background: "#14161a"
      }}
    >
      <span
        style={{
          width: 8, height: 8, borderRadius: 999, background: color, display: "inline-block"
        }}
      />
      <span style={{ fontSize: 12, opacity: 0.9 }}>
        API {ping?.ok ? `${ping?.ms}ms` : "offline"}
      </span>
    </div>
  );
}
