// src/components/FloatingMic.tsx
import React, { useCallback, useEffect, useRef, useState } from "react";

type Props = {
  onFinal: (transcriptOrEvents: any) => void;
  lang?: string; // default en-US
};

export default function FloatingMic({ onFinal, lang = "en-US" }: Props) {
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);
  const recRef = useRef<any>(null);

  // Use backend streaming if you wired it; otherwise fallback to Web Speech API
  const start = useCallback(async () => {
    setError(null);
    setInterim("");
    // Web Speech API
    const SR: any = (window as any).webkitSpeechRecognition || (window as any).SpeechRecognition;
    if (!SR) {
      setError("Speech recognition not supported in this browser");
      return;
    }
    const rec = new SR();
    rec.lang = lang;
    rec.interimResults = true;
    rec.continuous = false;

    rec.onresult = (e: any) => {
      let finalText = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript || "";
        if (e.results[i].isFinal) finalText += t;
        else setInterim(t);
      }
      if (finalText.trim()) {
        onFinal(finalText.trim());
      }
    };
    rec.onerror = (ev: any) => setError(ev?.error || "mic error");
    rec.onend = () => setListening(false);

    // ask for mic with noise suppression
    try {
      await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: false }
      });
    } catch {
      setError("Mic permission denied");
      return;
    }

    recRef.current = rec;
    setListening(true);
    rec.start();
  }, [lang, onFinal]);

  const stop = useCallback(() => {
    try { recRef.current?.stop?.(); } catch {}
    setListening(false);
  }, []);

  useEffect(() => () => { try { recRef.current?.stop?.(); } catch {} }, []);

  return (
    <div
      className="floating-mic"
      style={{
        position: "fixed",
        right: 16,
        bottom: 16,
        zIndex: 1500,
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        padding: "10px 12px",
        borderRadius: 9999,
        background: "#14161a",
        border: "1px solid #1f2126",
        boxShadow: "0 6px 24px rgba(0,0,0,0.35)",
      }}
    >
      <span
        className="dot"
        style={{
          width: 8, height: 8, borderRadius: 999,
          background: listening ? "#2ecc71" : "#9aa0a6"
        }}
        aria-hidden
      />
      {listening && (
        <span className="text" style={{ fontSize: 12, opacity: 0.9 }}>
          {interim ? `🎤 ${interim}` : "Listening..."}
        </span>
      )}
      {error && (
        <span className="text" style={{ fontSize: 12, color: "#ff6b6b" }}>
          {error}
        </span>
      )}
      <button
        className="btn"
        onClick={() => (listening ? stop() : start())}
        style={{ marginLeft: 8 }}
        title={listening ? "Stop mic" : "Start dictation"}
      >
        {listening ? "Stop" : "Dictate"}
      </button>
    </div>
  );
}
