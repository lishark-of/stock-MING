import { useEffect, useRef, useState } from "react";
import { cancelTask, getTask, type ApiEnvelope, type TaskRecord } from "../api/client";
import DataLineageTable from "./DataLineageTable";
import DeepSeekModelStrategyLedger from "./DeepSeekModelStrategyLedger";
import StateClarityRail from "./StateClarityRail";
import StatusBadge from "./StatusBadge";
import TaskBoundarySummary from "./TaskBoundarySummary";

type Props = {
  taskId: string;
  onSuccess?: () => void;
};

type TaskLookupError = {
  error: string;
  call_ledger: Array<Record<string, unknown>>;
  warnings: unknown[];
};

function toneForStatus(status: TaskRecord["status"]) {
  if (status === "success") return "good";
  if (status === "failed" || status === "cancelled") return "bad";
  return "warn";
}

function labelForStatus(status: TaskRecord["status"]) {
  if (status === "success") return "已完成";
  if (status === "failed") return "失败";
  if (status === "cancelled") return "已取消";
  if (status === "running") return "运行中";
  return "等待中";
}

function mergeTaskEnvelope(res: ApiEnvelope<TaskRecord>): TaskRecord | null {
  if (!res.ok) return null;
  const dataLedger = res.data.call_ledger ?? [];
  const dataWarnings = res.data.warnings ?? [];
  return {
    ...res.data,
    call_ledger: dataLedger.length ? dataLedger : res.call_ledger,
    warnings: dataWarnings.length ? dataWarnings : res.warnings
  };
}

function taskLookupError(res: ApiEnvelope<TaskRecord>): TaskLookupError | null {
  if (res.ok) return null;
  return {
    error: String(res.error ?? "task_lookup_failed"),
    call_ledger: res.call_ledger ?? [],
    warnings: res.warnings ?? []
  };
}

function stateForTaskStep(status: TaskRecord["status"], step: "queued" | "running" | "finished") {
  if (status === "failed" || status === "cancelled") return step === "finished" ? "blocked" : "done";
  if (status === "success") return "done";
  if (status === "pending") return step === "queued" ? "active" : "waiting";
  if (status === "running") return step === "running" ? "active" : step === "queued" ? "done" : "waiting";
  return "waiting";
}

export default function TaskStatusPanel({ taskId, onSuccess }: Props) {
  const [task, setTask] = useState<TaskRecord | null>(null);
  const [lookupError, setLookupError] = useState<TaskLookupError | null>(null);
  const [cancelMessage, setCancelMessage] = useState("");
  const successNotified = useRef("");

  const loadTask = () => {
    if (!taskId) return;
    void getTask(taskId).then((res) => {
      const mergedTask = mergeTaskEnvelope(res);
      if (mergedTask) {
        setTask(mergedTask);
        setLookupError(null);
        return;
      }
      setLookupError(taskLookupError(res));
    });
  };

  useEffect(() => {
    if (!taskId) return undefined;
    let active = true;
    const load = () => {
      void getTask(taskId).then((res) => {
        const mergedTask = mergeTaskEnvelope(res);
        if (!active) return;
        if (mergedTask) {
          setTask(mergedTask);
          setLookupError(null);
          return;
        }
        setLookupError(taskLookupError(res));
      });
    };
    load();
    const timer = window.setInterval(() => {
      if (!task || task.status === "pending" || task.status === "running") load();
    }, 1500);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [taskId, task?.status]);

  useEffect(() => {
    if (task?.status === "success" && task.task_id !== successNotified.current) {
      successNotified.current = task.task_id;
      onSuccess?.();
    }
  }, [onSuccess, task?.status, task?.task_id]);

  if (!taskId) return null;
  if (!task) {
    if (lookupError) {
      return (
        <div className="task-panel task-panel--failed motion-surface" data-task-state="lookup_failed" data-motion-scope="task_phase_clarity" data-motion-purpose="state_change_confirmation">
          <div className="task-panel__head">
            <StatusBadge label="读取失败" tone="bad" />
            <span>任务编号：{taskId}</span>
          </div>
          <p>任务状态读取失败：{lookupError.error}</p>
          <p>本地任务状态接口只读取任务记录，不调用 Tushare、DeepSeek 或 GitHub。</p>
          <p>查询审计记录：{lookupError.call_ledger.length}</p>
          {lookupError.warnings.length ? <p className="risk-note">{String(lookupError.warnings[0])}</p> : null}
          {lookupError.call_ledger.length ? <DataLineageTable rows={lookupError.call_ledger} /> : <p className="empty-state">暂无任务查询审计记录。</p>}
        </div>
      );
    }
    return <p className="panel-loading">正在读取任务状态：{taskId}</p>;
  }
  const callLedger = task.call_ledger ?? [];
  const statusHistory = task.status_history ?? [];
  const cancellable = task.status === "pending" || task.status === "running";
  const taskStatusLabel = labelForStatus(task.status);
  const successRefreshMessage =
    task.status === "success" && onSuccess
      ? "任务成功后已通知页面刷新本地回放；这不会创建新 task、不调用 Tushare、DeepSeek 或 GitHub、不执行真实交易。"
      : "";
  const p2WritebackQuickRows = [
    {
      写回面: "cache",
      当前状态: task.status === "success" ? "任务已完成；页面可刷新 GET cache 回放结果" : "等待任务 success 后回放",
      用户下一步: task.status === "success" ? "查看当前页面刷新后的本地结果" : "继续看任务状态轨",
      证据: task.storage_source ?? "memory_or_sqlite_fallback",
      边界: "TaskStatusPanel 只轮询本地 FastAPI 任务状态；不会补调 provider/model。"
    },
    {
      写回面: "call_ledger",
      当前状态: callLedger.length ? `已回放 ${callLedger.length} 条本地审计记录` : "等待任务写入本地审计记录",
      用户下一步: callLedger.length ? "普通用户只看数量和边界；明细在审计详情中展开" : "任务完成后再看审计记录数量",
      证据: "task.call_ledger",
      边界: "审计记录默认收起；不展示凭据值、raw log 或交易动作。"
    },
    {
      写回面: "packet",
      当前状态: task.output_packet_key ? `目标 packet：${task.output_packet_key}` : "等待任务声明输出 packet",
      用户下一步: task.status === "success" ? "刷新本地 cache 后打开对应结果入口" : "等待任务完成后再回放 packet",
      证据: "task.output_packet_key",
      边界: "packet 只作为本地回放目标；不代表生产验收或 14 LTG closeout。"
    }
  ];

  return (
    <div className={`task-panel task-panel--${task.status} motion-surface`} data-task-state={task.status} data-motion-scope="task_phase_clarity" data-motion-purpose="state_change_confirmation">
      <div className="task-panel__head">
        <StatusBadge label={taskStatusLabel} tone={toneForStatus(task.status)} />
        <span>{task.task_type}</span>
      </div>
      <StateClarityRail
        label="任务执行状态"
        state={task.status}
        steps={[
          { label: "排队", state: stateForTaskStep(task.status, "queued"), detail: "已记录" },
          { label: "运行", state: stateForTaskStep(task.status, "running"), detail: `${Math.round((task.progress ?? 0) * 100)}%` },
          { label: "完成", state: stateForTaskStep(task.status, "finished"), detail: taskStatusLabel }
        ]}
      />
      <progress className="task-progress" value={task.progress ?? 0} max={1} />
      <p>{task.current_step}</p>
      <p>任务编号：{task.task_id}</p>
      <p>运行方式：{task.backend ?? "local_fallback"}</p>
      <p>记录来源：{task.storage_source ?? "memory_or_sqlite_fallback"}</p>
      <p>创建时间：{task.created_at ?? "--"}</p>
      <p>开始时间：{task.started_at ?? "--"}</p>
      <p>结束时间：{task.finished_at ?? "--"}</p>
      {successRefreshMessage ? <p className="panelSuccessRefresh">{successRefreshMessage}</p> : null}
      <div aria-label="task status p2 writeback quick read">
        <p className="risk-note">P2 写回速读：普通用户先看 cache、call_ledger、packet 三面是否有本地回放信号；这张表只读任务状态，不创建新 task。</p>
        <DataLineageTable rows={p2WritebackQuickRows} />
      </div>
      <TaskBoundarySummary task={task} />
      <button
        disabled={!cancellable}
        onClick={() =>
          void cancelTask(task.task_id, "manual_cancel_from_task_status_panel").then((res) => {
            setCancelMessage(res.ok ? "本地取消请求已写入任务状态，不调用 Tushare、DeepSeek 或 GitHub。" : String(res.error ?? "cancel_failed"));
            loadTask();
          })
        }
      >
        本地取消任务
      </button>
      {cancelMessage ? <p className="risk-note">{cancelMessage}</p> : null}
      {task.warnings?.length ? <p className="risk-note">{task.warnings[0]}</p> : null}
      <details className="developer-audit-details" aria-label="task status audit details">
        <summary>任务审计详情</summary>
        <p>普通用户先看状态轨、当前步骤、本地回放提示和取消按钮；call ledger、model ledger 和状态历史默认收起。</p>
        <p>审计记录：{callLedger.length}</p>
        <DeepSeekModelStrategyLedger callLedger={callLedger} />
        {callLedger.length ? <DataLineageTable rows={callLedger} /> : <p className="empty-state">暂无任务审计记录。</p>}
        {statusHistory.length ? (
          <>
            <p>状态变化记录：{statusHistory.length}</p>
            <DataLineageTable rows={statusHistory} />
          </>
        ) : null}
      </details>
    </div>
  );
}
