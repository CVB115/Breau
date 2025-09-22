// src/hooks/useBrewHistory.ts
import { useCallback, useEffect, useMemo, useState } from "react";
import useProfile from "./useProfile";
import {
  getHistory,
  appendSession,
  updateSession,
  removeSession,
  clearHistory,
  HistorySession,
} from "../utils/historyLocal";

export default function useBrewHistory() {
  const { data: profile } = useProfile();
  const userId = profile?.userId || "default-user";

  const [sessions, setSessions] = useState<HistorySession[]>([]);

  const refresh = useCallback(() => setSessions(getHistory(userId)), [userId]);

  useEffect(() => { refresh(); }, [refresh]);

  const add = useCallback((session: HistorySession) => {
    const id = appendSession(userId, session);
    setSessions(getHistory(userId));
    return id;
  }, [userId]);

  const patch = useCallback((id: string, patch: Partial<HistorySession>) => {
    updateSession(userId, id, patch);
    setSessions(getHistory(userId));
  }, [userId]);

  const remove = useCallback((id: string) => {
    removeSession(userId, id);
    setSessions(getHistory(userId));
  }, [userId]);

  const clearAll = useCallback(() => {
    clearHistory(userId);
    setSessions([]);
  }, [userId]);

  const count = useMemo(() => sessions.length, [sessions]);

  return { userId, sessions, count, refresh, add, patch, remove, clearAll, setSessions };
}
