// src/hooks/useBeansLibrary.ts
import { useCallback, useEffect, useMemo, useState } from "react";
import { mirrorKey, readMirror, writeMirror } from "../utils/localMirror";
import useProfile from "./useProfile";

export type Bean = {
  id: string;
  name: string;
  roaster?: string;
  origin?: string;
  variety?: string;
  process?: string;
  roast_level?: string;
  image_url?: string;
  retired?: boolean;
  [k: string]: any;
};
type Bag = { items: Bean[] };

const asArray = <T,>(x: unknown): T[] => (Array.isArray(x) ? (x as T[]) : []);
const genId = () => {
  try { // @ts-ignore
    if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  } catch {}
  return `id_${Math.random().toString(36).slice(2)}_${Date.now()}`;
};

export default function useBeansLibrary() {
  const { data: profile } = useProfile();
  const userId = profile?.userId || "default-user";
  const KEY = mirrorKey.beans(userId);

  const [items, setItems] = useState<Bean[]>([]);

  useEffect(() => {
    const cached = readMirror<Bag>(KEY, { items: [] });
    setItems(asArray<Bean>(cached?.items));
  }, [KEY]);

  const persist = useCallback((next: Bean[]) => {
    writeMirror<Bag>(KEY, { items: next });
    setItems(next);
  }, [KEY]);

  const add = useCallback(async (bean: Omit<Bean, "id">, id?: string) => {
    const newId = id ?? genId();
    const next = [{ id: newId, ...bean }, ...items] as Bean[];
    persist(next);
    (async () => {
      try {
        await fetch("/api/library/beans", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id: newId, ...bean }),
        });
      } catch {}
    })();
    return newId;
  }, [items, persist]);

  const update = useCallback((id: string, patch: Partial<Bean>) => {
    persist(items.map(b => (b.id === id ? { ...b, ...patch } : b)));
    (async () => {
      try {
        await fetch(`/api/library/beans/${encodeURIComponent(id)}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(patch),
        });
      } catch {}
    })();
  }, [items, persist]);

  const retire  = useCallback((id: string, retired = true) => update(id, { retired }), [update]);
  const remove  = useCallback((id: string) => {
    persist(items.filter(b => b.id !== id));
    (async () => { try { await fetch(`/api/library/beans/${encodeURIComponent(id)}`, { method: "DELETE" }); } catch {} })();
  }, [items, persist]);

  const active      = useMemo(() => items.filter(b => !b.retired), [items]);
  const retiredList = useMemo(() => items.filter(b => b.retired), [items]);
  const listKey     = useMemo(() => `${items.length}:${items.map(b => b.id).join("|")}`, [items]);

  return { items, active, retired: retiredList, listKey, add, update, retire, remove, setItems };
}
