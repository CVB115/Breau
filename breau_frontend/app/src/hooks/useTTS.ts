// src/hooks/useTTS.ts
import { useCallback, useEffect, useRef, useState } from "react";

export function useTTS(opts?: { rate?: number; pitch?: number; voiceName?: string; lang?: string }) {
  const synth = typeof window !== "undefined" ? window.speechSynthesis : undefined;
  const [isSupported] = useState(() => !!synth);
  const [isSpeaking, setSpeaking] = useState(false);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const utterRef = useRef<SpeechSynthesisUtterance | null>(null);

  // load voices
  useEffect(() => {
    if (!synth) return;
    const load = () => setVoices(synth.getVoices());
    load();
    synth.onvoiceschanged = load;
    return () => { synth.onvoiceschanged = null; };
  }, [synth]);

  const stop = useCallback(() => {
    if (!synth) return;
    synth.cancel();
    setSpeaking(false);
    utterRef.current = null;
  }, [synth]);

  const speak = useCallback((text: string) => {
    if (!synth || !text) return;
    stop();
    const u = new SpeechSynthesisUtterance(text);
    u.rate = opts?.rate ?? 1.0;
    u.pitch = opts?.pitch ?? 1.0;
    if (opts?.lang) u.lang = opts.lang;
    if (opts?.voiceName) {
      const v = voices.find(v => v.name === opts.voiceName);
      if (v) u.voice = v;
    }
    u.onend = () => setSpeaking(false);
    u.onerror = () => setSpeaking(false);
    utterRef.current = u;
    setSpeaking(true);
    synth.speak(u);
  }, [synth, voices, opts?.rate, opts?.pitch, opts?.voiceName, opts?.lang, stop]);

  return { isSupported, isSpeaking, voices, speak, stop };
}
