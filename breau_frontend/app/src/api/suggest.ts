// src/api/suggest.ts
import { api } from "@api/client";
import { API } from "@api/endpoints";

/** What the suggest endpoint accepts. */
export type SuggestRequest = {
  user_id?: string;
  goals_text: string;

  // Prefer id, but we also pass a snapshot of the bean (your pages do this)
  bean_id?: string;
  bean?: {
    id?: string;
    name?: string;
    roaster?: string;
    origin?: string;
    process?: string;
    variety?: string;
  };

  // Optional: include active gear if you want the model to use it
  gear?: {
    brewer?: unknown;
    grinder?: unknown;
    filter?: unknown;
    water?: unknown;
    [k: string]: unknown;
  };

  // Allow extra keys without breaking types
  [k: string]: unknown;
};

/** Minimal shape your UI reads in Preview/Guide (extend when backend grows). */
export type SuggestResponse = {
  recipe: {
    steps?: Array<{
      id: string;
      label: string;
      water_to?: number;
      note?: string;
      duration_s?: number;
    }>;
    // other calculated variables are fine here too
    [k: string]: unknown;
  };
  predicted_notes?: Array<{ note: string; score: number }>;
  session_id?: string; // if backend chooses to create one early
  [k: string]: unknown;
};

/** Goals page calls this, then navigates to /brew/suggest/preview with state. */
export async function suggest(payload: SuggestRequest): Promise<SuggestResponse> {
  return await api.post<SuggestResponse>(API.brewSuggest(), payload);
}

/** Preview page fetches (or re-fetches) the suggestion using the same payload. */
export async function fetchSuggestion(payload: SuggestRequest): Promise<SuggestResponse> {
  return await api.post<SuggestResponse>(API.brewSuggest(), payload);
}
