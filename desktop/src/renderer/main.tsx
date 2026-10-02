import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles/neobrutal.css";
import "./styles/app.css";

const root = document.getElementById("root");
if (!root) throw new Error("The desktop root is unavailable.");
createRoot(root).render(
  <StrictMode>
    <App api={window.paperFactory} />
  </StrictMode>,
);
