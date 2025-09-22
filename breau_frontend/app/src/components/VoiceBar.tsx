// src/components/VoiceBar.tsx
import { useTTS } from "@hooks/useTTS";
import { useEffect, useState, useRef } from "react";

type Props = {
  getSpeakText: () => string;
  onTranscript?: (output: any) => void;
  lang?: string;
};

function useBackendSTT(onFinal: (text: string, event?: any) => void) {
  const [isListening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunks = useRef<BlobPart[]>([]);

  const start = async () => {
    setError(null);
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const recorder = new MediaRecorder(stream);
    chunks.current = [];

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.current.push(e.data);
    };

    recorder.onstop = async () => {
      const blob = new Blob(chunks.current, { type: "audio/wav" });
      const form = new FormData();
      form.append("file", blob, "chunk.wav");

      try {
        const { text } = await fetch("/api/voice/chunk", {
          method: "POST",
          body: form,
        }).then((r) => r.json());

        setInterim(text);

        const events = await fetch("/api/nlp/interpret", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text }),
        }).then((r) => r.json());

        if (onFinal) {
          onFinal(text); // raw transcript
          events.forEach((ev: any) => onFinal(text, ev)); // parsed events
        }
      } catch (err: any) {
        setError("Voice/NLP failed");
        console.error(err);
      } finally {
        setListening(false);
      }
    };

    recorder.start();
    mediaRef.current = recorder;
    setListening(true);
  };

  const stop = () => {
    if (mediaRef.current?.state === "recording") mediaRef.current.stop();
  };

  const reset = () => setInterim("");

  return {
    isSupported: true,
    isListening,
    interim,
    error,
    start,
    stop,
    reset,
  };
}

export default function VoiceBar({ getSpeakText, onTranscript, lang = "en-US" }: Props) {
  const { isSupported: ttsOK, isSpeaking, speak, stop: stopTTS } = useTTS({ lang });
  const { isSupported, isListening, interim, error, start, stop, reset } = useBackendSTT((text, event) => {
    if (!text) return;
    if (event) onTranscript?.(event);
    else onTranscript?.(text);
  });

  return (
    <div className="card row" style={{ justifyContent: "space-between", alignItems: "center" }}>
      <div style={{ display: "grid", gap: 6 }}>
        {!ttsOK && <div style={{ color: "#ff6b6b" }}>TTS not supported</div>}
        {!isSupported && <div style={{ color: "#ff6b6b" }}>STT not supported</div>}
        {isListening && <div style={{ opacity: 0.8 }}>🎤 {interim || "Listening..."}</div>}
        {error && <div style={{ color: "#ff6b6b" }}>STT error: {error}</div>}
      </div>

      <div className="row" style={{ gap: 8 }}>
        <button
          className="btn secondary"
          onClick={() => (isSpeaking ? stopTTS() : speak(getSpeakText()))}
          disabled={!ttsOK}
          title="Read current step"
        >
          {isSpeaking ? "Stop" : "Speak"}
        </button>

        <button
          className="btn"
          onClick={() => (isListening ? (stop(), reset()) : start())}
          disabled={!isSupported}
          title="Dictate notes or commands"
        >
          {isListening ? "Stop Mic" : "Dictate"}
        </button>
      </div>
    </div>
  );
}
