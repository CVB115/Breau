import { z } from "zod";

// Primitive helpers
const ID = z.string().min(1);

export const ZGearCombo = z.object({
  brewer: z.object({ name: z.string() }).partial().optional(),
  grinder: z.object({ model: z.string(), burr_type: z.string().optional() }).partial().optional(),
  filter: z.object({ permeability: z.string().optional(), material: z.string().optional() }).partial().optional(),
  water: z.object({ profile_preset: z.string().optional() }).partial().optional(),
}).partial();

export const ZBeanEntry = z.object({
  id: ID,
  name: z.string(),
  roaster: z.string().optional(),
  process: z.string().optional(),
  origin: z.string().optional(),
  variety: z.string().optional(),
  notes: z.string().optional(),
  inventory_grams: z.number().optional(),
  active: z.boolean().optional(),
});

export const ZUserProfile = z.object({
  user_id: ID,
  active_bean_id: ID.nullish(),
  active_gear: ZGearCombo.optional(),
  settings: z.object({
    units: z.enum(["metric", "imperial"]).optional(),
    smart_suggestions: z.boolean().optional(),
    learning_overlay: z.boolean().optional(),
  }).partial().optional(),
  beans: z.array(ZBeanEntry).optional(),
}).partial();

export const ZNoteScore = z.object({
  note: z.string(),
  score: z.number(),
});

export const ZBrewSessionSummary = z.object({
  session_id: ID,
  date: z.string(),          // ISO
  recipe: z.unknown().optional(),
  rating: z.number().optional(),
  predicted_notes: z.array(ZNoteScore).optional(),
  perceived_notes: z.array(ZNoteScore).optional(),
});

export const ZHomeSummary = z.object({
  profile: ZUserProfile.nullish(),
  lastSession: ZBrewSessionSummary.nullish(),
  recent: z.array(ZBrewSessionSummary).optional(),
}).partial();

// Brew suggest
export const ZSuggestInput = z.object({
  user_id: z.string().default("local"),
  bean_id: z.string().optional(),
  gear: ZGearCombo.optional(),
  goals_text: z.string().optional(),
  goals: z.array(z.string()).optional(),
});

export const ZRecipe = z.object({
  method: z.string().optional(),
  ratio: z.object({ water_g: z.number().optional(), coffee_g: z.number().optional() }).partial().optional(),
  steps: z.array(z.object({
    id: z.string(),
    label: z.string(),
    water_to: z.number().optional(),
    note: z.string().optional(),
  })).optional(),
}).partial();

export const ZSuggestResponse = z.object({
  recipe: ZRecipe,
  predicted_notes: z.array(ZNoteScore).optional(),
  trace: z.any().optional(),
});
