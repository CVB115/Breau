// src/utils/parseBrewCommand.ts
// Natural language → structured events for Manual Log
// Handles: “start bloom”, “end first pour”, “at 0:40”, “pour 2 to 140g”,
// “add pour”, “remaining water in the third pour”, notes, target total, etc.

export type ControlAction =
  | "start" | "pause" | "resume" | "next" | "done" | "finish";

export type BrewEvent =
  | { type: "control"; action: ControlAction }
  | { type: "add_pour" }
  | { type: "set_target_total"; grams: number }
  | { type: "note"; text: string }
  | { type: "start_step"; step: "bloom" | "pour"; index?: number; at_ms?: number }
  | { type: "end_step"; step: "bloom" | "pour"; index?: number; at_ms?: number }
  | { type: "set_step_to"; step: "bloom" | "pour"; index?: number; water_to_g: number }
  | { type: "set_step_remaining"; step: "pour"; index?: number } // “remaining water in pour 2”
  | { type: "set_style"; step: "bloom" | "pour"; index?: number; style: "center"|"spiral"|"pulse" }
  | { type: "set_temp"; step: "bloom" | "pour"; index?: number; temp_C: number };

const ORD: Record<string, number> = {
  "first": 1, "1st": 1, "one": 1,
  "second": 2, "2nd": 2, "two": 2,
  "third": 3, "3rd": 3, "three": 3,
  "fourth": 4, "4th": 4, "four": 4,
  "fifth": 5, "5th": 5, "five": 5,
};

function parseTimeToMs(s: string): number | undefined {
  // “0:40”, “1:05”, “40s”, “90 sec”, “1m 20s”, “80”
  const t = s.trim().toLowerCase();
  const mmss = t.match(/^(\d+):(\d{1,2})$/);
  if (mmss) return (parseInt(mmss[1],10)*60 + parseInt(mmss[2],10)) * 1000;

  const ms = t.match(/^(?:(\d+)m)\s*(\d+)?s?$/); // “1m 20s”, “2m”
  if (ms) {
    const m = parseInt(ms[1]||"0",10);
    const s2 = parseInt(ms[2]||"0",10);
    return (m*60+s2)*1000;
  }

  const ss = t.match(/^(\d+)\s*(?:s|sec|secs|seconds)?$/);
  if (ss) return parseInt(ss[1],10) * 1000;

  return undefined;
}

function gramsFrom(text: string): number | undefined {
  const m = text.match(/(\d+(?:\.\d+)?)\s*(?:g|grams?)?/i);
  if (!m) return;
  const v = parseFloat(m[1]);
  return isFinite(v) ? v : undefined;
}

function findPourIndex(text: string): number | undefined {
  // “pour 2”, “second pour”, “third”, “pour three”
  const t = text.toLowerCase();
  const ordWord = Object.keys(ORD).find(k => t.includes(k));
  if (ordWord) return ORD[ordWord];
  const m = t.match(/pour\s*(\d+)/);
  if (m) return parseInt(m[1],10);
  return undefined;
}

function styleFrom(text: string): "center"|"spiral"|"pulse"|undefined {
  const t = text.toLowerCase();
  if (t.includes("center") || t.includes("centre") || t.includes("straight")) return "center";
  if (t.includes("spiral")) return "spiral";
  if (t.includes("pulse")) return "pulse";
  return undefined;
}

function tempFrom(text: string): number | undefined {
  const m = text.match(/(\d{1,3})\s*(?:c|°c)?/i);
  if (!m) return;
  const n = parseInt(m[1],10);
  if (!isFinite(n)) return;
  return Math.max(0, Math.min(100, n));
}

function atTime(text: string): number | undefined {
  const m = text.match(/\bat\s+([0-9:sm ]+)\b/i);
  if (!m) return;

  const pick = m[1].trim();

  // existing: mm:ss, “40s”, “1m 20s”, etc.
  const base = parseTimeToMs(pick);
  if (base != null) return base;

  // NEW: bare mmss, e.g. “at 030”, “at 205”
  const bare = pick.match(/^(\d{3,4})$/);
  if (bare) {
    const raw = bare[1];
    const mm = parseInt(raw.slice(0, -2), 10);
    const ss = parseInt(raw.slice(-2), 10);
    if (mm >= 0 && ss >= 0 && ss < 60) return (mm * 60 + ss) * 1000;
  }
  return undefined;
}


export function parseBrewCommand(input: string): BrewEvent[] {
  const text = input.trim();
  if (!text) return [];

  const t = text.toLowerCase();

  // 1) Pure control
  if (/^(start|go|begin)\b/.test(t)) return [{ type: "control", action: "start" }];
  if (/^(pause|hold|stop)\b/.test(t)) return [{ type: "control", action: "pause" }];
  if (/^(resume|continue)\b/.test(t)) return [{ type: "control", action: "resume" }];
  if (/^(next)\b/.test(t)) return [{ type: "control", action: "next" }];
  if (/^(done|finish)\b/.test(t)) return [{ type: "control", action: "done" }];

  // 2) Target total
  if (/\b(target|total|overall)\b/.test(t) && /g\b/.test(t)) {
    const g = gramsFrom(t);
    if (g) return [{ type: "set_target_total", grams: g }];
  }

  // 3) Add pour
  if (/\b(add|another)\b.*\bpour\b/.test(t)) return [{ type: "add_pour" }];

  // 4) Start/End specific step (with optional “at …”)
  if (/\bstart\b.*\bbloom\b/.test(t) || /\bbloom\b.*\bstart\b/.test(t)) {
    return [{ type: "start_step", step: "bloom", at_ms: atTime(t) }];
  }
  if (/\bend\b.*\bbloom\b/.test(t) || /\bfinish\b.*\bbloom\b/.test(t)) {
    return [{ type: "end_step", step: "bloom", at_ms: atTime(t) }];
  }
  if (/\bstart\b.*\bpour\b/.test(t)) {
    return [{ type: "start_step", step: "pour", index: findPourIndex(t), at_ms: atTime(t) }];
  }
  if (/\b(end|finish)\b.*\bpour\b/.test(t)) {
    return [{ type: "end_step", step: "pour", index: findPourIndex(t), at_ms: atTime(t) }];
  }

  // 5) Set water-to (cumulative) for a step
  // Examples: “bloom to 45g”, “pour 2 to 140”, “second pour to 120 grams”
  if (/\b(to|till)\b.*\bg\b/.test(t) || /\bto\s+\d+\b/.test(t)) {
    const g = gramsFrom(t);
    if (g) {
      if (t.includes("bloom")) {
        return [{ type: "set_step_to", step: "bloom", water_to_g: g }];
      }
      if (t.includes("pour")) {
        return [{ type: "set_step_to", step: "pour", index: findPourIndex(t), water_to_g: g }];
      }
    }
  }

  // 6) Remaining water in Nth pour
  if (/\bremaining\b.*\bwater\b.*\bpour\b/.test(t)) {
    return [{ type: "set_step_remaining", step: "pour", index: findPourIndex(t) }];
  }

  // 7) Style and temperature
  const style = styleFrom(t);
  if (style) {
    if (t.includes("bloom")) return [{ type: "set_style", step: "bloom", style }];
    if (t.includes("pour")) return [{ type: "set_style", step: "pour", index: findPourIndex(t), style }];
  }
  if (/\btemp|temperature|kettle\b/.test(t)) {
    const c = tempFrom(t);
    if (isFinite(c as number)) {
      if (t.includes("bloom")) return [{ type: "set_temp", step: "bloom", temp_C: c! }];
      if (t.includes("pour")) return [{ type: "set_temp", step: "pour", index: findPourIndex(t), temp_C: c! }];
    }
  }

  // 8) Fallback: treat as note
  return [{ type: "note", text }];
}
