import PacketCard from "../components/PacketCard";

export default function LegacyTools() {
  return (
    <PacketCard title="Legacy / Admin / Debug" subtitle="Streamlit 2.0 保留为 legacy，不再作为正式主应用">
      <p>旧版 Streamlit 入口仍保留在 app.py，用于排查、管理和阶段性兼容。</p>
      <p>3.0 正式主路径会逐步迁移到 React + FastAPI + Tauri。</p>
    </PacketCard>
  );
}
