import { useState } from "react";
import Layout, { type RouteKey } from "./components/Layout";
import AShareEvidenceRadar from "./routes/AShareEvidenceRadar";
import ChokepointScan from "./routes/ChokepointScan";
import CommandCenterHome from "./routes/CommandCenterHome";
import DataCapabilityConsole from "./routes/DataCapabilityConsole";
import FactorQuantHub from "./routes/FactorQuantHub";
import HealthStatus from "./routes/HealthStatus";
import LegacyTools from "./routes/LegacyTools";
import MigrationStatus from "./routes/MigrationStatus";
import NextSessionMap from "./routes/NextSessionMap";
import PacketRegistry from "./routes/PacketRegistry";
import QuantBacktestLab from "./routes/QuantBacktestLab";
import SerenityMethodRadar from "./routes/SerenityMethodRadar";
import StorageOverview from "./routes/StorageOverview";
import StrategyTrace from "./routes/StrategyTrace";
import TaskCatalog from "./routes/TaskCatalog";
import TradeReviewLab from "./routes/TradeReviewLab";

export default function App() {
  const [route, setRoute] = useState<RouteKey>("home");
  return (
    <Layout active={route} onNavigate={setRoute}>
      {route === "home" ? <CommandCenterHome /> : null}
      {route === "health" ? <HealthStatus /> : null}
      {route === "evidence" ? <AShareEvidenceRadar /> : null}
      {route === "dataCapability" ? <DataCapabilityConsole /> : null}
      {route === "next" ? <NextSessionMap /> : null}
      {route === "factor" ? <FactorQuantHub /> : null}
      {route === "chokepoint" ? <ChokepointScan /> : null}
      {route === "serenity" ? <SerenityMethodRadar /> : null}
      {route === "packets" ? <PacketRegistry /> : null}
      {route === "migration" ? <MigrationStatus /> : null}
      {route === "storage" ? <StorageOverview /> : null}
      {route === "tasks" ? <TaskCatalog /> : null}
      {route === "strategy" ? <StrategyTrace /> : null}
      {route === "quant" ? <QuantBacktestLab /> : null}
      {route === "tradeReview" ? <TradeReviewLab /> : null}
      {route === "legacy" ? <LegacyTools /> : null}
    </Layout>
  );
}
