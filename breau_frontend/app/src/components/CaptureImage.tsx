import { useEffect, useRef, useState } from "react";

export default function CaptureImage({
  onCapture,
  label = "Open camera",
}: {
  onCapture: (f: File) => void;
  label?: string;
}) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [open, setOpen] = useState(false);

  async function openCam() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setOpen(true);
    } catch {
      alert("Camera not available");
    }
  }
  function closeCam() {
    streamRef.current?.getTracks().forEach(t => t.stop());
    streamRef.current = null;
    setOpen(false);
  }
  function snap() {
    if (!videoRef.current) return;
    const v = videoRef.current;
    const canvas = document.createElement("canvas");
    canvas.width = v.videoWidth;
    canvas.height = v.videoHeight;
    const ctx = canvas.getContext("2d")!;
    ctx.drawImage(v, 0, 0);
    canvas.toBlob((blob) => {
      if (!blob) return;
      const file = new File([blob], "capture.jpg", { type: "image/jpeg" });
      onCapture(file);
      closeCam();
    }, "image/jpeg", 0.9);
  }

  useEffect(() => () => closeCam(), []);

  if (!("mediaDevices" in navigator)) {
    return <button className="btn secondary" disabled title="Camera not supported">Camera</button>;
  }

  return (
    <>
      {!open && <button className="btn secondary" onClick={openCam}>{label}</button>}
      {open && (
        <div className="card col" style={{ position: "relative" }}>
          <video ref={videoRef} style={{ width: "100%", borderRadius: 12 }} />
          <div className="row" style={{ gap: 8 }}>
            <button className="btn" onClick={snap}>Capture</button>
            <button className="btn secondary" onClick={closeCam}>Close</button>
          </div>
        </div>
      )}
    </>
  );
}
