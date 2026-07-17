import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles.css";
import "./components/ProductSurface.css";
import "./routes/CommandCenterHome.css";
import "./routes/CandidateRadar.css";
import "./routes/FactorQuantHub.css";
import "./routes/NextSessionMap.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
