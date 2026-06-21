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
        <span>任务创建记录</span>
        <span>{receipt.ok ? "已创建" : String(receipt.error ?? "创建失败")}</span>
      </div>
      <StateClarityRail
        label="任务创建状态"
        state={receipt.ok ? "accepted" : "failed"}
        steps={[
          { label: "创建结果", state: receipt.ok ? "done" : "blocked", detail: receipt.ok ? "已接收" : "失败" },
          { label: "审计记录", state: callLedger.length ? "done" : "waiting", detail: `${String(callLedger.length)} 条` },
          { label: "边界检查", state: task?.external_calls_triggered ? "blocked" : "done", detail: "安全" }
        ]}
      />
      <p>任务编号：{String(receipt.data?.task_id ?? "--")}</p>
      <TaskBoundarySummary task={task} />
      <p>页面审计记录：{topLevelCallLedger.length}</p>
      <p>任务审计记录：{taskCallLedger.length}</p>
      <p>按钮任务记录只展示 FastAPI 返回的审计血缘；不调用 Tushare、DeepSeek 或 GitHub。</p>
      {warnings.length ? <p className="risk-note">{String(warnings[0])}</p> : null}
      <DeepSeekModelStrategyLedger callLedger={modelStrategyCallLedger} />
      {callLedger.length ? <DataLineageTable rows={callLedger} /> : <p className="empty-state">暂无任务创建审计记录。</p>}
    </div>
  );
}
