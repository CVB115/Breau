import { useState, useCallback } from "react";

export function useSTT({ onResult }: { onResult: (text: string, events: any[]) => void }) {
  const [active, setActive] = useState(false);
  const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder | null>(null);
  const [chunks, setChunks] = useState<BlobPart[]>([]);

  const start = useCallback(async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const recorder = new MediaRecorder(stream);
    setMediaRecorder(recorder);
    setChunks([]);

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) {
        setChunks((prev) => [...prev, e.data]);
      }
    };

    recorder.onstop = async () => {
      const blob = new Blob(chunks, { type: "audio/wav" });
      const form = new FormData();
      form.append("file", blob, "chunk.wav");

      try {
        // STT
        const { text } = await fetch("/api/voice/chunk", {
          method: "POST",
          body: form,
        }).then((res) => res.json());

        // NLP
        const events = await fetch("/api/nlp/interpret", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text }),
        }).then((res) => res.json());

        onResult(text, events);
      } catch (err) {
        console.error("STT/NLP failed:", err);
        onResult("(failed)", []);
      }
    };

    recorder.start();
    setActive(true);
  }, [chunks]);

  const stop = useCallback(() => {
    if (mediaRecorder && mediaRecorder.state === "recording") {
      mediaRecorder.stop();
      setActive(false);
    }
  }, [mediaRecorder]);

  return { active, start, stop };
}
