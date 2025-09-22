/// <reference lib="webworker" />
import Tesseract from "tesseract.js";

type JobIn = { id: string; file: Blob; lang?: string };
type JobOut =
  | { id: string; type: "progress"; progress: number; status?: string }
  | { id: string; type: "result"; text: string }
  | { id: string; type: "error"; message: string };

self.onmessage = async (e: MessageEvent<JobIn>) => {
  const { id, file, lang = "eng" } = e.data;
  try {
    const { data } = await Tesseract.recognize(file, lang, {
      logger: (m) => {
        if (m.status === "recognizing text") {
          (self as any).postMessage({
            id,
            type: "progress",
            progress: Math.round((m.progress || 0) * 100),
            status: m.status,
          } as JobOut);
        }
      },
    });
    const text = data.text || "";
    (self as any).postMessage({ id, type: "result", text } as JobOut);
  } catch (err: any) {
    (self as any).postMessage({
      id,
      type: "error",
      message: err?.message || String(err),
    } as JobOut);
  }
};

export {};
