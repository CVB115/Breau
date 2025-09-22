// src/api/ocr.ts
import { API } from "@api/endpoints";

export type OCRFields = {
  origin?: string | null;
  process?: string | null;
  variety?: string | null;        // CSV string for UI
  roast_level?: string | null;
  flavor_notes?: string[] | null;
};

export type OCRResult = {
  text?: string | null;
  fields?: OCRFields | null;
};

export async function ocrExtract(file: File): Promise<OCRResult> {
  const fd = new FormData();
  fd.append("file", file);                 // <-- FastAPI expects this exact name

  const res = await fetch(API.ocrExtract(), {
    method: "POST",
    body: fd,                              // <-- let the browser set multipart boundary
    // DO NOT set "Content-Type" manually
    credentials: "include",
  });

  if (!res.ok) {
    // try to surface FastAPI error nicely
    let msg = `${res.status} ${res.statusText}`;
    try {
      const j = await res.json();
      msg = JSON.stringify(j);
    } catch {}
    throw new Error(msg);
  }
  return (await res.json()) as OCRResult;
}
