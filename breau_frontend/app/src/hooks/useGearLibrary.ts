// src/hooks/useGearLibrary.ts
import { useCallback, useEffect, useMemo, useState } from "react";
import { mirrorKey, readMirror, writeMirror } from "../utils/localMirror";
import useProfile from "./useProfile";

export type Gear = {
  id: string;
  name: string;
  type?: "dripper" | "espresso" | "grinder" | "kettle" | "scale" | "filter" | string;
  notes?: string;
  retired?: boolean;
  [k: string]: any;
};
type Bag = { items: Gear[] };

const asArray = <T,>(x: unknown): T[] => (Array.isArray(x) ? (x as T[]) : []);
const genId = () => {
  try { // @ts-ignore
    if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  } catch {}
  return `id_${Math.random().toString(36).slice(2)}_${Date.now()}`;
};

export default function useGearLibrary() {
  const { data: profile } = useProfile();
  const userId = profile?.userId || "default-user";
  const KEY = mirrorKey.gear(userId);

  const [gear, setGear] = useState<Gear[]>([]);

  useEffect(() => {
    const cached = readMirror<Bag>(KEY, { items: [] });
    setGear(asArray<Gear>(cached?.items));
  }, [KEY]);

  const persist = useCallback((next: Gear[]) => {
    writeMirror<Bag>(KEY, { items: next });
    setGear(next);
  }, [KEY]);

  const add = useCallback(async (g: Omit<Gear, "id">, id?: string) => {
    const newId = id ?? genId();
    const next = [{ id: newId, ...g }, ...gear] as Gear[];
    persist(next);
    return newId;
  }, [gear, persist]);

  const update = useCallback((id: string, patch: Partial<Gear>) => {
    persist(gear.map(x => (x.id === id ? { ...x, ...patch } : x)));
  }, [gear, persist]);

  const retire = useCallback((id: string, retired = true) => update(id, { retired }), [update]);
  const remove = useCallback((id: string) => persist(gear.filter(x => x.id !== id)), [gear, persist]);

  const active      = useMemo(() => gear.filter(g => !g.retired), [gear]);
  const retiredList = useMemo(() => gear.filter(g => g.retired), [gear]);
  const listKey     = useMemo(() => `${gear.length}:${gear.map(g => g.id).join("|")}`, [gear]);

  return { gear, active, retired: retiredList, listKey, add, update, retire, remove, setGear };
}
