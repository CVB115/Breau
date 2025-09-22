// src/pages/Profile/index.tsx
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useUser } from "@context/UserProvider";
import APIStatus from "@components/APIStatus";
import { api } from "@api/client";
import { API } from "@api/endpoints";
import { readMirror, mirrorKey } from "@utils/localMirror";
import useBeansLibrary from "@hooks/useBeansLibrary";

/** Build a friendly gear label */
function gearToLabel(g: any): string {
  if (!g) return "—";
  if (g.label) return g.label;
  const brewer = g.brewer?.name || "Brewer";
  const grinder = [g.grinder?.brand, g.grinder?.model].filter(Boolean).join(" ") || "Grinder";
  const water = g.water?.name || "Water";
  return [brewer, grinder, water].join(" • ");
}

function useProfileHeaderData(userId: string) {
  const [name, setName] = useState("");
  const [beanStats, setBeanStats] = useState({ active: 0, retired: 0 });
  const [gearLabel, setGearLabel] = useState("—");
  const [lastBrew, setLastBrew] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      // --- profile name -------------------------------------------------
      try {
        const profileInfoPath =
          (API as any).profileInfo
            ? (API as any).profileInfo(userId)
            : `/api/profile/${encodeURIComponent(userId)}`;
        const p = await api.get<any>(profileInfoPath);
        if (p?.name) setName(p.name);
      } catch {
        try {
          const raw = localStorage.getItem(`breau.profile.${userId}`);
          const p = JSON.parse(raw || "null");
          if (p?.name) setName(p.name);
        } catch {}
      }

      // --- beans stats (server, then local fallback) --------------------
      try {
        const beansPath =
          (API as any).profileBeans
            ? (API as any).profileBeans(userId)
            : `/api/profile/${encodeURIComponent(userId)}/beans`;
        const r = await api.get<any>(beansPath);
        const server: any[] =
          Array.isArray(r) ? r :
          Array.isArray(r?.beans) ? r.beans :
          Array.isArray(r?.data) ? r.data :
          [];
        const active = server.filter((b) => b?.state !== "retired").length;
        const retired = Math.max(server.length - active, 0);
        setBeanStats({ active, retired });
      } catch {}

      try {
        const localBeans = readMirror<any[]>(mirrorKey.beans(userId), []);
        if (Array.isArray(localBeans)) {
          const active = localBeans.filter((b) => b?.state !== "retired").length;
          const retired = Math.max(localBeans.length - active, 0);
          setBeanStats({ active, retired });
        }
      } catch {}

      // --- gear label ---------------------------------------------------
      try {
        const localGear = readMirror<any>(mirrorKey.gearActive(userId), null);
        if (localGear) setGearLabel(gearToLabel(localGear));
      } catch {}

      // --- last brew (best effort) -------------------------------------
      try {
        const raw = localStorage.getItem(`breau.history.${userId}`);
        if (raw) {
          const obj = JSON.parse(raw);
          const first = Array.isArray(obj)
            ? obj[0]
            : (Object.values(obj ?? {}) as any[]).sort((a, b) =>
                String(b?.started_at || b?.updated_at || "").localeCompare(
                  String(a?.started_at || a?.updated_at || "")
                )
              )[0];
          if (first?.recipe_name || first?.title) {
            setLastBrew(first.recipe_name || first.title);
          }
        }
      } catch {}
    })();
  }, [userId]);

  return { name, beanStats, gearLabel, lastBrew };
}

export default function ProfileIndex() {
  const { userId } = useUser();
  const nav = useNavigate();
  const { name, beanStats, gearLabel, lastBrew } = useProfileHeaderData(userId);

  // Same source as Beans page so counts always match
  const beansLib = useBeansLibrary() as any;
  const beansItems = (beansLib?.items ?? []) as Array<{ retired?: boolean }>;
  const beansActive = beansItems.filter((b) => !b?.retired).length;
  const beansRetired = Math.max(beansItems.length - beansActive, 0);

  const initials =
    name.trim().split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase() || "AB";

  return (
    <main className="page">
      {/* Header */}
      <div className="card row profile-header">
        <div className="avatar">{initials}</div>
        <div className="info">
          <div className="name">{name || "Welcome"}</div>
          <div className="meta">ID: {userId}</div>
          <div className="stats">
            <span>{beansActive} active</span>
            <span>•</span>
            <span>{beansRetired} retired</span>
            <span>•</span>
            <span>{gearLabel}</span>
          </div>
          {lastBrew && <div className="last">Last: {lastBrew}</div>}
        </div>
        <div className="actions">
          <button className="btn secondary" onClick={() => nav("/profile/edit")}>
            Edit
          </button>
          <APIStatus />
        </div>
      </div>

      {/* Cards grid – uses your .grid-2col to avoid stacking */}
      <div className="grid-2col">
        <ProfileCard
          icon="🫘"
          title="Beans"
          desc="Scan bags or add beans manually."
          stat={`${beansActive} active • ${beansRetired} retired`}
          to="/profile/beans"
          altTo="?scan=1"
        />
        <ProfileCard
          icon="⚙️"
          title="Gear"
          desc="Set active combo (brewer + grinder)."
          stat={gearLabel}
          to="/profile/gear"
        />
        <ProfileCard
          icon="✨"
          title="Taste & Goals"
          desc="Save goals, launch Suggested."
          to="/profile/taste-goals"
        />
        <ProfileCard
          icon="🛠"
          title="Settings"
          desc="Units, overlays, voice toggles."
          to="/profile/settings"
        />
        <ProfileCard
          icon="⬇️"
          title="Export & Reset"
          desc="Export JSON, clear local cache."
          to="/profile/export-reset"
        />
        <ProfileCard
          icon="🧪"
          title="Developer Tools"
          desc="Suggest mode, API base, test."
          to="/profile/devtools"
        />
      </div>
    </main>
  );
}

function ProfileCard({
  icon,
  title,
  desc,
  stat,
  to,
  altTo,
}: {
  icon: string;
  title: string;
  desc: string;
  stat?: string;
  to: string;
  altTo?: string;
}) {
  return (
    <div className="card col profile-card">
      <div className="row" style={{ alignItems: "center", gap: 12 }}>
        <div className="profile-icon">{icon}</div>
        <div className="col">
          <h2 style={{ margin: 0 }}>{title}</h2>
          <div style={{ fontSize: 13, opacity: 0.8 }}>{desc}</div>
        </div>
      </div>
      {stat && (
        <div style={{ fontSize: 12, marginTop: 4, opacity: 0.7 }}>{stat}</div>
      )}
      <div className="row" style={{ gap: 8, marginTop: 8 }}>
        <Link to={to} className="btn">Open</Link>
        {altTo && <Link to={to + altTo} className="btn secondary">Scan</Link>}
      </div>
    </div>
  );
}
