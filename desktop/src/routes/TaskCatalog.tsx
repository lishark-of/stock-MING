import { useEffect, useState } from "react";
import { cancelTask, getTaskCatalog, getTasks, type TaskRecord } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import StatusBadge from "../components/StatusBadge";

export default function TaskCatalog() {
  const [catalog, setCatalog] = useState<Record<string, unknown>>({});
  const [taskRecords, setTaskRecords] = useState<TaskRecord[]>([]);

  const refreshTasks = () => {
    void getTasks().then((res) => setTaskRecords(res.data.tasks ?? []));
  };

  useEffect(() => {
    void getTaskCatalog().then((res) => setCatalog(res.data));
    refreshTasks();
  }, []);

  const policy = catalog.policy as Record<string, unknown> | undefined;
  const catalogTasks = catalog.tasks as Array<Record<string, unknown>> | undefined;
  const externalSources = catalog.external_sources as unknown[] | undefined;
  const taskRows = taskRecords.map((task) => ({
    task_id: task.task_id,
    task_type: task.task_type,
    status: task.status,
    progress: task.progress,
    current_step: task.current_step,
    output_packet_key: task.output_packet_key,
    backend: task.backend ?? "local_fallback",
    call_ledger_count: task.call_ledger?.length ?? 0,
    does_not_execute_trades: true,
    does_not_modify_strategy_action: true
  }));

  return (
    <>
      <div className="page-head">
        <h1>任务目录</h1>
        <StatusBadge label={String(catalog.status ?? "catalog")} tone={catalog.status === "ready" ? "good" : "neutral"} />
      </div>

      <MetricGrid
        items={[
          { label: "任务数量", value: catalog.task_count as number | undefined },
          { label: "任务记录", value: taskRecords.length },
          { label: "全部按钮门控", value: policy?.all_tasks_button_gated, tone: policy?.all_tasks_button_gated === false ? "bad" : "good" },
          { label: "call ledger required", value: policy?.call_ledger_required_for_all, tone: policy?.call_ledger_required_for_all === false ? "bad" : "good" },
          { label: "cache API 外联", value: policy?.cache_api_external_calls === true ? "存在" : "无", tone: policy?.cache_api_external_calls === true ? "bad" : "good" },
          { label: "真实交易", value: policy?.does_not_execute_trades === false ? "可能" : "禁止", tone: policy?.does_not_execute_trades === false ? "bad" : "good" },
          { label: "修改 action", value: policy?.does_not_modify_strategy_action === false ? "可能" : "不会", tone: policy?.does_not_modify_strategy_action === false ? "bad" : "good" },
          { label: "外部源", value: externalSources?.join(" / ") || "无" },
          { label: "已触发外部调用", value: catalog.external_calls_triggered === true ? "是" : "否", tone: catalog.external_calls_triggered === true ? "bad" : "good" }
        ]}
      />

      <div className="grid">
        <PacketCard title="任务边界" subtitle="只读任务目录；不会创建任务；POST task 才可能触发外部请求" status="read_only">
          <p>本页只读取 FastAPI 的任务目录 cache 和 GET /api/tasks 任务记录，不调用 Tushare、DeepSeek 或 GitHub。</p>
          <p>任务执行必须由对应 POST API 按钮触发，并且需要写入 call_ledger_required_for_all 对应的审计记录。</p>
          <p>does_not_execute_trades 与 does_not_modify_strategy_action 必须保持为 true。</p>
        </PacketCard>

        <PacketCard title="外部请求策略" subtitle="GET catalog 不外联；按钮任务才可能进入外部源" status={String(policy?.post_task_may_trigger_external_request ?? true)}>
          <p>possible external sources: {externalSources?.join(", ") || "none"}</p>
          <p>Tushare called: {String(catalog.tushare_called ?? false)}</p>
          <p>DeepSeek called: {String(catalog.deepseek_called ?? false)}</p>
          <p>GitHub called: {String(catalog.github_called ?? false)}</p>
        </PacketCard>
      </div>

      <PacketCard title="任务清单" subtitle="按钮门控、可能外部源和输出 packet" status="catalog">
        <DataLineageTable rows={catalogTasks ?? []} />
      </PacketCard>

      <PacketCard title="任务记录" subtitle="GET /api/tasks 只读状态；不会创建任务" status="read_only">
        <DataLineageTable rows={taskRows} />
      </PacketCard>

      <PacketCard title="取消任务" subtitle="POST /api/tasks/{task_id}/cancel 只改本地任务状态；不外联、不交易" status="local_cancel">
        <p>取消入口只面向 pending / running 任务，写入 local_task_cancel 调用血缘，并把步骤标记为 cancelled_by_user_no_external_call。</p>
        <p>不会调用 Tushare、DeepSeek 或 GitHub，不执行真实交易，不修改 strategy action。</p>
        <div className="button-row">
          {taskRecords.map((task) => {
            const cancellable = task.status === "pending" || task.status === "running";
            return (
              <button
                key={task.task_id}
                disabled={!cancellable}
                onClick={() => void cancelTask(task.task_id).then(() => refreshTasks())}
              >
                取消 {task.task_type}
              </button>
            );
          })}
        </div>
      </PacketCard>

      <PacketCard title="原始目录 payload" subtitle="调试用 JSON；不含 token/key" status="safe">
        <JsonDetails title="task catalog raw" data={catalog} />
        <JsonDetails title="task records raw" data={taskRecords} />
      </PacketCard>
    </>
  );
}
