// src/context/ToastProvider.tsx
import { createContext, useCallback, useContext, useMemo, useState } from "react";

type Toast = { id: string; kind?: "success" | "error" | "info"; text: string; ttl?: number };
type Ctx = {
  toasts: Toast[];
  toast: (text: string, kind?: Toast["kind"], ttlMs?: number) => void;
  remove: (id: string) => void;
};

const C = createContext<Ctx | null>(null);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const remove = useCallback((id: string) => {
    setToasts((t) => t.filter((x) => x.id !== id));
  }, []);

  const toast = useCallback((text: string, kind: Toast["kind"] = "info", ttlMs = 2500) => {
    const id = Math.random().toString(36).slice(2);
    const t: Toast = { id, text, kind, ttl: ttlMs };
    setToasts((prev) => [...prev, t]);
    if (ttlMs > 0) setTimeout(() => remove(id), ttlMs);
  }, [remove]);

  const value = useMemo(() => ({ toasts, toast, remove }), [toasts, toast, remove]);

  return (
    <C.Provider value={value}>
      {children}
      <div className="toast-wrap">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.kind || "info"}`} onClick={() => remove(t.id)}>
            {t.text}
          </div>
        ))}
      </div>
    </C.Provider>
  );
}

export function useToast() {
  const ctx = useContext(C);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}
