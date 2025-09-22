// src/utils/migrateMirror.ts
import { readMirror, writeMirror, mirrorKey } from "./localMirror";

type BeansBag = { items?: any[] };
type GearBag  = { items?: any[] };
type ProfileBag = { data?: { userId?: string; name?: string; [k: string]: any } };
type PrefsBag = Record<string, any>;
type HistoryBag = { sessions?: any[] };

// Old ad-hoc keys to migrate from (safe to keep even if unused)
const OLD_KEYS = {
  beans: "beans_library_v1",
  gear: "gear_library_v1",
  profile: "profile_v1",
  prefs: "preferences_v1",
  history: "history_v1",
};

function pickUserId(): string {
  const p = readMirror<ProfileBag>(OLD_KEYS.profile, { data: { userId: "default-user" } });
  return p?.data?.userId || "default-user";
}

export function migrateMirrorOnBoot(): void {
  const userId = pickUserId();

  // ---- profile (canonical global) ----
  const oldProfile = readMirror<ProfileBag>(OLD_KEYS.profile, { data: { userId, name: "" } });
  const currentProfile = readMirror<ProfileBag | undefined>(mirrorKey.profile(), undefined as any);
  if (!currentProfile?.data && oldProfile?.data) {
    writeMirror(mirrorKey.profile(), { data: { userId: oldProfile.data.userId ?? userId, ...oldProfile.data } });
  } else if (!currentProfile) {
    writeMirror(mirrorKey.profile(), { data: { userId, name: "" } });
  }

  // ---- beans ----
  const oldBeans = readMirror<BeansBag>(OLD_KEYS.beans, { items: [] });
  const newBeans = readMirror<BeansBag | undefined>(mirrorKey.beans(userId), undefined as any);
  if (!newBeans?.items && oldBeans?.items?.length) {
    writeMirror(mirrorKey.beans(userId), { items: oldBeans.items });
  }

  // ---- gear ----
  const oldGear = readMirror<GearBag>(OLD_KEYS.gear, { items: [] });
  const newGear = readMirror<GearBag | undefined>(mirrorKey.gear(userId), undefined as any);
  if (!newGear?.items && oldGear?.items?.length) {
    writeMirror(mirrorKey.gear(userId), { items: oldGear.items });
  }

  // ---- preferences ----
  const oldPrefs = readMirror<PrefsBag>(OLD_KEYS.prefs, {});
  const newPrefs = readMirror<PrefsBag | undefined>(mirrorKey.preferences(userId), undefined as any);
  if (!newPrefs && oldPrefs && Object.keys(oldPrefs).length) {
    writeMirror(mirrorKey.preferences(userId), oldPrefs);
  }

  // ---- history ----
  const oldHistory = readMirror<HistoryBag>(OLD_KEYS.history, { sessions: [] });
  const newHistory = readMirror<HistoryBag | undefined>(mirrorKey.history(userId), undefined as any);
  if (!newHistory?.sessions && oldHistory?.sessions?.length) {
    writeMirror(mirrorKey.history(userId), { sessions: oldHistory.sessions });
  }
}
