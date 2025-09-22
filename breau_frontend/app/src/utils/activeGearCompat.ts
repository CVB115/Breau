// src/utils/activeGearCompat.ts
import { mirrorKey, readMirror, writeMirror } from "./localMirror";

/** Legacy profile root where older code stashed active gear blobs */
const LEGACY_PROFILE_KEY = "breau.profile";

export type ActiveGear = {
  brewer?: any;
  grinder?: any;
  filter?: any;
  water?: any;
  label?: string;
};

/** Read active gear with backward compatibility (new key, then legacy) */
export function readActiveGear(userId: string): ActiveGear | null {
  // 1) preferred new key
  const fromNew = readMirror<ActiveGear | null>(mirrorKey.gearActive(userId), null);
  if (fromNew) return fromNew;

  // 2) legacy: profile.active_gear or profile.gear.active
  const prof = readMirror<any>(LEGACY_PROFILE_KEY, {}) || {};
  if (prof?.active_gear) return prof.active_gear as ActiveGear;
  if (prof?.gear?.active) return prof.gear.active as ActiveGear;

  return null;
}

/** Write active gear to the new key, mirror to legacy profile (best‑effort) */
export function writeActiveGear(userId: string, gear: ActiveGear) {
  // write to the new canonical key
  writeMirror(mirrorKey.gearActive(userId), gear);

  // also keep legacy profile consistent (best‑effort, won’t throw)
  const prof = readMirror<any>(LEGACY_PROFILE_KEY, {}) || {};
  const next = {
    ...prof,
    active_gear: gear,
    gear: { ...(prof.gear || {}), active: gear },
  };
  writeMirror(LEGACY_PROFILE_KEY, next);
}
