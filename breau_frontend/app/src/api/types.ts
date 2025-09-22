export type ID = string;

export interface GearCombo {
  brewer?: { name: string };
  grinder?: { model: string; burr_type?: string };
  filter?: { permeability?: string; material?: string };
  water?: { profile_preset?: string };
}

export interface BeanEntry {
  id: ID;
  name: string;
  roaster?: string;
  process?: string;
  /** Newly added to match Zod + UI */
  origin?: string;
  /** Newly added to match Zod + UI */
  variety?: string;
  /** Optional tasting notes */
  notes?: string;
  inventory_grams?: number;
  active?: boolean;
}

export interface UserProfile {
  user_id: ID;
  active_bean_id?: ID | null;
  active_gear?: GearCombo;
  settings?: {
    units?: "metric" | "imperial";
    smart_suggestions?: boolean;
    learning_overlay?: boolean;
  };
  beans?: BeanEntry[];
}

export interface NoteScore {
  note: string;
  score: number;
}

export interface BrewSessionSummary {
  session_id: ID;
  date: string;
  recipe?: any;
  rating?: number;
  predicted_notes?: NoteScore[];
  perceived_notes?: NoteScore[];
}

export interface HomeSummary {
  profile?: UserProfile | null;
  lastSession?: BrewSessionSummary | null;
  recent?: BrewSessionSummary[];
}
