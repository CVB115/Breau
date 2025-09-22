// src/api/endpoints.ts

/**
 * Central place for building backend endpoint URLs.
 * Uses the Vite dev proxy: every path is prefixed with /api so it forwards to your backend.
 */

function api(path: string) {
  return `/api${path}`;
}

export const API = {
  // ---------------------------
  // Sessions (v2, preferred)
  // ---------------------------

  /** v2: Start a new brew session (manual or suggested). */
  sessionsStart(): string {
    return api(`/sessions/start`);
  },

  /** v2: Append a step to an active session. */
  sessionsStep(): string {
    return api(`/sessions/step`);
  },

  /** v2: Finish a session (send summary/recipe_snapshot/feedback). */
  sessionsFinish(): string {
    return api(`/sessions/finish`);
  },

  // ---------------------------
  // Brew (legacy v1, kept for fallback/back-compat)
  // ---------------------------

  /** v1: Start a new brew session. Prefer sessionsStart() going forward. */
  start(): string {
    return api(`/brew/start`);
  },

  /** v1: Log a step (some callers may append /:id themselves). Prefer sessionsStep(). */
  step(): string {
    return api(`/brew/step`);
  },

  /** v1: Finish a session (some callers may append /:id). Prefer sessionsFinish(). */
  finish(): string {
    return api(`/brew/finish`);
  },

  /** v1: Fetch a specific session document (legacy shape). */
  sessionDetail(userId: string, sessionId: string): string {
    return api(
      `/brew/session/${encodeURIComponent(userId)}/${encodeURIComponent(sessionId)}`
    );
  },

  /** (Alias kept for callers) */
  brewStart(): string {
    return this.start();
  },

  /** (Alias kept for callers) */
  brewFinish(): string {
    return this.finish();
  },

  /** Lightweight event/analytics log for voice, etc. */
  brewLog(): string {
    return api(`/brew/log`);
  },

  /** Fetch a session’s plan (steps) for guided brew. */
  brewSessionPlan(sessionId: string): string {
    return api(`/brew/${encodeURIComponent(sessionId)}/plan`);
  },

  // ---------------------------
  // Brew / Suggest
  // ---------------------------

  /** Request a recipe suggestion. POST a SuggestPayload. */
  brewSuggest(): string {
    return api(`/brew/suggest`);
  },

  /** Back-compat alias for existing calls. Prefer brewSuggest() going forward. */
  suggest(): string {
    return this.brewSuggest();
  },

  

  // ---------------------------
  // History
  // ---------------------------

  /** Recent sessions for a user. */
  history(userId: string, limit = 5): string {
    return api(`/history/${encodeURIComponent(userId)}?limit=${limit}`);
  },

  /** Last brew session summary for a user. */
  lastSession(userId: string): string {
    return `/api/history/${encodeURIComponent(userId)}/last`;
  },

  // ---------------------------
  // Profile: Beans
  // ---------------------------

  profile(userId: string): string {
    return `/api/profile/${encodeURIComponent(userId)}`;
  },

  /** User's bean library (GET list, POST to add). */
  profileBeans(userId: string): string {
    return api(`/profile/${encodeURIComponent(userId)}/beans`);
  },

  // ---------------------------
  // Profile: Gear (active combo + combos list)
  // ---------------------------

  /** Get active gear combo for a user. */
  profileActiveGear(userId: string): string {
    return api(`/profile/${encodeURIComponent(userId)}/gear/active`);
  },

  /** Set active gear combo (POST with { gear_combo_id } or { gear: {...} }). */
  setActiveGear(userId: string): string {
    return api(`/profile/${encodeURIComponent(userId)}/gear/active`);
  },

  /** List saved gear combos for a user. */
  profileGearCombos(userId: string): string {
    return api(`/profile/${encodeURIComponent(userId)}/gear/combos`);
  },

  // ---------------------------
  // OCR
  // ---------------------------

  /** OCR extract endpoint (multipart/form-data with the image file). */
  ocrWarmup(): string {
    return "/api/ocr/warmup";
  },
  ocrExtract(): string {
    return "/api/ocr/extract";
  },
};

export type SuggestPayload = {
  user_id?: string;
  goals_text?: string;
  /** Send either bean_id or bean_name (both is fine; server can resolve). */
  bean_id?: string;
  bean_name?: string;
  gear?: {
    brewer?: unknown;
    grinder?: unknown;
    filter?: unknown;
    water?: unknown;
  };
};

export default API;
