// src/hooks/useHomeData.ts
import { useMemo } from "react";
import useBeansLibrary from "./useBeansLibrary";
import useGearLibrary from "./useGearLibrary";
import useProfile from "./useProfile";

export default function useHomeData() {
  const { items: beans, active, retired } = useBeansLibrary();
  const { gear } = useGearLibrary();
  const { data: profile } = useProfile();

  return useMemo(
    () => ({
      beans: { total: beans.length, active: active.length, retired: retired.length },
      gear: { total: gear.length },
      profile,
    }),
    [beans, active, retired, gear, profile]
  );
}
