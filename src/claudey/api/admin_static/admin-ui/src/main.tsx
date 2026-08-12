import * as React from "react";
import { createRoot } from "react-dom/client";

import "./styles/globals.css";
import { App } from "./app";

// Restore persisted theme before first paint to avoid a flash.
try {
  const theme = localStorage.getItem("claudey.theme");
  if (theme === "dark") document.documentElement.classList.add("dark");
} catch {
  /* storage unavailable — default light */
}

const root = document.getElementById("root");
if (!root) throw new Error("Missing #root mount point");

createRoot(root).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);