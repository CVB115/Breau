// src/api/client.ts
export type Json = Record<string, any>;

const API_BASE =
  (import.meta as any)?.env?.VITE_API_BASE?.replace(/\/+$/, "") || "/api";

// ---- net tap (for NetProvider) --------------------------------------------
type NetTap = (e: {
  url: string;
  method: string;
  ok: boolean;
  status?: number;
  ms: number;
  error?: string;
}) => void;

const netTaps: NetTap[] = [];
export function registerNetTap(fn: NetTap) {
  netTaps.push(fn);
  return () => {
    const i = netTaps.indexOf(fn);
    if (i >= 0) netTaps.splice(i, 1);
  };
}
function notifyTap(e: Parameters<NetTap>[0]) {
  for (const fn of netTaps) {
    try { fn(e); } catch {}
  }
}

// ---- helpers ---------------------------------------------------------------
function isAbsolute(url: string) {
  return /^https?:\/\//i.test(url);
}
function join(base: string, part: string) {
  if (!part) return base;
  if (isAbsolute(part)) return part;
  if (part.startsWith("/")) return `${base}${part}`; // "/foo" -> "/api/foo"
  return `${base}/${part}`;                           // "foo"  -> "/api/foo"
}

async function doFetch(path: string, init: RequestInit = {}) {
  // allow callers to pass "sessions/start" or "/api/sessions/start"
  const normalized = path.replace(/^\/?api\/?/, "");
  const url = join(API_BASE, normalized);

  const started = performance.now();
  const method = (init.method || "GET").toUpperCase();

  const opts: RequestInit = { ...init };

  // JSON encode if body is a plain object (not FormData / string)
  const isFD = typeof FormData !== "undefined" && opts.body instanceof FormData;
  if (opts.body && !isFD && typeof opts.body !== "string") {
    opts.headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
    opts.body = JSON.stringify(opts.body);
  }

  try {
    const res = await fetch(url, opts);
    const ms = Math.max(0, performance.now() - started);
    const ct = res.headers.get("content-type") || "";

    notifyTap({ url, method, ok: res.ok, status: res.status, ms });

    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(text || `${res.status} ${res.statusText}`);
    }
    if (res.status === 204) return null;
    return ct.includes("application/json") ? res.json() : res.text();
  } catch (err: any) {
    const ms = Math.max(0, performance.now() - started);
    notifyTap({ url, method, ok: false, ms, error: String(err?.message || err) });
    throw err;
  }
}

/** Low-level helper: `http("/sessions/start", { method:"POST", body })` */
export function http(path: string, init: RequestInit = {}) {
  return doFetch(path, init);
}

// ---- public API ------------------------------------------------------------
const api = {
  get<T = any>(path: string, init?: RequestInit) {
    return http(path, { ...(init || {}), method: "GET" }) as Promise<T>;
  },
  post<T = any>(path: string, body?: Json | FormData, init?: RequestInit) {
    // cast body so RequestInit type-check passes; doFetch() will stringify JSON
    return http(path, { ...(init || {}), method: "POST", body: body as any }) as Promise<T>;
  },
  put<T = any>(path: string, body?: Json | FormData, init?: RequestInit) {
    return http(path, { ...(init || {}), method: "PUT", body: body as any }) as Promise<T>;
  },
  del<T = any>(path: string, init?: RequestInit) {
    return http(path, { ...(init || {}), method: "DELETE" }) as Promise<T>;
  },
};

export default api;
export { api, API_BASE };
