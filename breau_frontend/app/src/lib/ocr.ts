let worker: Worker | null = null;

type Sub = {
  resolve: (text: string) => void;
  reject: (err: any) => void;
  onProgress?: (p: number) => void;
};

const pending = new Map<string, Sub>();

function ensureWorker() {
  if (!worker) {
    worker = new Worker(new URL("../workers/ocrWorker.ts", import.meta.url), {
      type: "module",
    });
    worker.onmessage = (e: MessageEvent<any>) => {
      const { id, type } = e.data || {};
      const sub = pending.get(id);
      if (!sub) return;
      if (type === "progress") {
        sub.onProgress?.(Number(e.data.progress || 0));
      } else if (type === "result") {
        sub.resolve(String(e.data.text || ""));
        pending.delete(id);
      } else if (type === "error") {
        sub.reject(new Error(e.data.message || "OCR error"));
        pending.delete(id);
      }
    };
  }
}

export function ocrOnWorker(
  file: File | Blob,
  lang = "eng",
  onProgress?: (percent: number) => void
): Promise<string> {
  ensureWorker();
  const id = Math.random().toString(36).slice(2);
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject, onProgress });
    worker!.postMessage({ id, file, lang });
  });
}

export function terminateOcrWorker() {
  if (worker) {
    worker.terminate();
    worker = null;
    pending.clear();
  }
}
