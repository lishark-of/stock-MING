import type { TaskCreationEnvelope } from "../api/client";
import DataLineageTable from "./DataLineageTable";

export default function TaskLaunchReceipt({ receipt }: { receipt: TaskCreationEnvelope | null }) {
  if (!receipt) return null;
  const task = receipt.data?.task;
  const callLedger = receipt.call_ledger.length ? receipt.call_ledger : task?.call_ledger ?? [];
  const warnings = receipt.warnings.length ? receipt.warnings : task?.warnings ?? [];

  return (
    <div className="task-panel">
      <div className="task-panel__head">
        <span>任务创建回执</span>
        <span>{receipt.ok ? "accepted" : String(receipt.error ?? "failed")}</span>
      </div>
      <p>task_id: {String(receipt.data?.task_id ?? "--")}</p>
      <p>top_level_call_ledger: {callLedger.length}</p>
      <p>按钮任务回执只展示 FastAPI 返回的审计血缘；不调用 Tushare、DeepSeek 或 GitHub。</p>
      {warnings.length ? <p className="risk-note">{String(warnings[0])}</p> : null}
      {callLedger.length ? <DataLineageTable rows={callLedger} /> : <p className="empty-state">暂无任务创建 call_ledger。</p>}
    </div>
  );
}
