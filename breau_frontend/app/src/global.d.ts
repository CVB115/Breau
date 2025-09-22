// src/global.d.ts
// Minimal stubs so TS stops complaining. Safe to delete later if you add proper DOM lib.

declare class MediaRecorder extends EventTarget {
  readonly mimeType: string;
  readonly state: "inactive" | "recording" | "paused";
  readonly stream: MediaStream;
  ondataavailable: ((this: MediaRecorder, ev: BlobEvent) => any) | null;
  onstop: ((this: MediaRecorder, ev: Event) => any) | null;
  start(timeslice?: number): void;
  stop(): void;
  pause(): void;
  resume(): void;
  requestData(): void;
  constructor(stream: MediaStream, options?: MediaRecorderOptions);
}

interface BlobEvent extends Event {
  readonly data: Blob;
  readonly timecode: number;
}

interface MediaRecorderOptions {
  mimeType?: string;
  audioBitsPerSecond?: number;
  bitsPerSecond?: number;
}
