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

function taskLedgerApi(row: Record<string, unknown>) {
  return String(row.api ?? "");
}

function isTushareProviderLedgerRow(row: Record<string, unknown>) {
  return row.tushare_called === true || (row.external_calls_triggered === true && taskLedgerApi(row).startsWith("tushare_"));
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
  const tushareProviderRows = callLedger.filter(isTushareProviderLedgerRow);
  const tushareProviderSuccessCount = tushareProviderRows.filter((row) => String(row.call_status ?? "") === "success").length;
  const taskDeepSeekCalled = task.deepseek_called === true || callLedger.some((row) => row.deepseek_called === true);
  const taskGithubCalled = task.github_called === true || callLedger.some((row) => row.github_called === true);
  const statusHistory = task.status_history ?? [];
  const cancellable = task.status === "pending" || task.status === "running";
  const taskStatusLabel = labelForStatus(task.status);
  const successRefreshMessage =
    task.status === "success" && onSuccess
      ? "任务成功后已通知页面刷新本地回放；这不会创建新 task、不调用 Tushare、DeepSeek 或 GitHub、不执行真实交易。"
      : "";
  const callLedgerQuickStatus = tushareProviderRows.length
    ? `Tushare ${tushareProviderSuccessCount}/${tushareProviderRows.length} 个接口已写入主任务 call_ledger`
    : callLedger.length
      ? `已回放 ${callLedger.length} 条本地审计记录`
      : "等待任务写入本地审计记录";
  const callLedgerQuickNext = tushareProviderRows.length
    ? "刷新本地 cache 后查看股票量化推演和次日图谱"
    : callLedger.length
      ? "普通用户只看数量和边界；明细在审计详情中展开"
      : "任务完成后再看审计记录数量";
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
      当前状态: callLedgerQuickStatus,
      用户下一步: callLedgerQuickNext,
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
  const candidateRadarResultReplay =
    task.output_packet_key === "command_center_3_candidate_radar_cache" ||
    task.task_type.includes("candidate_radar_quant_projection");
  const taskTushareFirstQuickRows = [
    {
      回放项: "Tushare-first ledger",
      当前状态: tushareProviderRows.length
        ? `Tushare ${tushareProviderSuccessCount}/${tushareProviderRows.length} 个接口已写入 task.call_ledger`
        : "等待确认任务写入 Tushare provider ledger",
      用户下一步: tushareProviderRows.length ? "打开股票量化推演和次日图谱回放本地结果" : "继续等待任务完成或查看阻断原因",
      证据: `task.call_ledger; total=${callLedger.length}`,
      边界: "TaskStatusPanel 只读当前 task.call_ledger；不补调 Tushare、DeepSeek 或 GitHub。"
    },
    {
      回放项: "DeepSeek",
      当前状态: taskDeepSeekCalled ? "检测到 DeepSeek ledger；需查看治理详情" : "DeepSeek skipped / 未调用；P1/P2/P3 不等待模型",
      用户下一步: "DeepSeek governed executor 单独补，不阻塞 Tushare-first 和基础图谱",
      证据: "task.deepseek_called + task.call_ledger",
      边界: "模型输出不能覆盖价格、factor、operation_zones 或 strategy action。"
    },
    {
      回放项: "交易边界",
      当前状态: task.does_not_execute_trades === false || task.does_not_modify_strategy_action === false
        ? "阻断：任务 ledger 标记交易或 action 边界异常"
        : "不交易、不改 strategy action",
      用户下一步: taskGithubCalled ? "先查看审计详情里的外部调用来源" : "把结果当研究线索，不当买入指令",
      证据: "task safety flags",
      边界: "真实交易路径继续隔离；Radar candidate 不是买入指令。"
    }
  ];
  const p3ResultReplayRows = candidateRadarResultReplay
    ? [
        {
          结果入口: "股票量化推演",
          当前状态: task.status === "success" ? "可刷新后回放本地量化推演摘要" : "等待任务完成后回放",
          用户下一步: "打开股票量化推演，先看 P3 可读结论、支持/压制和缺失证据",
          入口: "#factor",
          边界: "只切换本地模块路由；不创建 task、不调用 Tushare/DeepSeek、不写交易动作。"
        },
        {
          结果入口: "次日图谱",
          当前状态: task.status === "success" ? "可复核本地 next-session cache" : "等待 cache / packet 回放",
          用户下一步: "打开次日图谱，复核路径、参考线和 operation_zones 来源",
          入口: "#next",
          边界: "只读本地图谱；不生成交易指令、不覆盖 strategy action。"
        },
        {
          结果入口: "下一票雷达",
          当前状态: "可回到候选页复核候选来源、分组和一屏行动",
          用户下一步: "把结果当研究线索，不当买入指令",
          入口: "#candidates",
          边界: "Radar candidate 不是买入指令；真实交易路径继续隔离。"
        }
      ]
    : [
        {
          结果入口: "Packet 回放",
          当前状态: task.output_packet_key ? `可按 ${task.output_packet_key} 查本地 packet` : "等待输出 packet",
          用户下一步: "打开 Packet 注册表，只读查看本地输出",
          入口: "#packets",
          边界: "Packet 回放不是生产验收，也不会触发 provider/model。"
        },
        {
          结果入口: "Task Monitor",
          当前状态: "可回到任务列表复核状态",
          用户下一步: "只读查看任务列表和本地状态",
          入口: "#tasks",
          边界: "任务列表只读轮询本地 FastAPI；不创建外部工作。"
        }
      ];
  const p3ResultReplayLinks = candidateRadarResultReplay
    ? [
        { href: "#factor", label: "查看股票量化推演", title: "切换到股票量化推演模块；只读 cache / ledger / packet", aria: "open stock quant result from task status" },
        { href: "#next", label: "查看次日图谱", title: "切换到次日图谱模块；只读本地 next-session cache", aria: "open next session map from task status" },
        { href: "#candidates", label: "回到下一票雷达", title: "切换到下一票雷达；复核候选来源和确认链路", aria: "open candidate radar from task status" }
      ]
    : [
        { href: "#packets", label: "查看 Packet", title: "切换到 Packet 注册表；只读本地输出", aria: "open packet registry from task status" },
        { href: "#tasks", label: "查看任务列表", title: "切换到 Task Monitor；只读任务状态", aria: "open task monitor from task status" }
      ];
  const showTaskFailureRecovery = task.status === "failed" || task.status === "cancelled";
  const taskFailureRecoveryRows = [
    {
      恢复项: "P0 一键启动预检",
      当前状态: task.status === "failed" ? "任务未成功；先确认前后端联通" : "任务已取消；先确认本地服务仍可读",
      用户下一步: "回到一键启动预检，确认后端、storage、cache 状态",
      入口: "#desktop",
      边界: "只读本地预检，不自动重试、不创建新 task。"
    },
    {
      恢复项: "手动回到原入口",
      当前状态: candidateRadarResultReplay ? "可回下一票雷达重新确认标的" : "可回任务列表或 Packet 注册表定位入口",
      用户下一步: candidateRadarResultReplay ? "核对股票代码后再点确认一次" : "从任务列表查看来源，再回原页面手动操作",
      入口: candidateRadarResultReplay ? "#candidates" : "#tasks",
      边界: "只有用户再次点击确认按钮才会创建任务；搜索输入和页面切换不外联。"
    },
    {
      恢复项: "保留本地证据",
      当前状态: "失败或取消只保留本地状态、审计数量和安全摘要",
      用户下一步: "不要把失败 packet 或审计明细当生产证据",
      入口: "#tasks",
      边界: "不展示凭据值、错误原文或交易动作；DeepSeek 仍需 governed executor。"
    }
  ];
  const taskFailureRecoveryLinks = [
    { href: "#desktop", label: "查看一键启动预检", title: "回到桌面预检；只读确认前后端联通", aria: "open desktop preflight from failed task status" },
    { href: candidateRadarResultReplay ? "#candidates" : "#tasks", label: candidateRadarResultReplay ? "回到下一票雷达" : "查看任务列表", title: "回到本地入口；再次确认前不会创建任务", aria: "open local recovery entry from failed task status" },
    { href: "#packets", label: "查看 Packet", title: "打开 Packet 注册表；只读查看本地输出", aria: "open packet registry from failed task status" }
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
      {candidateRadarResultReplay ? (
        <div aria-label="task status tushare first ledger quick read">
          <p className="risk-note">Tushare-first 速读：普通用户先看主任务是否已回放接口级 ledger；这张表只读当前任务状态，不创建新 task。</p>
          <DataLineageTable rows={taskTushareFirstQuickRows} />
        </div>
      ) : null}
      <div aria-label="task status p3 result replay quick read">
        <p className="risk-note">P3 结果入口速读：任务写回后按本地入口回放可解释结果；这些链接只切换本地页面，不创建 task、不调用 provider/model。</p>
        <DataLineageTable rows={p3ResultReplayRows} />
        <div className="actions" aria-label="task status p3 result replay links">
          {p3ResultReplayLinks.map((link) => (
            <a key={link.href} href={link.href} title={link.title} aria-label={link.aria}>{link.label}</a>
          ))}
        </div>
      </div>
      {showTaskFailureRecovery ? (
        <div aria-label="task status failed recovery quick read">
          <p className="risk-note">失败/取消恢复速读：先回 P0 确认前后端联通，再由用户手动回到原入口；这里不自动重试、不调用 provider/model、不执行真实交易。</p>
          <DataLineageTable rows={taskFailureRecoveryRows} />
          <div className="actions" aria-label="task status failed recovery links">
            {taskFailureRecoveryLinks.map((link) => (
              <a key={`${link.href}-${link.label}`} href={link.href} title={link.title} aria-label={link.aria}>{link.label}</a>
            ))}
          </div>
        </div>
      ) : null}
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
