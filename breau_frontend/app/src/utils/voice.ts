// src/utils/voice.ts
type LogFn = (type: string, payload?: any) => void;
const NOP: LogFn = () => {};

export function speak(text: string, onDone?: () => void, log: LogFn = NOP) {
  try {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return onDone?.();
    const u = new SpeechSynthesisUtterance(text);
    u.onstart = () => log("tts.start", { text });
    u.onend = () => { log("tts.end"); onDone?.(); };
    u.onerror = (e) => { log("tts.error", e); onDone?.(); };
    window.speechSynthesis.speak(u);
  } catch (e) {
    log("tts.fail", e);
    onDone?.();
  }
}

// --- Push‑to‑talk (browser Web Speech) ---
let rec: any;

export function startPTT(onFinal: (text: string) => void, onInterim: (text: string) => void = NOP, log: LogFn = NOP) {
  try {
    const W: any = window as any;
    const Ctor = W.SpeechRecognition || W.webkitSpeechRecognition;
    if (!Ctor) { log("stt.unsupported"); return () => {}; }
    rec = new Ctor();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = "en-US";
    rec.onstart = () => log("stt.start");
    rec.onresult = (ev: any) => {
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const r = ev.results[i];
        const txt = r[0].transcript.trim();
        if (r.isFinal) { log("stt.final", { txt }); onFinal(txt); }
        else { log("stt.interim", { txt }); onInterim(txt); }
      }
    };
    rec.onerror = (e: any) => log("stt.error", e);
    rec.start();
  } catch (e) {
    log("stt.fail", e);
  }
  return () => { try { rec?.stop(); } catch {} };
}

export function stopPTT() { try { rec?.stop(); } catch {} }
