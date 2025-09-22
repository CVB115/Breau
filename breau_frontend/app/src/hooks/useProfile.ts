// src/hooks/useProfile.ts
import { useCallback, useEffect, useState } from "react";
import { readMirror, writeMirror, mirrorKey } from "../utils/localMirror";

export type Profile = {
  userId: string;
  name?: string;
  avatar_url?: string;
  [k: string]: any;
};
type Bag = { data: Profile };

const DEFAULT: Profile = { userId: "default-user", name: "" };

export default function useProfile() {
  const [data, setData] = useState<Profile>(DEFAULT);

  useEffect(() => {
    const cached = readMirror<Bag>(mirrorKey.profile(), { data: DEFAULT });
    setData({ ...DEFAULT, ...(cached?.data ?? {}) });
  }, []);

  const save = useCallback((next: Profile) => {
    setData(next);
    writeMirror<Bag>(mirrorKey.profile(), { data: next });
  }, []);

  const setName = useCallback((name: string) => save({ ...data, name }), [data, save]);
  const setUserId = useCallback((userId: string) => save({ ...data, userId }), [data, save]);

  return { data, save, setName, setUserId };
}
