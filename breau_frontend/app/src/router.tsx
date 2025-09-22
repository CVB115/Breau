// src/router.tsx
import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";

import Home from "@pages/Home";

// Brew (shared)
import BrewIndex from "@pages/Brew";
import Assess from "@pages/Brew/Assess";
import BrewSummary from "@pages/Brew/Summary";

// Manual (Log) flow
import ManualSetup from "@pages/Brew/Manual/Setup";
import ManualLog from "@pages/Brew/Manual/Log";

// Suggest flow
import Goals from "@pages/Brew/Suggest/Goals";
import Preview from "@pages/Brew/Suggest/Preview";
import Guide from "@pages/Brew/Suggest/Guide";
import Rate from "@pages/Brew/Suggest/Rate";


// History
import HistoryIndex from "@pages/History";
import SessionDetail from "@pages/History/SessionDetail";

// Profile
import ProfileIndex from "@pages/Profile";
import EditProfile from "@pages/Profile/EditProfile";
import Gear from "@pages/Profile/Gear";
import Beans from "@pages/Profile/Beans";
import TasteGoals from "@pages/Profile/TasteGoals";
import Settings from "@pages/Profile/Settings";
import ExportReset from "@pages/Profile/ExportReset";
import DevTools from "@pages/Profile/DevTools";

import BottomNav from "@components/BottomNav";

export default function AppRouter() {
  return (
    <>
      <Routes>
        <Route path="/" element={<Home />} />

        {/* Brew */}
        <Route path="/brew" element={<BrewIndex />} />
        <Route path="/brew/suggest" element={<Goals />} />
        <Route path="/brew/suggest/goals" element={<Navigate to="/brew/suggest" replace />} />
        <Route path="/brew/suggest/preview" element={<Preview />} />
        <Route path="/brew/suggest/guide" element={<Guide />} />
        <Route path="/brew/suggest/rate" element={<Rate />} />
        <Route path="/brew/assess" element={<Assess />} />
        {/* choose which summary you want to show after Assess */}
        <Route path="/brew/summary" element={<BrewSummary />} />
        <Route path="/brew/summary/:session_id" element={<BrewSummary />} />
        {/* or: <Route path="/brew/summary" element={<SuggestSummary />} /> */}

        {/* Manual (Log) */}
        <Route path="/brew/manual" element={<ManualSetup />} />
        <Route path="/brew/manual/log" element={<ManualLog />} />
        {/* removed: /brew/manual/guide/:id — no matching screen */}

        {/* History */}
        <Route path="/history" element={<HistoryIndex />} />
        <Route path="/history/:id" element={<SessionDetail />} />
        <Route path="/brew/session/:id" element={<SessionDetail />} />

        {/* Profile */}
        <Route path="/profile" element={<ProfileIndex />} />
        <Route path="/profile/edit" element={<EditProfile />} />
        <Route path="/profile/gear" element={<Gear />} />
        <Route path="/profile/beans" element={<Beans />} />
        <Route path="/profile/taste-goals" element={<TasteGoals />} />
        <Route path="/profile/settings" element={<Settings />} />
        <Route path="/profile/export-reset" element={<ExportReset />} />
        <Route path="/profile/devtools" element={<DevTools />} />

        {/* Aliases */}
        <Route path="/beans" element={<Navigate to="/profile/beans" replace />} />
        <Route path="/beans/scan" element={<Navigate to="/profile/beans?scan=1" replace />} />

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>

      <BottomNav />
    </>
  );
}
