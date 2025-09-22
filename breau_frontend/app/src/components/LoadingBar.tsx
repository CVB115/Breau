import { useEffect, useRef, useState } from "react";
import { NetEvent, registerNetTap } from "@api/client";

export default function LoadingBar() {
  const [active, setActive] = useState(0);
  const [visible, setVisible] = useState(false);
  const [width, setWidth] = useState(0);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    const off = registerNetTap((ev: NetEvent) => {
      if (ev.phase === "request") {
        setActive((n) => n + 1);
        setVisible(true);
        if (timer.current) window.clearInterval(timer.current);
        setWidth(10);
        timer.current = window.setInterval(() => {
          setWidth((w) => Math.min(90, w + Math.random() * 10));
        }, 200);
      } else {
        setActive((n) => Math.max(0, n - 1));
      }
    });
    return () => { off(); if (timer.current) window.clearInterval(timer.current); };
  }, []);

  useEffect(() => {
    if (active === 0 && visible) {
      if (timer.current) { window.clearInterval(timer.current); timer.current = null; }
      setWidth(100);
      const t = window.setTimeout(() => { setVisible(false); setWidth(0); }, 350);
      return () => window.clearTimeout(t);
    }
  }, [active, visible]);

  if (!visible) return null;
  return (
    <div style={{
      position: "fixed", top: 0, left: 0, height: 3, width: "100%",
      background: "transparent", zIndex: 1200
    }}>
      <div style={{
        height: "100%", width: `${width}%`,
        background: "linear-gradient(90deg, #1a66ff, #6ba8ff)",
        transition: "width .2s ease"
      }} />
    </div>
  );
}
