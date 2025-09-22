// src/context/UserProvider.tsx
import { createContext, useContext, useMemo, useState, ReactNode } from "react";

type UserCtx = {
  userId: string;
  setUserId: (id: string) => void;
};
const Ctx = createContext<UserCtx | undefined>(undefined);

export function UserProvider({ children }: { children: ReactNode }) {
  const [userId, setUserId] = useState<string>("local");
  const value = useMemo(() => ({ userId, setUserId }), [userId]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useUser() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useUser must be used within UserProvider");
  return ctx;
}
