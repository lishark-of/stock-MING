import { useEffect, useRef, useState } from "react";
import { cancelTask, getTask, type ApiEnvelope, type TaskRecord } from "../api/client";
import DataLineageTable from "./DataLineageTable";
import DeepSeekModelStrategyLedger from "./DeepSeekModelStrategyLedger";
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
        <div className="task-panel">
          <div className="task-panel__head">
            <StatusBadge label={lookupError.error} tone="bad" />
            <span>{taskId}</span>
          </div>
          <p>任务状态读取失败：{lookupError.error}</p>
          <p>GET /api/tasks/{"{task_id}"} 只读取本地任务状态，不调用 Tushare、DeepSeek 或 GitHub。</p>
          <p>call_ledger: {lookupError.call_ledger.length}</p>
          {lookupError.warnings.length ? <p className="risk-note">{String(lookupError.warnings[0])}</p> : null}
          {lookupError.call_ledger.length ? <DataLineageTable rows={lookupError.call_ledger} /> : <p className="empty-state">暂无 task lookup call_ledger。</p>}
        </div>
      );
    }
    return <p>任务状态读取中：{taskId}</p>;
  }
  const callLedger = task.call_ledger ?? [];
  const statusHistory = task.status_history ?? [];
  const cancellable = task.status === "pending" || task.status === "running";

  return (
    <div className="task-panel">
      <div className="task-panel__head">
        <StatusBadge label={task.status} tone={toneForStatus(task.status)} />
        <span>{task.task_type}</span>
      </div>
      <progress value={task.progress ?? 0} max={1} />
      <p>{task.current_step}</p>
      <p>task_id: {task.task_id}</p>
      <p>backend: {task.backend ?? "local_fallback"}</p>
      <p>storage_source: {task.storage_source ?? "memory_or_sqlite_fallback"}</p>
      <p>created_at: {task.created_at ?? "--"}</p>
      <p>started_at: {task.started_at ?? "--"}</p>
      <p>finished_at: {task.finished_at ?? "--"}</p>
      <TaskBoundarySummary task={task} />
      <p>call_ledger: {callLedger.length}</p>
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
      <DeepSeekModelStrategyLedger callLedger={callLedger} />
      {callLedger.length ? <DataLineageTable rows={callLedger} /> : <p className="empty-state">暂无 call_ledger 记录。</p>}
      {statusHistory.length ? (
        <>
          <p>status_history: {statusHistory.length}</p>
          <DataLineageTable rows={statusHistory} />
        </>
      ) : null}
    </div>
  );
}
