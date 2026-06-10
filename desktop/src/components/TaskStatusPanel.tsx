import { useEffect, useRef, useState } from "react";
import { cancelTask, getTask, type ApiEnvelope, type TaskRecord } from "../api/client";
import DataLineageTable from "./DataLineageTable";
import StatusBadge from "./StatusBadge";

type Props = {
  taskId: string;
  onSuccess?: () => void;
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

export default function TaskStatusPanel({ taskId, onSuccess }: Props) {
  const [task, setTask] = useState<TaskRecord | null>(null);
  const [cancelMessage, setCancelMessage] = useState("");
  const successNotified = useRef("");

  const loadTask = () => {
    if (!taskId) return;
    void getTask(taskId).then((res) => {
      const mergedTask = mergeTaskEnvelope(res);
      if (mergedTask) setTask(mergedTask);
    });
  };

  useEffect(() => {
    if (!taskId) return undefined;
    let active = true;
    const load = () => {
      void getTask(taskId).then((res) => {
        const mergedTask = mergeTaskEnvelope(res);
        if (active && mergedTask) setTask(mergedTask);
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
  if (!task) return <p>任务状态读取中：{taskId}</p>;
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
      <p>output_packet_key: {task.output_packet_key || "--"}</p>
      <p>external_calls_triggered: {String(task.external_calls_triggered ?? false)}</p>
      <p>Tushare / DeepSeek / GitHub: {String(task.tushare_called ?? false)} / {String(task.deepseek_called ?? false)} / {String(task.github_called ?? false)}</p>
      <p>does_not_execute_trades: {String(task.does_not_execute_trades ?? true)}</p>
      <p>does_not_modify_strategy_action: {String(task.does_not_modify_strategy_action ?? true)}</p>
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
      {task.error_message_safe ? <p className="risk-note">{task.error_message_safe}</p> : null}
      {task.warnings?.length ? <p className="risk-note">{task.warnings[0]}</p> : null}
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
