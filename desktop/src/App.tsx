import { useState } from "react";
import Layout, { type RouteKey } from "./components/Layout";
import ChokepointScan from "./routes/ChokepointScan";
import CommandCenterHome from "./routes/CommandCenterHome";
import FactorQuantHub from "./routes/FactorQuantHub";
import LegacyTools from "./routes/LegacyTools";
import NextSessionMap from "./routes/NextSessionMap";
import SerenityMethodRadar from "./routes/SerenityMethodRadar";

export default function App() {
  const [route, setRoute] = useState<RouteKey>("home");
  return (
    <Layout active={route} onNavigate={setRoute}>
      {route === "home" ? <CommandCenterHome /> : null}
      {route === "next" ? <NextSessionMap /> : null}
      {route === "factor" ? <FactorQuantHub /> : null}
      {route === "chokepoint" ? <ChokepointScan /> : null}
      {route === "serenity" ? <SerenityMethodRadar /> : null}
      {route === "legacy" ? <LegacyTools /> : null}
    </Layout>
  );
}
