// src/data/library.ts
// Curated starter seeds for Library: Brewers, Filters, Grinders, Water.
// Keep this small and sensible; localStorage will persist user edits/additions.

export type SeedBrewer = {
  id: string;
  name: string;
  geometry: "conical" | "flatbed";
  method: "pour_over" | "immersion";
  flow_factor?: number; // optional; API can infer if missing
};

export type SeedFilter = {
  id: string;
  name: string;
  material: "paper" | "abaca" | "cloth" | "metal";
  thickness: "thin" | "std" | "thick";
  permeability_factor?: number; // optional; API can infer if missing
};

export type SeedGrinder = {
  id: string;
  brand: string;
  model: string;
  burr_type: "conical" | "flat";
  scale?: { type: "clicks" | "numbers" | "dial" | "ring"; min: number; max: number; step: number };
  a?: number; // optional microns intercept
  b?: number; // optional microns/step slope
  aliases?: string[];
};

export type SeedWater = {
  id: string;
  name: string;
  style: "sca" | "balanced" | "soft" | "tww_classic" | "local";
  // Basic mineral targets in mg/L (ppm). Keep minimal for the app; backend can transform as needed.
  minerals: {
    Ca?: number;   // calcium
    Mg?: number;   // magnesium
    HCO3?: number; // alkalinity as bicarbonate
    Na?: number;
    K?: number;
    SO4?: number;
    Cl?: number;
    TDS?: number;  // optional convenience value
  };
  notes?: string;
};

// ——— Top-5 Brewers ———
export const seedBrewers: SeedBrewer[] = [
  { id: "hario_v60_02",    name: "Hario V60-02",      geometry: "conical", method: "pour_over", flow_factor: 1.00 },
  { id: "kalita_wave_185", name: "Kalita Wave 185",   geometry: "flatbed", method: "pour_over", flow_factor: 0.92 },
  { id: "chemex_6cup",     name: "Chemex 6-cup",      geometry: "conical", method: "pour_over", flow_factor: 0.88 },
  { id: "origami_m",       name: "Origami M",         geometry: "conical", method: "pour_over", flow_factor: 1.02 },
  { id: "orea_v3",         name: "Orea V3",           geometry: "flatbed", method: "pour_over", flow_factor: 1.05 },
];

// ——— Top-5 Filters ———
export const seedFilters: SeedFilter[] = [
  { id: "v60_02_white",       name: "Hario V60 02 (white)",   material: "paper",  thickness: "std",  permeability_factor: 1.00 },
  { id: "wave_185",           name: "Kalita Wave 185",        material: "paper",  thickness: "std",  permeability_factor: 0.95 },
  { id: "cafec_abaca_02",     name: "CAFEC Abaca (V60 02)",   material: "abaca",  thickness: "std",  permeability_factor: 1.06 },
  { id: "sibarist_fast_cone", name: "Sibarist FAST Cone (02)",material: "paper",  thickness: "thin", permeability_factor: 1.25 },
  { id: "melitta_4",          name: "Melitta #4",             material: "paper",  thickness: "thick",permeability_factor: 0.96 },
];

// ——— Top-5 Grinders ———
export const seedGrinders: SeedGrinder[] = [
  {
    id: "comandante_c40_mk4", brand: "Comandante", model: "C40 MK4", burr_type: "conical",
    scale: { type: "clicks", min: 0, max: 45, step: 1 }, a: 200.0, b: 18.0, aliases: ["C40", "C40 MK4", "Comandante"]
  },
  {
    id: "1zpresso_k_ultra", brand: "1Zpresso", model: "K-Ultra", burr_type: "conical",
    scale: { type: "clicks", min: 0, max: 200, step: 1 }, a: 180.0, b: 20.0, aliases: ["K Ultra", "K-Ultra", "1Z K-Ultra"]
  },
  {
    id: "fellow_ode_gen2", brand: "Fellow", model: "Ode Gen 2", burr_type: "flat",
    scale: { type: "numbers", min: 1, max: 31, step: 1 }, a: 160.0, b: 10.0, aliases: ["Ode v2", "Ode Gen2"]
  },
  {
    id: "niche_zero", brand: "Niche", model: "Zero", burr_type: "conical",
    scale: { type: "dial", min: 0, max: 100, step: 1 }, a: 180.0, b: 11.0, aliases: ["Niche", "Zero"]
  },
  {
    id: "df64_gen2", brand: "DF64", model: "Gen 2", burr_type: "flat",
    scale: { type: "numbers", min: 0, max: 90, step: 0.5 }, a: 150.0, b: 9.0, aliases: ["DF64", "G-iota"]
  },
];

// ——— Top-5 Waters ———
// These are reasonable presets for demo. Users can add custom water with minimal fields later.
export const seedWaters: SeedWater[] = [
  {
    id: "water_sca",
    name: "SCA-ish Brew Water",
    style: "sca",
    minerals: { Ca: 17, Mg: 5, HCO3: 40, Na: 5, K: 2, SO4: 20, Cl: 10, TDS: 120 },
    notes: "Balanced extraction, safe alkalinity for acidity clarity.",
  },
  {
    id: "water_balanced",
    name: "Balanced (Light/Med Roasts)",
    style: "balanced",
    minerals: { Ca: 25, Mg: 10, HCO3: 45, Na: 5, SO4: 25, Cl: 15, TDS: 140 },
    notes: "A touch more hardness for body while keeping clarity.",
  },
  {
    id: "water_soft_volvic_like",
    name: "Soft (Volvic-like)",
    style: "soft",
    minerals: { Ca: 11, Mg: 8, HCO3: 65, Na: 12, K: 6, SO4: 8, Cl: 15, TDS: 110 },
    notes: "Soft, round mouthfeel; gentle acidity.",
  },
  {
    id: "water_tww_classic",
    name: "Third Wave Water Classic",
    style: "tww_classic",
    minerals: { Ca: 35, Mg: 10, HCO3: 40, Na: 8, SO4: 55, Cl: 15, TDS: 150 },
    notes: "Classic profile for filter coffee; bright and sweet.",
  },
  {
    id: "water_local",
    name: "Local (Customizable)",
    style: "local",
    minerals: { Ca: 20, Mg: 5, HCO3: 50, Na: 10, SO4: 20, Cl: 20, TDS: 140 },
    notes: "Starting point for local tap + filter systems.",
  },
];

export default {
  brewers: seedBrewers,
  filters: seedFilters,
  grinders: seedGrinders,
  waters: seedWaters,
};
