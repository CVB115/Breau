// src/main.tsx
import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "./styles/index.css";

import AppRouter from "./router";
import { UserProvider } from "./context/UserProvider";
import { ActiveBeanGearProvider } from "./context/ActiveBeanGearProvider";
import { ToastProvider } from "./context/ToastProvider";
import NetProvider from "./context/NetProvider";
import LoadingBar from "./components/LoadingBar";
import WarmupProvider from "./providers/WarmupProvider";

const root = createRoot(document.getElementById("root")!);

root.render(
  <React.StrictMode>
    <BrowserRouter>
      <UserProvider>
        {/* Persist and share active bean/gear selections across the app */}
        <ActiveBeanGearProvider>
          <ToastProvider>
            <NetProvider>
              <WarmupProvider>
                <LoadingBar />
                <div className="app-shell">
                  <AppRouter />
                </div>
              </WarmupProvider>
            </NetProvider>
          </ToastProvider>
        </ActiveBeanGearProvider>
      </UserProvider>
    </BrowserRouter>
  </React.StrictMode>
);

// Register SW (served from /public/sw.js)
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch((err) => {
      // non-fatal if it fails
      console.warn("SW register failed:", err);
    });
  });
}
