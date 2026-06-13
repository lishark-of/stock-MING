import type { TaskCreationEnvelope } from "../api/client";
import DataLineageTable from "./DataLineageTable";
import DeepSeekModelStrategyLedger from "./DeepSeekModelStrategyLedger";
import StateClarityRail from "./StateClarityRail";
import TaskBoundarySummary from "./TaskBoundarySummary";

export default function TaskLaunchReceipt({ receipt }: { receipt: TaskCreationEnvelope | null }) {
  if (!receipt) return null;
  const task = receipt.data?.task;
  const topLevelCallLedger = receipt.call_ledger ?? [];
  const taskCallLedger = task?.call_ledger ?? [];
  const callLedger = topLevelCallLedger.length ? topLevelCallLedger : taskCallLedger;
  const modelStrategyCallLedger = [...topLevelCallLedger, ...taskCallLedger];
  const warnings = receipt.warnings.length ? receipt.warnings : task?.warnings ?? [];

  return (
    <div className="task-panel task-panel--receipt motion-surface" data-task-state={receipt.ok ? "accepted" : "failed"} data-motion-scope="task_receipt_clarity" data-motion-purpose="state_change_confirmation">
      <div className="task-panel__head">
        <span>任务创建回执</span>
        <span>{receipt.ok ? "accepted" : String(receipt.error ?? "failed")}</span>
      </div>
      <StateClarityRail
        label="task receipt state"
        state={receipt.ok ? "accepted" : "failed"}
        steps={[
          { label: "accepted", state: receipt.ok ? "done" : "blocked", detail: receipt.ok ? "ok" : "failed" },
          { label: "ledger", state: callLedger.length ? "done" : "waiting", detail: String(callLedger.length) },
          { label: "boundary", state: task?.external_calls_triggered ? "blocked" : "done", detail: "safe" }
        ]}
      />
      <p>task_id: {String(receipt.data?.task_id ?? "--")}</p>
      <TaskBoundarySummary task={task} />
      <p>top_level_call_ledger: {topLevelCallLedger.length}</p>
      <p>task_call_ledger: {taskCallLedger.length}</p>
      <p>按钮任务回执只展示 FastAPI 返回的审计血缘；不调用 Tushare、DeepSeek 或 GitHub。</p>
      {warnings.length ? <p className="risk-note">{String(warnings[0])}</p> : null}
      <DeepSeekModelStrategyLedger callLedger={modelStrategyCallLedger} />
      {callLedger.length ? <DataLineageTable rows={callLedger} /> : <p className="empty-state">暂无任务创建 call_ledger。</p>}
    </div>
  );
}
