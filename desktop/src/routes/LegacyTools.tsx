import PacketCard from "../components/PacketCard";
import MetricGrid from "../components/MetricGrid";

export default function LegacyTools() {
  return (
    <PacketCard title="Legacy / Admin / Debug" subtitle="Streamlit 2.0 保留为 legacy，不再作为正式主应用">
      <MetricGrid
        items={[
          { label: "正式入口", value: "Command Center 3" },
          { label: "Streamlit", value: "legacy/admin/debug" },
          { label: "自动外联", value: "禁止", tone: "good" },
          { label: "真实交易", value: "禁止", tone: "good" }
        ]}
      />
      <p>旧版 Streamlit 入口仍保留在 app.py，用于排查、管理和阶段性兼容。</p>
      <p>3.0 正式主路径会逐步迁移到 React + FastAPI + Tauri。</p>
    </PacketCard>
  );
}
