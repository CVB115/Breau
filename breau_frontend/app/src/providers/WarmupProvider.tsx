import { useEffect, useRef } from "react";

/**
 * Pre-warms services on first mount.
 * Uses plain fetch so 404/connection issues don't hit the api client
 * (and therefore won't print red "client.ts:XX" errors in the console).
 */
export default function WarmupProvider({ children }: { children: React.ReactNode }) {
  const did = useRef(false);

  useEffect(() => {
    if (did.current) return;
    did.current = true;

    // Avoid flooding the console: best-effort, fully silent.
    (async () => {
      // Warmup OCR (optional on backend)
      try {
        await fetch("/api/ocr/warmup", { method: "GET" });
        // ignore non-200s; do not console.log
      } catch {
        /* ignore */
      }

      // Probe local history preview (optional on backend)
      try {
        await fetch("/api/history/local?limit=5", { method: "GET" });
      } catch {
        /* ignore */
      }
    })();
  }, []);

  return <>{children}</>;
}
