// Simple speech synthesis + recognition helpers (browser-only).
// Gracefully degrades if features are unsupported.

declare global {
  interface Window {
    webkitSpeechRecognition?: any;
  }
}

export function canSpeak() {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

export function speak(text: string) {
  if (!canSpeak()) return;
  const u = new SpeechSynthesisUtterance(text);
  u.rate = 1; // tweak if needed
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(u);
}

export function stopSpeak() {
  if (!canSpeak()) return;
  window.speechSynthesis.cancel();
}

export function canListen() {
  return typeof window !== "undefined" && (!!window.webkitSpeechRecognition || "SpeechRecognition" in window);
}

export type ListenOptions = {
  lang?: string;
  onResult?: (finalTranscript: string) => void;
  onError?: (err: any) => void;
};

export function startListening({ lang = "en-US", onResult, onError }: ListenOptions = {}) {
  if (!canListen()) return () => {};
  const Rec = (window as any).SpeechRecognition || window.webkitSpeechRecognition;
  const rec = new Rec();
  rec.lang = lang;
  rec.interimResults = false;
  rec.continuous = true;

  rec.onresult = (e: any) => {
    const result = e.results[e.results.length - 1];
    const transcript = result[0].transcript.trim();
    onResult?.(transcript);
  };
  rec.onerror = (e: any) => onError?.(e);
  rec.onend = () => { /* auto stop */ };

  rec.start();
  return () => {
    try { rec.stop(); } catch {}
  };
}
