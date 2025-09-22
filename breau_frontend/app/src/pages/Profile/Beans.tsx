// src/pages/Profile/Beans.tsx
import React, { useEffect, useMemo, useRef, useState } from "react";
import useBeansLibrary from "@hooks/useBeansLibrary";

// Optional fallbacks if hook is minimal
import {
  addBean as addBeanAPI,
  updateBean as updateBeanAPI,
  removeBean as removeBeanAPI,
} from "@api/library";

type PanelMode = "none" | "manual" | "scan" | "edit";

type BeanRecord = {
  id?: string | number;
  name?: string;
  roaster?: string;
  origin?: string;
  process?: string;
  variety?: string;
  roastLevel?: string;   // camelCase
  roast_level?: string;  // snake_case
  notes?: string[] | string;
  flavor_notes?: string;
  image_url?: string;
  retired?: boolean;
};

type OCRParsed = Partial<
  Pick<BeanRecord, "origin" | "process" | "variety" | "roast_level" | "flavor_notes">
>;

export default function BeansPage() {
  // ---------- Library (hook) ----------
  const lib = useBeansLibrary();
  const anyLib = lib as unknown as {
    items?: any[];
    add?: (b: any) => Promise<any> | any;
    update?: (id: any, patch: any) => Promise<any> | any;
    remove?: (id: any) => Promise<any> | any;
    refresh?: () => Promise<any> | any;
    reload?: () => Promise<any> | any;
    refetch?: () => Promise<any> | any;
  };

  const itemsFromHook: BeanRecord[] = (anyLib?.items ?? []) as any[];
  const refresh: undefined | (() => any | Promise<any>) =
    (typeof anyLib?.refresh === "function" && anyLib.refresh) ||
    (typeof anyLib?.reload === "function" && anyLib.reload) ||
    (typeof anyLib?.refetch === "function" && anyLib.refetch) ||
    undefined;

  const addHook: undefined | ((b: any) => Promise<any>) = anyLib?.add;
  const updateHook: undefined | ((id: any, patch: any) => Promise<any>) = anyLib?.update;
  const removeHook: undefined | ((id: any) => Promise<any>) = anyLib?.remove;

  // ---------- Local list (responsive/offline) ----------
  const [beans, setBeans] = useState<BeanRecord[]>(itemsFromHook);
  useEffect(() => setBeans(itemsFromHook), [itemsFromHook]);

  const counts = useMemo(() => {
    const active = beans.filter((b) => !b.retired).length;
    const retired = Math.max(beans.length - active, 0);
    return { active, retired };
  }, [beans]);

  // selection for multi-delete
  const [selectMode, setSelectMode] = useState(false);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const beansKey = useMemo(() => beans.map((b) => String(b.id)).join("|"), [beans]);
  useEffect(() => setSelected({}), [beansKey]);

  // bottom panel
  const [mode, setMode] = useState<PanelMode>("none");
  const [editingId, setEditingId] = useState<string | null>(null);

  // manual/parsed form
  const [form, setForm] = useState<BeanRecord>({
    name: "",
    roaster: "",
    origin: "",
    process: "",
    variety: "",
    roastLevel: "",
    flavor_notes: "",
  });
  const setField = <K extends keyof BeanRecord>(k: K, v: BeanRecord[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  // OCR state
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);   // inline thumbnail
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null); // full-screen viewer
  const lastPreviewRef = useRef<string | null>(null);
  const [rawText, setRawText] = useState("");
  const [busy, setBusy] = useState(false);

  // small helpers
  const roastDisplay = (b: BeanRecord) => b.roastLevel ?? b.roast_level ?? "";
  const notesDisplay = (b: BeanRecord) =>
    Array.isArray(b.notes) ? b.notes.join(", ") : (b.notes || b.flavor_notes || "");

  function openManual() {
    setEditingId(null);
    setForm({ name: "", roaster: "", roastLevel: "", origin: "", process: "", variety: "", flavor_notes: "" });
    setMode("manual");
  }
  function openScan() {
    setEditingId(null);
    setRawText("");
    setFile(null);
    if (lastPreviewRef.current) URL.revokeObjectURL(lastPreviewRef.current);
    lastPreviewRef.current = null;
    setPreviewUrl(null);
    setForm({ name: "", roaster: "", roastLevel: "", origin: "", process: "", variety: "", flavor_notes: "" });
    setMode("scan");
  }
  function openEdit(b: BeanRecord) {
    setEditingId(String(b.id));
    setMode("edit");
    setForm({
      name: b.name || "",
      roaster: b.roaster || "",
      roastLevel: roastDisplay(b),
      origin: b.origin || "",
      process: b.process || "",
      variety: b.variety || "",
      flavor_notes: notesDisplay(b),
    });
    setRawText("");
    setFile(null);
    if (lastPreviewRef.current) URL.revokeObjectURL(lastPreviewRef.current);
    lastPreviewRef.current = null;
    setPreviewUrl(null);
  }

  // persistence (prefer hook; fallback API; else local optimistic)
  async function addBean(payload: any) {
    try {
      if (addHook) await addHook(payload);
      else await addBeanAPI(payload);
      await refresh?.();
    } catch {
      setBeans((prev) => [{ id: `local-${Date.now()}`, ...payload }, ...prev]);
    }
  }
  async function updateBean(id: string | number, patch: any) {
    try {
      if (updateHook) await updateHook(id, patch);
      else await updateBeanAPI({ id, ...patch } as any);
      await refresh?.();
    } catch {
      setBeans((prev) => prev.map((b) => (String(b.id) === String(id) ? { ...b, ...patch } : b)));
    }
  }
  async function removeBean(id: string | number) {
    try {
      if (removeHook) await removeHook(id);
      else await removeBeanAPI(String(id));
      await refresh?.();
    } catch {
      setBeans((prev) => prev.filter((b) => String(b.id) !== String(id)));
    }
  }

  // OCR helpers
  async function fetchFirstOk(urls: string[], options?: RequestInit) {
    for (const u of urls) {
      try {
        const r = await fetch(u, options);
        if (r.ok) return r;
      } catch {}
    }
    throw new Error("No OCR endpoint responded.");
  }
  function normalizeExtractResult(data: any): { raw: string; fields: OCRParsed } {
    if (typeof data?.raw_text === "string") return { raw: data.raw_text, fields: (data?.parsed || {}) as OCRParsed };
    if (typeof data?.text === "string") return { raw: data.text, fields: (data?.fields || {}) as OCRParsed };
    return { raw: "", fields: {} };
  }
  const toStringList = (v?: string | string[]) => (!v ? "" : Array.isArray(v) ? v.join(", ") : v);

  // OCR actions
  async function extractText() {
    if (!file) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetchFirstOk(["/api/ocr/extract", "/ocr/extract"], { method: "POST", body: fd });
      const data = await res.json();
      const { raw, fields } = normalizeExtractResult(data);
      setRawText(raw);
      setForm((f) => ({
        ...f,
        origin: fields.origin ?? f.origin,
        process: fields.process ?? f.process,
        variety: (fields.variety && toStringList(fields.variety)) || f.variety,
        flavor_notes: (fields.flavor_notes && toStringList(fields.flavor_notes)) || f.flavor_notes,
      }));
    } catch (e) {
      alert("OCR failed. Try another photo.");
    } finally {
      setBusy(false);
    }
  }
  async function reparseRaw() {
    if (!rawText.trim()) return;
    setBusy(true);
    try {
      const res = await fetchFirstOk(["/api/ocr/parse", "/ocr/parse"], {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw_text: rawText }),
      });
      const data = await res.json();
      const parsed = (data?.parsed || {}) as OCRParsed;
      setForm((f) => ({
        ...f,
        origin: parsed.origin ?? f.origin,
        process: parsed.process ?? f.process,
        variety: (parsed.variety && toStringList(parsed.variety)) || f.variety,
        flavor_notes: (parsed.flavor_notes && toStringList(parsed.flavor_notes)) || f.flavor_notes,
      }));
    } catch (e) {
      alert("Parse failed.");
    } finally {
      setBusy(false);
    }
  }

  async function saveBean() {
    const payload = {
      name: (form.name || "").trim(),
      roaster: (form.roaster || "").trim(),
      origin: form.origin?.trim() || undefined,
      process: form.process?.trim() || undefined,
      variety: form.variety?.trim() || undefined,
      roastLevel: form.roastLevel?.trim() || undefined, // store camelCase going forward
      notes: (form.flavor_notes || "")
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
    };
    if (!payload.name) return alert("Please enter the Bean name.");

    if (mode === "edit" && editingId) {
      await updateBean(editingId, payload);
    } else {
      await addBean(payload);
    }

    // reset + close
    setMode("none");
    setEditingId(null);
    setForm({ name: "", roaster: "", roastLevel: "", origin: "", process: "", variety: "", flavor_notes: "" });
    setRawText("");
    // don't revoke while the lightbox is showing the same blob
    if (!lightboxUrl || lightboxUrl !== lastPreviewRef.current) {
      if (lastPreviewRef.current) URL.revokeObjectURL(lastPreviewRef.current);
    }
    lastPreviewRef.current = null;
    setFile(null);
    setPreviewUrl(null);
  }

  // ---------- UI ----------
  return (
    <main className="page">
      {/* Header & actions */}
      <div className="card col">
        <h2>Beans</h2>

        <div className="row" style={{ justifyContent: "space-between" }}>
          <div className="row">
            <button className="btn" onClick={openManual}>Add manually</button>
            <button className="btn secondary" onClick={openScan}>Scan label</button>
            <button className="btn secondary" onClick={() => refresh?.()}>Refresh</button>
          </div>

          <div className="row">
            {!selectMode && beans.length > 0 && (
              <button className="btn secondary" onClick={() => setSelectMode(true)}>Select</button>
            )}
            {selectMode && (
              <>
                <button
                  className="btn"
                  onClick={async () => {
                    const ids = Object.keys(selected).filter((id) => selected[id]);
                    if (!ids.length) return setSelectMode(false);
                    if (!confirm(`Delete ${ids.length} bean${ids.length > 1 ? "s" : ""}?`)) return;
                    for (const id of ids) await removeBean(id);
                    setSelectMode(false);
                  }}
                >
                  Delete
                </button>
                <button className="btn secondary" onClick={() => { setSelected({}); setSelectMode(false); }}>
                  Cancel
                </button>
              </>
            )}
          </div>
        </div>

        <div className="row" style={{ gap: 8, opacity: 0.8, fontSize: 12 }}>
          <span>{counts.active} active</span>
          <span>•</span>
          <span>{counts.retired} retired</span>
        </div>
      </div>

      {/* Inventory list */}
      <div className="card col">
        {beans.length === 0 && <span style={{ opacity: 0.8 }}>No beans saved yet.</span>}

        <div className="col" style={{ gap: 10 }}>
          {beans.map((b) => {
            const idStr = String(b.id ?? `${b.name}-${b.roaster}-${Math.random()}`);
            const roast = roastDisplay(b);
            const sub = [b.roaster, b.origin, roast].filter(Boolean).join(" • ");
            return (
              <div
                key={idStr}
                className="row"
                style={{ justifyContent: "space-between", padding: "6px 0", alignItems: "center" }}
              >
                <div className="row" style={{ alignItems: "flex-start" }}>
                  {b.image_url && (
                    <button
                      className="thumb"
                      onClick={() => setLightboxUrl(b.image_url!)}
                      style={{
                        width: 56, height: 56, borderRadius: 10, overflow: "hidden",
                        border: "1px solid #1f2126", display: "grid", placeItems: "center", cursor: "zoom-in"
                      }}
                      title="View label"
                    >
                      <img src={b.image_url!} alt={b.name || "label"} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                    </button>
                  )}
                  <div className="col" style={{ gap: 4 }}>
                    <div><strong>{b.name || "Unnamed bean"}</strong></div>
                    {!!sub && <div style={{ fontSize: 12, opacity: 0.75 }}>{sub}</div>}
                    {!!notesDisplay(b) && (
                      <div style={{ fontSize: 12, opacity: 0.75 }}>{notesDisplay(b)}</div>
                    )}
                  </div>
                </div>

                <div className="row">
                  {selectMode ? (
                    <input
                      type="checkbox"
                      checked={!!selected[idStr]}
                      onChange={(e) => setSelected((s) => ({ ...s, [idStr]: e.target.checked }))}
                    />
                  ) : (
                    <>
                      <button className="btn secondary" onClick={() => openEdit(b)}>Edit</button>
                      <button className="btn secondary" onClick={() => removeBean(idStr)}>Delete</button>
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Bottom panel (Scan / Manual / Edit) */}
      {mode !== "none" && (
        <div className="card col">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h3>
              {mode === "scan" ? "Scan label" : mode === "manual" ? "Add manually" : "Edit bean"}
            </h3>
            <button className="btn secondary" onClick={() => setMode("none")}>Close</button>
          </div>

          {/* Scan block */}
          {mode === "scan" && (
            <div className="col" style={{ gap: 12 }}>
              <div className="row" style={{ gap: 12, alignItems: "center" }}>
                <input
                  type="file"
                  accept="image/*"
                  onChange={(e) => {
                    const f = e.target.files?.[0] || null;
                    setFile(f);
                    if (f) {
                      const url = URL.createObjectURL(f);
                      if (lastPreviewRef.current) URL.revokeObjectURL(lastPreviewRef.current);
                      lastPreviewRef.current = url;
                      setPreviewUrl(url);
                    } else if (lastPreviewRef.current) {
                      URL.revokeObjectURL(lastPreviewRef.current);
                      lastPreviewRef.current = null;
                      setPreviewUrl(null);
                    }
                  }}
                />
                {/* Small thumbnail preview; click to open lightbox */}
                {previewUrl && (
                  <button
                    className="thumb"
                    onClick={() => setLightboxUrl(previewUrl)}
                    style={{
                      width: 140, height: 96, borderRadius: 12, overflow: "hidden",
                      border: "1px solid #1f2126", display: "grid", placeItems: "center",
                      cursor: "zoom-in", background: "#0b0c10"
                    }}
                    title="Open preview"
                  >
                    <img
                      src={previewUrl}
                      alt="preview"
                      style={{ width: "100%", height: "100%", objectFit: "cover" }}
                    />
                  </button>
                )}
              </div>

              <div className="row" style={{ gap: 8 }}>
                <button className="btn" onClick={extractText} disabled={busy || !file}>
                  {busy ? "Working…" : "Extract text"}
                </button>
                <button className="btn secondary" onClick={reparseRaw} disabled={busy || !rawText}>
                  Apply again
                </button>
                <button
                  className="btn secondary"
                  onClick={() => {
                    setRawText("");
                    setFile(null);
                    if (!lightboxUrl || lightboxUrl !== lastPreviewRef.current) {
                      if (lastPreviewRef.current) URL.revokeObjectURL(lastPreviewRef.current);
                    }
                    lastPreviewRef.current = null;
                    setPreviewUrl(null);
                  }}
                >
                  Clear
                </button>
              </div>

              <label className="col">
                <span className="form-label">Raw OCR text</span>
                <textarea
                  className="ocr-text"
                  placeholder="Extracted text will appear here…"
                  value={rawText}
                  onChange={(e) => setRawText(e.target.value)}
                />
              </label>
            </div>
          )}

          {/* Manual + Parsed fields — neatly lined up */}
          <div className="col" style={{ gap: 8 }}>
            {/* Row 1: Name + Roaster */}
            <div className="row" style={{ gap: 8 }}>
              <label className="col" style={{ flex: 1 }}>
                <span className="form-label">Name (manual) *</span>
                <input
                  placeholder="e.g., Guatemala La Florida"
                  value={form.name || ""}
                  onChange={(e) => setField("name", e.target.value)}
                />
              </label>
              <label className="col" style={{ flex: 1 }}>
                <span className="form-label">Roaster (manual)</span>
                <input
                  placeholder="e.g., NYLON"
                  value={form.roaster || ""}
                  onChange={(e) => setField("roaster", e.target.value)}
                />
              </label>
            </div>

            {/* Row 2: Origin + Process */}
            <div className="row" style={{ gap: 8 }}>
              <label className="col" style={{ flex: 1 }}>
                <span className="form-label">Origin</span>
                <input
                  placeholder="e.g., Huila, Colombia"
                  value={form.origin || ""}
                  onChange={(e) => setField("origin", e.target.value)}
                />
              </label>
              <label className="col" style={{ flex: 1 }}>
                <span className="form-label">Process</span>
                <input
                  placeholder="e.g., Washed / Natural / Anaerobic"
                  value={form.process || ""}
                  onChange={(e) => setField("process", e.target.value)}
                />
              </label>
            </div>

            {/* Row 3: Variety + Roast level */}
            <div className="row" style={{ gap: 8 }}>
              <label className="col" style={{ flex: 1 }}>
                <span className="form-label">Variety</span>
                <input
                  placeholder="e.g., Caturra, SL28, Gesha"
                  value={form.variety || ""}
                  onChange={(e) => setField("variety", e.target.value)}
                />
              </label>
              <label className="col" style={{ flex: 1 }}>
                <span className="form-label">Roast level (manual)</span>
                <input
                  placeholder="e.g., Light / Medium / Dark"
                  value={form.roastLevel || ""}
                  onChange={(e) => setField("roastLevel", e.target.value)}
                />
              </label>
            </div>

            {/* Row 4: Notes full width */}
            <label className="col">
              <span className="form-label">Notes (comma-separated)</span>
              <input
                placeholder="peach, jasmine, bergamot"
                value={String(form.flavor_notes || "")}
                onChange={(e) => setField("flavor_notes", e.target.value)}
              />
            </label>

            <div className="row" style={{ gap: 8 }}>
              <button className="btn" onClick={saveBean}>
                {mode === "edit" ? "Save changes" : "Save bean"}
              </button>
              <button className="btn secondary" onClick={() => setMode("none")}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Lightbox viewer (like ChatGPT) */}
      {lightboxUrl && (
        <div
          className="net-overlay"
          onClick={() => setLightboxUrl(null)}
          style={{ cursor: "zoom-out" }}
        >
          <div className="net-body" style={{ placeItems: "center" }}>
            <img
              src={lightboxUrl}
              alt="preview"
              style={{ maxHeight: "82vh", maxWidth: "92vw", borderRadius: 12, border: "1px solid #1f2126" }}
            />
          </div>
        </div>
      )}
    </main>
  );
}
