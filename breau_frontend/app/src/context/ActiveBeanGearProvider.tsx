// src/context/ActiveBeanGearProvider.tsx
import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import useProfile from "../hooks/useProfile";
import { readMirror, writeMirror } from "../utils/localMirror";

const keyActive = (userId: string) => `breau.active_gear.${userId}`;
const LEGACY_PROFILE = "breau.profile";

export type ActiveGear = {
  brewer?: any;
  grinder?: any;
  filter?: any;
  water?: any;
  label?: string;
};

function readActiveGear(userId: string): ActiveGear | null {
  const newest = readMirror<ActiveGear | null>(keyActive(userId), null);
  if (newest) return newest;

  const prof = readMirror<any>(LEGACY_PROFILE, null);
  return (
    prof?.active_gear ||
    prof?.gear?.active ||
    prof?.preferences?.active_gear ||
    null
  );
}

function writeActive(userId: string, gear: ActiveGear) {
  writeMirror(keyActive(userId), gear);
  const prof = readMirror<any>(LEGACY_PROFILE, {}) || {};
  const next = {
    ...prof,
    active_gear: gear,
    gear: { ...(prof.gear || {}), active: gear },
  };
  writeMirror(LEGACY_PROFILE, next);
}

type Ctx = { active: ActiveGear | null; setActive: (g: ActiveGear) => void };
const GearCtx = createContext<Ctx>({ active: null, setActive: () => {} });

export function ActiveBeanGearProvider({ children }: { children: React.ReactNode }) {
  const { data: profile } = useProfile();
  const userId = profile?.userId || "default-user";

  const [active, setActive] = useState<ActiveGear | null>(null);

  useEffect(() => {
    setActive(readActiveGear(userId));
  }, [userId]);

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (!e.key) return;
      if (e.key.startsWith("breau.active_gear.") || e.key === LEGACY_PROFILE) {
        setActive(readActiveGear(userId));
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [userId]);

  const value = useMemo<Ctx>(
    () => ({
      active,
      setActive: (g) => {
        writeActive(userId, g);
        setActive(g);
      },
    }),
    [active, userId]
  );

  return <GearCtx.Provider value={value}>{children}</GearCtx.Provider>;
}

export function useActiveGear() {
  return useContext(GearCtx);
}

export function useActiveBeanGear() {
  return useActiveGear();
}

export default ActiveBeanGearProvider;
