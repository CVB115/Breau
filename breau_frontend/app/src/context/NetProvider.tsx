// src/context/NetProvider.tsx
import { useEffect, useMemo, useState } from "react";
import { registerNetTap } from "@api/client";

// Discriminated union we use internally (loose & compatible)
type RequestEvent = {
  phase: "request";
  method: string;
  url: string;
  ts?: number;
  headers?: any;
  body?: any;
};

type ResponseEvent = {
  phase: "response";
  method: string;
  url: string;
  status?: number;
  body?: any;
};

type ErrorEvent = {
  phase: "error";
  method: string;
  url: string;
  status?: number;
  message?: string;
  body?: any;
};

type AnyEvent = RequestEvent | ResponseEvent | ErrorEvent;

type Row = {
  id: string;
  req?: RequestEvent;
  res?: ResponseEvent;
  err?: ErrorEvent;
};

export default function NetProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState<Row[]>([]);

  useEffect(() => {
    // NOTE: don't annotate the param — let it be whatever @api/client expects.
    const off = registerNetTap((rawEv) => {
      const ev = rawEv as unknown as AnyEvent; // single cast, then narrow below

      setRows((prev) => {
        if (ev.phase === "request") {
          const ts = typeof (ev as RequestEvent).ts === "number" ? (ev as RequestEvent).ts! : Date.now();
          const id = `${ev.method} ${ev.url} ${ts}`;
          return [{ id, req: ev as RequestEvent }, ...prev].slice(0, 200);
        }

        // match latest row of same method+url without response/err
        const idx = prev.findIndex(
          (r) => r.req && r.req.method === ev.method && r.req.url === ev.url && !r.res && !r.err
        );
        if (idx === -1) return prev;

        const copy = [...prev];
        const base = copy[idx];

        if (ev.phase === "response") {
          copy[idx] = { ...base, res: ev as ResponseEvent };
        } else {
          copy[idx] = { ...base, err: ev as ErrorEvent };
        }
        return copy;
      });
    });

    return off;
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "`") setOpen((o) => !o);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const content = useMemo(() => rows, [rows]);

  return (
    <>
      {children}
      {!open && (
        <button
          className="net-pill"
          title="Open Network Console (Ctrl/⌘ + `)"
          onClick={() => setOpen(true)}
        >
          Net
        </button>
      )}
      {open && (
        <div className="net-overlay">
          <div className="net-bar">
            <strong>Network Console</strong>
            <div className="net-actions">
              <button onClick={() => setRows([])}>Clear</button>
              <button onClick={() => setOpen(false)}>Close</button>
            </div>
          </div>

          <div className="net-body">
            {content.length === 0 && <div className="net-empty">No requests yet.</div>}

            {content.map((r) => {
              const status = r.err?.status ?? r.res?.status;
              const ok = status && status >= 200 && status < 300;
              return (
                <div key={r.id} className={`net-row ${ok ? "ok" : r.err ? "err" : ""}`}>
                  <div className="net-head">
                    <span className="net-method">{r.req?.method}</span>
                    <span className="net-url">{r.req?.url}</span>
                    {status != null && <span className="net-status">{status}</span>}
                  </div>

                  {r.req && (
                    <details>
                      <summary>Request</summary>
                      <pre>{JSON.stringify({ headers: r.req.headers, body: r.req.body }, null, 2)}</pre>
                    </details>
                  )}

                  {r.res && (
                    <details open>
                      <summary>Response</summary>
                      <pre>{JSON.stringify(r.res.body, null, 2)}</pre>
                    </details>
                  )}

                  {r.err && (
                    <details open>
                      <summary>Error</summary>
                      <pre>
                        {JSON.stringify(
                          { status: r.err.status, body: r.err.body, message: r.err.message },
                          null,
                          2
                        )}
                      </pre>
                    </details>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </>
  );
}
