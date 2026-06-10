import PacketCard from "../components/PacketCard";
import MetricGrid from "../components/MetricGrid";
import DataLineageTable from "../components/DataLineageTable";

const LEGACY_BOUNDARIES = [
  { boundary: "正式主入口", status: "Command Center 3 React/Tauri", note: "普通主流程请使用 3.0 前端和 FastAPI cache/task API。" },
  { boundary: "Streamlit 定位", status: "legacy/admin/debug", note: "保留用于回退、排查、旧功能兼容和管理操作。" },
  { boundary: "外部请求", status: "button_gated", note: "Tushare、DeepSeek、GitHub 校验不得在旧入口启动时自动触发。" },
  { boundary: "任务路径", status: "FastAPI task pipeline", note: "重计算应逐步迁移到 POST task，并写入 call_ledger。" },
  { boundary: "真实交易", status: "disabled", note: "不执行真实交易，不自动下单，不绕过 strategy_execution_packet。" },
  { boundary: "功能保留", status: "no feature cuts", note: "旧工作台功能保留到 3.0 页面/API 等价迁移完成。" }
];

const LEGACY_ALLOWED_USES = [
  { use_case: "旧功能回退", allowed: true, route: "app.py", guard: "legacy/admin/debug only" },
  { use_case: "开发调试", allowed: true, route: "app.py", guard: "不绕过按钮门控" },
  { use_case: "管理与诊断", allowed: true, route: "app.py", guard: "不自动外联" },
  { use_case: "普通主流程", allowed: false, route: "React/Tauri", guard: "迁往 Command Center 3" },
  { use_case: "真实交易", allowed: false, route: "none", guard: "永不自动触发" }
];

export default function LegacyTools() {
  return (
    <>
      <PacketCard title="Legacy / Admin / Debug" subtitle="Streamlit 2.0 保留为 legacy，不再作为正式主应用" status="legacy">
        <MetricGrid
          items={[
            { label: "正式入口", value: "Command Center 3" },
            { label: "Streamlit", value: "legacy/admin/debug" },
            { label: "普通主流程", value: "迁往 React/Tauri", tone: "good" },
            { label: "自动外联", value: "禁止", tone: "good" },
            { label: "真实交易", value: "禁止", tone: "good" },
            { label: "自动下单", value: "禁止", tone: "good" }
          ]}
        />
        <p>旧版 Streamlit 入口仍保留在 app.py，用于排查、管理、旧功能回退和阶段性兼容。</p>
        <p>普通主流程请使用 Command Center 3；3.0 正式主路径会逐步迁移到 React + FastAPI + Tauri。</p>
        <p>Legacy 页面不会创建任务，不调用 Tushare、DeepSeek 或 GitHub，也不会绕过 strategy_execution_packet。</p>
      </PacketCard>

      <PacketCard title="Legacy 边界" subtitle="旧入口保留，但不得重新成为主路径" status="read_only">
        <DataLineageTable rows={LEGACY_BOUNDARIES} />
      </PacketCard>

      <PacketCard title="允许用途" subtitle="回退和调试可保留，普通主流程逐步迁出" status="guarded">
        <DataLineageTable rows={LEGACY_ALLOWED_USES} />
      </PacketCard>
    </>
  );
}
