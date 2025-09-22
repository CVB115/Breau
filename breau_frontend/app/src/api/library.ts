// src/api/library.ts
// Persistent local library (Beans, Brewers, Filters, Grinders, Waters)
// Minimal add flows: Brewer(name+geometry), Filter(name+material+thickness), Grinder(free fields; a/b optional), Water(name + style OR minerals).

import seeds from "@data/library";

// —— Types (align with data seeds) ——
export type Bean = {
  id: string;
  name: string;
  roaster?: string;
  origin?: string;
  process?: string;
  variety?: string;
  notes?: string[];
  roastLevel?: string;
  dateRoasted?: string;
  stockLevel?: number;
};

export type Brewer = {
  id: string;
  name: string;
  geometry: "conical" | "flatbed";
  method: "pour_over" | "immersion";
  flow_factor?: number;
};

export type Filter = {
  id: string;
  name: string;
  material: "paper" | "abaca" | "cloth" | "metal";
  thickness: "thin" | "std" | "thick";
  permeability_factor?: number;
};

export type Grinder = {
  id: string;
  brand: string;
  model: string;
  burr_type: "conical" | "flat";
  scale?: { type: "clicks" | "numbers" | "dial" | "ring"; min: number; max: number; step: number };
  a?: number | null; // optional: intercept in microns
  b?: number | null; // optional: slope microns/step
  aliases?: string[];
};

export type Water = {
  id: string;
  name: string;
  style: "sca" | "balanced" | "soft" | "tww_classic" | "local" | "custom";
  minerals: {
    Ca?: number; Mg?: number; HCO3?: number; Na?: number; K?: number; SO4?: number; Cl?: number; TDS?: number;
  };
  notes?: string;
};

// —— UI Option helpers (export for dropdown hints) ——
export const GEOMETRY_OPTIONS: Brewer["geometry"][] = ["conical", "flatbed"];
export const METHOD_OPTIONS: Brewer["method"][] = ["pour_over", "immersion"];
export const FILTER_MATERIAL_OPTIONS: Filter["material"][] = ["paper", "abaca", "cloth", "metal"];
export const FILTER_THICKNESS_OPTIONS: Filter["thickness"][] = ["thin", "std", "thick"];
export const WATER_STYLE_OPTIONS: Water["style"][] = ["sca", "balanced", "soft", "tww_classic", "local", "custom"];

// —— Storage keys & versioning ——
const STORAGE_VERSION = 3; // bump when seed shape/logic changes
const NS = "breau";
const KEYS = {
  version: `${NS}_lib_version`,
  beans: `${NS}_beans`,
  brewers: `${NS}_brewers`,
  filters: `${NS}_filters`,
  grinders: `${NS}_grinders`,
  waters: `${NS}_waters`,
};

// —— Safe JSON helpers ——
function read<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}
function write<T>(key: string, val: T) {
  localStorage.setItem(key, JSON.stringify(val));
}
function uid(prefix: string) {
  return `${prefix}_${Math.random().toString(36).slice(2, 8)}`;
}

// —— Defaults / Inference ——
const DEFAULT_FLOW_BY_GEOMETRY: Record<Brewer["geometry"] | "immersion", number> = {
  conical: 1.0,
  flatbed: 0.95,
  immersion: 0.8,
};
const DEFAULT_PERMEABILITY: Record<Filter["material"], number> = {
  paper: 1.0,
  abaca: 1.05,
  cloth: 1.15,
  metal: 1.30,
};
const THICKNESS_TWEAK: Record<Filter["thickness"], number> = {
  thin: +0.15,
  std: 0,
  thick: -0.05,
};

// Water quick presets (for "custom" fill convenience if user selects style)
const WATER_PRESETS: Record<Exclude<Water["style"], "custom">, Partial<Water["minerals"]>> = {
  sca:        { Ca: 17, Mg: 5, HCO3: 40, Na: 5, K: 2, SO4: 20, Cl: 10, TDS: 120 },
  balanced:   { Ca: 25, Mg: 10, HCO3: 45, Na: 5, SO4: 25, Cl: 15, TDS: 140 },
  soft:       { Ca: 11, Mg: 8, HCO3: 65, Na: 12, K: 6, SO4: 8, Cl: 15, TDS: 110 },
  tww_classic:{ Ca: 35, Mg: 10, HCO3: 40, Na: 8, SO4: 55, Cl: 15, TDS: 150 },
  local:      { Ca: 20, Mg: 5, HCO3: 50, Na: 10, SO4: 20, Cl: 20, TDS: 140 },
};

// —— One-time seed merge (idempotent) ——
function ensureSeeded() {
  const current = read<number>(KEYS.version);
  if (current === STORAGE_VERSION) return;

  const haveBrewers = read<Brewer[]>(KEYS.brewers);
  const haveFilters = read<Filter[]>(KEYS.filters);
  const haveGrinders = read<Grinder[]>(KEYS.grinders);
  const haveWaters = read<Water[]>(KEYS.waters);
  const haveBeans = read<Bean[]>(KEYS.beans);

  if (!haveBrewers || haveBrewers.length === 0) write(KEYS.brewers, seeds.brewers as Brewer[]);
  if (!haveFilters || haveFilters.length === 0) write(KEYS.filters, seeds.filters as Filter[]);
  if (!haveGrinders || haveGrinders.length === 0) write(KEYS.grinders, seeds.grinders as Grinder[]);
  if (!haveWaters || haveWaters.length === 0) write(KEYS.waters, (seeds as any).waters as Water[]);
  if (!haveBeans) write(KEYS.beans, [] as Bean[]);

  write(KEYS.version, STORAGE_VERSION);
}
ensureSeeded();

// ===================== Beans =====================
export function getBeans(): Bean[] {
  return read<Bean[]>(KEYS.beans) ?? [];
}
export function addBean(partial: Omit<Bean, "id">) {
  const beans = getBeans();
  const bean: Bean = { id: uid("bean"), ...partial };
  beans.push(bean);
  write(KEYS.beans, beans);
  return bean;
}
export function updateBean(updated: Bean) {
  write(KEYS.beans, getBeans().map((b) => (b.id === updated.id ? updated : b)));
}
export function removeBean(id: string) {
  write(KEYS.beans, getBeans().filter((b) => b.id !== id));
}

// ===================== Brewers =====================
export function getBrewers(): Brewer[] {
  return read<Brewer[]>(KEYS.brewers) ?? [];
}

// Minimal add: name + geometry (method optional; default pour_over). flow_factor inferred.
export function addBrewerMinimal(input: { name: string; geometry: Brewer["geometry"]; method?: Brewer["method"] }) {
  const method = input.method ?? "pour_over";
  const flow_base = method === "immersion" ? DEFAULT_FLOW_BY_GEOMETRY.immersion : DEFAULT_FLOW_BY_GEOMETRY[input.geometry];
  const brewer: Brewer = {
    id: uid("brewer"),
    name: input.name.trim(),
    geometry: input.geometry,
    method,
    flow_factor: flow_base,
  };
  const list = getBrewers();
  list.push(brewer);
  write(KEYS.brewers, list);
  return brewer;
}
export function updateBrewer(updated: Brewer) {
  write(KEYS.brewers, getBrewers().map((g) => (g.id === updated.id ? updated : g)));
}
export function removeBrewer(id: string) {
  write(KEYS.brewers, getBrewers().filter((g) => g.id !== id));
}

// ===================== Filters =====================
export function getFilters(): Filter[] {
  return read<Filter[]>(KEYS.filters) ?? [];
}

// Minimal add: name + material + thickness; permeability inferred from material + thickness.
export function addFilterMinimal(input: { name: string; material: Filter["material"]; thickness: Filter["thickness"] }) {
  const base = DEFAULT_PERMEABILITY[input.material] ?? 1.0;
  const tweak = THICKNESS_TWEAK[input.thickness] ?? 0;
  const filter: Filter = {
    id: uid("filter"),
    name: input.name.trim(),
    material: input.material,
    thickness: input.thickness,
    permeability_factor: +(base + tweak).toFixed(2),
  };
  const list = getFilters();
  list.push(filter);
  write(KEYS.filters, list);
  return filter;
}
export function updateFilter(updated: Filter) {
  write(KEYS.filters, getFilters().map((f) => (f.id === updated.id ? updated : f)));
}
export function removeFilter(id: string) {
  write(KEYS.filters, getFilters().filter((f) => f.id !== id));
}

// ===================== Grinders =====================
export function getGrinders(): Grinder[] {
  return read<Grinder[]>(KEYS.grinders) ?? [];
}

// Flexible add: user can fill anything; a/b are optional. If scale missing, set a generic dial.
export function addGrinderFlexible(input: Omit<Grinder, "id">) {
  const grinder: Grinder = {
    id: uid("grinder"),
    scale: input.scale ?? { type: "dial", min: 0, max: 100, step: 1 },
    a: input.a ?? null,
    b: input.b ?? null,
    ...input,
  };
  const list = getGrinders();
  list.push(grinder);
  write(KEYS.grinders, list);
  return grinder;
}
export function updateGrinder(updated: Grinder) {
  write(KEYS.grinders, getGrinders().map((g) => (g.id === updated.id ? updated : g)));
}
export function removeGrinder(id: string) {
  write(KEYS.grinders, getGrinders().filter((g) => g.id !== id));
}

// ===================== Waters =====================
export function getWaters(): Water[] {
  return read<Water[]>(KEYS.waters) ?? [];
}

// Minimal add: Either provide a style (we copy preset minerals), OR provide explicit minerals.
// Always requires a name.
export function addWaterMinimal(input: {
  name: string;
  style?: Water["style"];
  minerals?: Partial<Water["minerals"]>;
  notes?: string;
}) {
  const style = input.style ?? "custom";
  const fromPreset =
    style !== "custom"
      ? WATER_PRESETS[style as Exclude<Water["style"], "custom">] ?? {}
      : {};

  const minerals: Water["minerals"] = {
    ...fromPreset,
    ...(input.minerals ?? {}),
  };

  const water: Water = {
    id: uid("water"),
    name: input.name.trim(),
    style,
    minerals,
    notes: input.notes,
  };

  const list = getWaters();
  list.push(water);
  write(KEYS.waters, list);
  return water;
}
export function updateWater(updated: Water) {
  write(KEYS.waters, getWaters().map((w) => (w.id === updated.id ? updated : w)));
}
export function removeWater(id: string) {
  write(KEYS.waters, getWaters().filter((w) => w.id !== id));
}

// ===================== Convenience =====================
// Small helpers that some UIs use to clear or re-seed (not exposed in production UI).
export function __resetLibraryForDev() {
  write(KEYS.beans, []);
  write(KEYS.brewers, seeds.brewers as Brewer[]);
  write(KEYS.filters, seeds.filters as Filter[]);
  write(KEYS.grinders, seeds.grinders as Grinder[]);
  write(KEYS.waters, (seeds as any).waters as Water[]);
  write(KEYS.version, STORAGE_VERSION);
}
