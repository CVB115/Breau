// src/pages/profile/Gear.tsx
import { useEffect, useMemo, useState } from "react";
import { useUser } from "@context/UserProvider";
import useProfile from "@hooks/useProfile";
import { useToast } from "@context/ToastProvider";
import { api } from "@api/client";
import { API } from "@api/endpoints";

import {
  // catalogs + minimal add flows
  getBrewers, addBrewerMinimal,
  getGrinders, addGrinderFlexible,
  getFilters, addFilterMinimal,
  getWaters,  addWaterMinimal,
  // option helpers for UI hints
  GEOMETRY_OPTIONS, METHOD_OPTIONS,
  FILTER_MATERIAL_OPTIONS, FILTER_THICKNESS_OPTIONS,
  WATER_STYLE_OPTIONS,
  // types
  type Brewer, type Grinder, type Filter, type Water,
} from "@api/library";

import { mirrorKey, readMirror, writeMirror } from "@utils/localMirror";

type Tab = "brewer" | "grinder" | "filter" | "water";

export default function Gear() {
  const { userId } = useUser();
  const { data: profile, save } = useProfile(); // hook reads user from context
  const { toast } = useToast();

  const [tab, setTab] = useState<Tab>("brewer");
  const [q, setQ] = useState("");

  // catalogs
  const [brewers, setBrewers] = useState<Brewer[]>([]);
  const [grinders, setGrinders] = useState<Grinder[]>([]);
  const [filters, setFilters] = useState<Filter[]>([]);
  const [waters, setWaters]   = useState<Water[]>([]);
  const [loading, setLoading] = useState(true);

  // current selection
  const [selBrewer, setSelBrewer] = useState<Brewer | undefined>(undefined);
  const [selGrinder, setSelGrinder] = useState<Grinder | undefined>(undefined);
  const [selFilter, setSelFilter] = useState<Filter | undefined>(undefined);
  const [selWater, setSelWater] = useState<Water | undefined>(undefined);

  // hydrate from local active gear mirror first (instant)
  useEffect(() => {
    const mirrored = readMirror<any>(mirrorKey.gearActive(userId), null);
    if (mirrored) applyActiveGearFromServer(mirrored);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId]);

  // legacy: profile.active_gear (offline OK)
  useEffect(() => {
    if (!profile?.active_gear) return;
    const g = profile.active_gear as any;
    setSelBrewer(g.brewer);
    setSelGrinder(g.grinder);
    setSelFilter(g.filter);
    setSelWater(g.water);
  }, [profile?.active_gear]);

  // preferred: backend snapshot
  useEffect(() => {
    let cancel = false;
    (async () => {
      try {
        const res = await api.get<any>(API.profileActiveGear(userId));
        if (cancel) return;
        const g = res?.gear ?? res?.active_gear ?? null;
        if (g) {
          applyActiveGearFromServer(g);
          writeMirror(mirrorKey.gearActive(userId), g);
        }
      } catch {
        // fine: stay with profile/local mirror
      }
    })();
    return () => { cancel = true; };
  }, [userId]);

  // load catalogs from our new library API
  useEffect(() => {
    let cancel = false;
    (async () => {
      setLoading(true);
      try {
        const [br, gr, fi, wa] = await Promise.all([
          Promise.resolve(getBrewers()),
          Promise.resolve(getGrinders()),
          Promise.resolve(getFilters()),
          Promise.resolve(getWaters()),
        ]);
        if (!cancel) {
          setBrewers(br);
          setGrinders(gr);
          setFilters(fi);
          setWaters(wa);
        }
      } finally {
        if (!cancel) setLoading(false);
      }
    })();
    return () => { cancel = true; };
  }, []);

  async function saveActive() {
    const payload = buildPayload(selBrewer, selGrinder, selFilter, selWater);
    if (!payload) {
      toast("Pick at least a brewer and a grinder.", "error");
      return;
    }

    // canonical API
    try {
      const res = await api.post<any>(API.setActiveGear(userId), { gear: payload });
      const out = res?.gear ?? payload;
      writeMirror(mirrorKey.gearActive(userId), out);
      toast("Active gear saved", "success");
      return;
    } catch {
      // fall through
    }

    // fallback: store in profile
    try {
      await save({ active_gear: payload } as any);
      writeMirror(mirrorKey.gearActive(userId), payload);
      toast("Saved locally (backend unavailable).", "info");
    } catch {
      writeMirror(mirrorKey.gearActive(userId), payload);
      toast("Saved locally (backend unavailable).", "info");
    }
  }

  // search filtering
  const brList = useMemo(() => filterByQuery(brewers, q, ["name", "method"]), [brewers, q]);
  const grList = useMemo(() => filterByQuery(grinders, q, ["brand", "model", "burr_type"]), [grinders, q]);
  const fiList = useMemo(() => filterByQuery(filters, q, ["name", "material"]), [filters, q]);
  const waList = useMemo(() => filterByQuery(waters, q, ["name", "style"]), [waters, q]);

  return (
    <main className="page">
      <div className="card col">
        <h2>Gear</h2>
        <p style={{ opacity: 0.85, marginTop: -6 }}>Choose brewer, grinder, filter & water. Works offline.</p>

        {/* tabs */}
        <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
          {(["brewer", "grinder", "filter", "water"] as Tab[]).map((t) => (
            <button
              key={t}
              className={`nav-btn ${tab === t ? "active" : ""}`}
              onClick={() => setTab(t)}
              style={{ padding: "6px 10px" }}
            >
              {t[0].toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>

        {/* search */}
        <div className="row" style={{ gap: 8, marginTop: 8 }}>
          <input placeholder="Search…" value={q} onChange={(e) => setQ(e.target.value)} />
          <button className="btn secondary" onClick={() => setQ("")}>Clear</button>
        </div>

        {/* lists */}
        <div className="card col" style={{ marginTop: 10 }}>
          {loading && (<><div className="skeleton" /><div className="skeleton" /></>)}

          {!loading && tab === "brewer" && brList.map((b) => (
            <Row key={b.id} active={selBrewer?.id === b.id} onPick={() => setSelBrewer(b)}>
              <strong>{b.name}</strong>
              <span style={{ opacity: 0.8 }}> · {b.method}</span>
              <span style={{ opacity: 0.6, fontSize: 12, marginLeft: 6 }}>{b.geometry}</span>
            </Row>
          ))}

          {!loading && tab === "grinder" && grList.map((g) => (
            <Row key={g.id} active={selGrinder?.id === g.id} onPick={() => setSelGrinder(g)}>
              <strong>{[g.brand, g.model].filter(Boolean).join(" ")}</strong>
              <span style={{ opacity: 0.8 }}> · {g.burr_type}</span>
            </Row>
          ))}

          {!loading && tab === "filter" && fiList.map((f) => (
            <Row key={f.id} active={selFilter?.id === f.id} onPick={() => setSelFilter(f)}>
              <strong>{f.name}</strong>
              <span style={{ opacity: 0.8, marginLeft: 6 }}>{[f.material, f.thickness].filter(Boolean).join(" · ")}</span>
            </Row>
          ))}

          {!loading && tab === "water" && waList.map((w) => (
            <Row key={w.id} active={selWater?.id === w.id} onPick={() => setSelWater(w)}>
              <strong>{w.name}</strong>
              <span style={{ opacity: 0.8, marginLeft: 6 }}>{w.style}</span>
              {typeof w.minerals?.TDS === "number" && (
                <span style={{ opacity: 0.6, marginLeft: 6, fontSize: 12 }}>TDS {w.minerals.TDS}</span>
              )}
            </Row>
          ))}

          <AddManual
            tab={tab}
            onAdd={(item) => {
              if (tab === "brewer") {
                // minimal: name + geometry (+ optional method)
                const n = addBrewerMinimal({
                  name: item.name,
                  geometry: item.geometry,
                  method: item.method || undefined,
                });
                setBrewers((x) => [n, ...x]);
                setSelBrewer(n);
              } else if (tab === "grinder") {
                // flexible free fields; a/b optional
                const n = addGrinderFlexible({
                  brand: item.brand ?? "",
                  model: item.model ?? "",
                  burr_type: item.burr_type || "conical",
                  scale: item.scale || undefined,
                  a: item.a ?? null,
                  b: item.b ?? null,
                  aliases: item.aliases || undefined,
                });
                setGrinders((x) => [n, ...x]);
                setSelGrinder(n);
              } else if (tab === "filter") {
                // minimal: name + material + thickness (inferred permeability)
                const n = addFilterMinimal({
                  name: item.name,
                  material: item.material,
                  thickness: item.thickness,
                });
                setFilters((x) => [n, ...x]);
                setSelFilter(n);
              } else {
                // minimal: name + style OR name + minerals
                const n = addWaterMinimal({
                  name: item.name,
                  style: item.style || "custom",
                  minerals: item.minerals || undefined,
                  notes: item.notes || undefined,
                });
                setWaters((x) => [n, ...x]);
                setSelWater(n);
              }
              toast("Added to library (local)", "success");
            }}
          />
        </div>

        <div className="row" style={{ gap: 8, marginTop: 10 }}>
          <button className="btn" onClick={saveActive}>Save active combo</button>
        </div>

        {/* current selection */}
        <div className="card col" style={{ marginTop: 12 }}>
          <h3>Active combo</h3>
          <div>Brewer: <strong>{selBrewer?.name || "—"}</strong></div>
          <div>Grinder: <strong>{selGrinder ? [selGrinder.brand, selGrinder.model].filter(Boolean).join(" ") : "—"}</strong></div>
          <div>Filter: <strong>{selFilter?.name || "—"}</strong></div>
          <div>Water: <strong>{selWater?.name || "—"}</strong></div>
        </div>
      </div>
    </main>
  );

  // --- helpers ---\\

    function matchBrewer(list: Brewer[], cand: any): Brewer | undefined {
      if (!cand) return undefined;
      const id = cand?.id as string | undefined;
      const name = String(cand?.name ?? "").toLowerCase();
      const method = String(cand?.method ?? "").toLowerCase();
      const geometry = String(cand?.geometry ?? "").toLowerCase();

      return (
        list.find(b => id && b.id === id) ||
        list.find(b => name && b.name?.toLowerCase() === name) ||
        list.find(
          b =>
            name &&
            method &&
            geometry &&
            b.name?.toLowerCase() === name &&
            String(b.method ?? "").toLowerCase() === method &&
            String(b.geometry ?? "").toLowerCase() === geometry
        )
      );
    }

    function matchGrinder(list: Grinder[], cand: any): Grinder | undefined {
      if (!cand) return undefined;
      const id = cand?.id as string | undefined;
      const brand = String(cand?.brand ?? "").toLowerCase();
      const model = String(cand?.model ?? "").toLowerCase();
      const combo = String(cand?.name ?? "").toLowerCase(); // sometimes server sends a combined label

      return (
        list.find(g => id && g.id === id) ||
        list.find(
          g =>
            brand &&
            model &&
            String(g.brand ?? "").toLowerCase() === brand &&
            String(g.model ?? "").toLowerCase() === model
        ) ||
        list.find(g => combo && [g.brand, g.model].filter(Boolean).join(" ").toLowerCase() === combo)
      );
    }

    function matchFilter(list: Filter[], cand: any): Filter | undefined {
      if (!cand) return undefined;
      const id = cand?.id as string | undefined;
      const name = String(cand?.name ?? "").toLowerCase();
      const material = String(cand?.material ?? "").toLowerCase();
      const thickness = String(cand?.thickness ?? "").toLowerCase();

      return (
        list.find(f => id && f.id === id) ||
        list.find(f => name && (f.name ?? "").toLowerCase() === name) ||
        list.find(
          f =>
            material &&
            thickness &&
            String(f.material ?? "").toLowerCase() === material &&
            String(f.thickness ?? "").toLowerCase() === thickness
        )
      );
    }

    function matchWater(list: Water[], cand: any): Water | undefined {
      if (!cand) return undefined;
      const id = cand?.id as string | undefined;
      const name = String(cand?.name ?? "").toLowerCase();

      return list.find(w => (id && w.id === id) || (name && (w.name ?? "").toLowerCase() === name));
    }

    function applyActiveGearFromServer(g: any) {
      if (g?.brewer) setSelBrewer(matchBrewer(brewers, g.brewer) ?? g.brewer);
      if (g?.grinder) setSelGrinder(matchGrinder(grinders, g.grinder) ?? g.grinder);
      if (g?.filter) setSelFilter(matchFilter(filters, g.filter) ?? g.filter);
      if (g?.water) setSelWater(matchWater(waters, g.water) ?? g.water);
    }

    

  function buildPayload(b?: Brewer, g?: Grinder, f?: Filter, w?: Water) {
    if (!b && !g && !f && !w) return null;
    const label = [
      b?.name || "Brewer",
      [g?.brand, g?.model].filter(Boolean).join(" ") || "Grinder",
      w?.name || "Water",
    ].join(" • ");
    return {
      label,
      brewer: b ? { id: b.id, name: b.name, method: b.method } : undefined,
      grinder: g ? { id: g.id, brand: g.brand, model: g.model, burr_type: g.burr_type } : undefined,
      filter:  f ? { id: f.id, name: f.name, material: f.material, thickness: f.thickness } : undefined,
      water:   w ? { id: w.id, name: w.name, style: w.style, minerals: w.minerals } : undefined,
    };
  }
}

function filterByQuery<T extends Record<string, any>>(arr: T[], q: string, keys: string[]) {
  const s = q.trim().toLowerCase();
  if (!s) return arr;
  return arr.filter((x) => keys.some((k) => String(x[k] ?? "").toLowerCase().includes(s)));
}

function Row(props: { children: React.ReactNode; active?: boolean; onPick?: () => void }) {
  return (
    <div className="row" style={{ justifyContent: "space-between", padding: "6px 0" }}>
      <div className="col">{props.children}</div>
      <button className={`btn ${props.active ? "" : "secondary"}`} onClick={props.onPick}>
        {props.active ? "Selected" : "Select"}
      </button>
    </div>
  );
}

function AddManual({
  tab,
  onAdd,
}: {
  tab: "brewer" | "grinder" | "filter" | "water";
  onAdd: (item: any) => void;
}) {
  const [open, setOpen] = useState(false);
  const [f, setF] = useState<any>({});
  const label = tab === "brewer" ? "Brewer" : tab === "grinder" ? "Grinder" : tab === "filter" ? "Filter" : "Water profile";

  function submit() {
    if (tab === "brewer" && (!f.name || !f.geometry)) return;
    if (tab === "grinder" && (!f.brand || !f.model)) return;
    if (tab === "filter" && (!f.name || !f.material || !f.thickness)) return;
    if (tab === "water" && !f.name) return;
    onAdd(f);
    setOpen(false);
    setF({});
  }

  return (
    <div className="card col" style={{ marginTop: 8 }}>
      {!open && (
        <button className="btn secondary" onClick={() => setOpen(true)}>
          Add manual {label}
        </button>
      )}
      {open && (
        <>
          <h4>Add manual {label}</h4>

          {tab === "brewer" && (
            <>
              <label className="col">
                <span>Name</span>
                <input value={f.name || ""} onChange={(e) => setF({ ...f, name: e.target.value })} />
              </label>
              <label className="col">
                <span>Geometry</span>
                <select value={f.geometry || ""} onChange={(e) => setF({ ...f, geometry: e.target.value })}>
                  <option value="" disabled>Select geometry</option>
                  {GEOMETRY_OPTIONS.map((g) => <option key={g} value={g}>{g}</option>)}
                </select>
                <small style={{ opacity: 0.7 }}>We’ll infer flow_factor; method defaults to pour_over.</small>
              </label>
              <label className="col">
                <span>Method (optional)</span>
                <select value={f.method || ""} onChange={(e) => setF({ ...f, method: e.target.value })}>
                  <option value="">(default: pour_over)</option>
                  {METHOD_OPTIONS.map((m) => <option key={m} value={m}>{m}</option>)}
                </select>
              </label>
            </>
          )}

          {tab === "grinder" && (
            <>
              <label className="col">
                <span>Brand</span>
                <input value={f.brand || ""} onChange={(e) => setF({ ...f, brand: e.target.value })} />
              </label>
              <label className="col">
                <span>Model</span>
                <input value={f.model || ""} onChange={(e) => setF({ ...f, model: e.target.value })} />
              </label>
              <label className="col">
                <span>Burr type</span>
                <select value={f.burr_type || "conical"} onChange={(e) => setF({ ...f, burr_type: e.target.value })}>
                  <option value="conical">conical</option>
                  <option value="flat">flat</option>
                </select>
              </label>
              <details>
                <summary>Advanced calibration (optional)</summary>
                <div className="col" style={{ gap: 8, marginTop: 8 }}>
                  <label className="col">
                    <span>a (microns)</span>
                    <input value={f.a ?? ""} onChange={(e) => setF({ ...f, a: Number(e.target.value) || undefined })} />
                  </label>
                  <label className="col">
                    <span>b (microns/step)</span>
                    <input value={f.b ?? ""} onChange={(e) => setF({ ...f, b: Number(e.target.value) || undefined })} />
                  </label>
                </div>
              </details>
            </>
          )}

          {tab === "filter" && (
            <>
              <label className="col">
                <span>Name</span>
                <input value={f.name || ""} onChange={(e) => setF({ ...f, name: e.target.value })} />
              </label>
              <label className="col">
                <span>Material</span>
                <select value={f.material || ""} onChange={(e) => setF({ ...f, material: e.target.value })}>
                  <option value="" disabled>Select material</option>
                  {FILTER_MATERIAL_OPTIONS.map((m) => <option key={m} value={m}>{m}</option>)}
                </select>
              </label>
              <label className="col">
                <span>Thickness</span>
                <select value={f.thickness || ""} onChange={(e) => setF({ ...f, thickness: e.target.value })}>
                  <option value="" disabled>Select thickness</option>
                  {FILTER_THICKNESS_OPTIONS.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </label>
              <small style={{ opacity: 0.7 }}>Permeability is inferred from material + thickness.</small>
            </>
          )}

          {tab === "water" && (
            <>
              <label className="col">
                <span>Name</span>
                <input value={f.name || ""} onChange={(e) => setF({ ...f, name: e.target.value })} />
              </label>
              <label className="col">
                <span>Style (preset) or “custom”</span>
                <select value={f.style || "custom"} onChange={(e) => setF({ ...f, style: e.target.value })}>
                  {WATER_STYLE_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </label>
              <details open={f.style === "custom"}>
                <summary>Custom minerals (optional if style ≠ custom)</summary>
                <div className="grid-2col" style={{ gap: 8, marginTop: 8 }}>
                  {["Ca","Mg","HCO3","Na","K","SO4","Cl","TDS"].map((k) => (
                    <label key={k} className="col">
                      <span>{k} (mg/L)</span>
                      <input
                        value={(f.minerals?.[k] ?? "")}
                        onChange={(e) => setF({
                          ...f,
                          minerals: { ...(f.minerals || {}), [k]: Number(e.target.value) || undefined },
                        })}
                      />
                    </label>
                  ))}
                </div>
              </details>
            </>
          )}

          <div className="row" style={{ gap: 8, marginTop: 8 }}>
            <button className="btn" onClick={submit}>Add</button>
            <button className="btn secondary" onClick={() => setOpen(false)}>Cancel</button>
          </div>
        </>
      )}
    </div>
  );
}
