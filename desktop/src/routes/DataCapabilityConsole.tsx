import { useEffect, useState } from "react";
import { getDataCapabilityCache } from "../api/client";
import DataLineageTable from "../components/DataLineageTable";
import JsonDetails from "../components/JsonDetails";
import MetricGrid, { type MetricItem } from "../components/MetricGrid";
import PacketCard from "../components/PacketCard";
import StatusBadge from "../components/StatusBadge";

function displayText(value: unknown, fallback = "--") {
  if (value === undefined || value === null || value === "") return fallback;
  return String(value);
}

function isTushareRow(row: Record<string, unknown>) {
  return displayText(row.provider, "").toLowerCase() === "tushare" || displayText(row.source, "").includes("Tushare");
}

function isAvailableState(value: unknown) {
  const text = displayText(value, "").toLowerCase();
  return text.includes("available") || text.includes("ready") || text.includes("可用");
}

function isRestrictedState(value: unknown) {
  const text = displayText(value, "").toLowerCase();
  return text.includes("permission") || text.includes("restricted") || text.includes("denied") || text.includes("权限");
}

function isPendingState(value: unknown) {
  const text = displayText(value, "").toLowerCase();
  return text.includes("empty") || text.includes("stale") || text.includes("fallback") || text.includes("manual") || text.includes("pending") || text.includes("跳过") || text.includes("缓存") || text.includes("无数据");
}

function countRows(rows: Array<Record<string, unknown>>, matcher: (value: unknown) => boolean) {
  return rows.filter((row) => matcher(row.capability_state ?? row.state ?? row.status ?? row.status_label)).length;
}

export default function DataCapabilityConsole() {
  const [cache, setCache] = useState<Record<string, unknown>>({});
  const [cacheEnvelopeLedger, setCacheEnvelopeLedger] = useState<Array<Record<string, unknown>>>([]);
  const [cacheEnvelopeWarnings, setCacheEnvelopeWarnings] = useState<Array<string>>([]);

  useEffect(() => {
    void getDataCapabilityCache().then((res) => {
      setCache(res.data);
      setCacheEnvelopeLedger(res.call_ledger ?? []);
      setCacheEnvelopeWarnings(res.warnings ?? []);
    });
  }, []);

  const dashboard = (cache.dashboard as Record<string, unknown> | undefined) ?? {};
  const consolePacket = (cache.console as Record<string, unknown> | undefined) ?? {};
  const healthLedger = (cache.data_health_ledger as Record<string, unknown> | undefined) ?? {};
  const counts = (cache.counts as Record<string, unknown> | undefined) ?? {};
  const policy = (cache.policy as Record<string, unknown> | undefined) ?? {};
  const providerCards = (cache.provider_cards as Array<Record<string, unknown>> | undefined) ?? [];
  const recoveryActions = (cache.recovery_actions as Array<Record<string, unknown>> | undefined) ?? [];
  const healthRows = (healthLedger.rows as Array<Record<string, unknown>> | undefined) ?? [];
  const payloadCallLedger = (cache.call_ledger as Array<Record<string, unknown>> | undefined) ?? [];
  const cacheWarnings = cacheEnvelopeWarnings.length ? cacheEnvelopeWarnings : ((cache.warnings as Array<string> | undefined) ?? []);
  const tushareProviderCard = providerCards.find((card) => isTushareRow(card)) ?? {};
  const tushareHealthRows = healthRows.filter(isTushareRow);
  const tushareAvailableCount = Number(tushareProviderCard.available_count ?? countRows(tushareHealthRows, isAvailableState));
  const tushareRestrictedCount = Number(tushareProviderCard.restricted_count ?? countRows(tushareHealthRows, isRestrictedState));
  const tusharePendingCount = Number(tushareProviderCard.pending_count ?? countRows(tushareHealthRows, isPendingState));
  const tushareRecoveryAction = recoveryActions.find((action) => isTushareRow(action)) ?? {};
  const dataCapabilityTushareSummary = tushareHealthRows.length || Object.keys(tushareProviderCard).length
    ? `Tushare 本地账本可读：可用 ${tushareAvailableCount}，受限 ${tushareRestrictedCount}，待补/缓存 ${tusharePendingCount}。`
    : "Tushare 数据能力等待本地账本；页面打开只显示 degraded，不自动探测接口。";
  const dataCapabilityTushareNextStep = tushareRestrictedCount || tusharePendingCount
    ? `先看受限/待补接口原因；需要更新时走按钮门控任务，当前建议：${displayText(tushareRecoveryAction.action_label, "继续只读本地缓存")}`
    : tushareAvailableCount
      ? "可用接口只作为本地证据来源；继续回首页、下一票雷达、量化推演和次日图谱读结果。"
      : "等待本地 data health 回放；不要把空账本当作无风险。";
  const dataCapabilityTushareTone: MetricItem["tone"] =
    tushareRestrictedCount ? "warn" : tushareAvailableCount ? "good" : "neutral";
  const dataCapabilityTushareOrdinaryItems: MetricItem[] = [
    {
      label: "Tushare 数据",
      value: dataCapabilityTushareSummary,
      tone: dataCapabilityTushareTone
    },
    {
      label: "可用接口",
      value: tushareAvailableCount ? `${tushareAvailableCount} 个可用` : "等待可用接口回放",
      tone: tushareAvailableCount ? "good" : "warn"
    },
    {
      label: "受限接口",
      value: tushareRestrictedCount ? `${tushareRestrictedCount} 个权限/配置受限` : "未标记受限",
      tone: tushareRestrictedCount ? "warn" : "good"
    },
    {
      label: "待补/缓存",
      value: tusharePendingCount ? `${tusharePendingCount} 个仍需窗口/缓存/手动复核` : "未标记待补",
      tone: tusharePendingCount ? "warn" : "good"
    },
    {
      label: "用户下一步",
      value: dataCapabilityTushareNextStep,
      tone: tushareAvailableCount ? "good" : "warn"
    },
    {
      label: "安全边界",
      value: "GET cache 只读；不 ping Tushare、DeepSeek、GitHub，不创建 task、不交易",
      tone: "good"
    }
  ];
  const dataCapabilityTushareReadableRows = (tushareHealthRows.length ? tushareHealthRows : recoveryActions.filter(isTushareRow)).slice(0, 8).map((row, index) => {
    const state = displayText(row.capability_state ?? row.state ?? row.status ?? row.status_label, "waiting");
    return {
      序号: index + 1,
      接口: displayText(row.api ?? row.label, "Tushare 接口"),
      当前状态: displayText(row.status_label ?? row.status ?? state, state),
      用户读法: isAvailableState(state)
        ? "可作为本地证据来源，仍需看对应结果页。"
        : isRestrictedState(state)
          ? "权限/配置受限，不能当作无数据或低风险。"
          : "按缓存、空窗口或待补处理，先保持保守。",
      下一步: displayText(row.next_action ?? row.action_label, dataCapabilityTushareNextStep),
      边界: "只读本地数据能力账本；不从页面打开触发 provider、模型或交易。"
    };
  });
  const dataCapabilityTushareResultHandoffRows = [
    {
      结果入口: "今日作战台",
      页面: "#home",
      用户看法: "确认当前股票、最近结果和 Tushare-first 是否已经回放。",
      边界: "首页输入静默；只有确认按钮才创建 Tushare-first task。"
    },
    {
      结果入口: "下一票雷达",
      页面: "#candidates/candidate-radar-search-quant-projection",
      用户看法: "确认股票代码、任务回执、call_ledger 和候选来源。",
      边界: "候选不是买入指令；链接只切换本地页面。"
    },
    {
      结果入口: "股票量化推演",
      页面: "#factor",
      用户看法: "用已回放的数据看支持/压制、P2 三面和 P3 结论。",
      边界: "Factor 页 GET cache 只读，不补调 Tushare/DeepSeek。"
    },
    {
      结果入口: "次日图谱",
      页面: "#next",
      用户看法: "用同一条确认链看路径、参考线和 operation_zones。",
      边界: "operation_zones 只是条件区间，不是交易动作。"
    }
  ];

  const providerRows = providerCards.map((card) => ({
    provider: card.provider,
    tone: card.tone,
    summary: card.summary,
    available_count: card.available_count,
    restricted_count: card.restricted_count,
    pending_count: card.pending_count
  }));

  const actionRows = recoveryActions.map((action) => ({
    provider: action.provider,
    label: action.label,
    api: action.api,
    state: action.state,
    action_label: action.action_label,
    writes_packet: action.writes_packet,
    toolbox_entry: action.toolbox_entry
  }));

  return (
    <>
      <div className="page-head">
        <h1>数据能力</h1>
        <StatusBadge label={String(cache.status ?? "missing")} tone={cache.status === "ready" ? "good" : "neutral"} />
      </div>

      <PacketCard title="Tushare 数据能力速读" subtitle="普通用户先看：可用、受限、待补和下一步" status={String(cache.status ?? "missing")}>
        <p className="ordinary-status-note" aria-label="data capability tushare ordinary summary" aria-live="polite">{dataCapabilityTushareSummary}</p>
        <MetricGrid items={dataCapabilityTushareOrdinaryItems} />
        <div aria-label="data capability tushare readable rows">
          <DataLineageTable rows={dataCapabilityTushareReadableRows} />
        </div>
        <div className="actions" aria-label="data capability tushare result handoff actions">
          <a href="#home" title="回今日作战台；只读查看当前标的和最近结果" aria-label="open home from data capability tushare card">今日作战台</a>
          <a href="#candidates/candidate-radar-search-quant-projection" title="切换到下一票雷达确认输入区；输入静默，确认按钮才创建任务" aria-label="open candidate radar from data capability tushare card">下一票雷达</a>
          <a href="#factor" title="切换到股票量化推演；只读 Factor cache" aria-label="open factor from data capability tushare card">股票量化推演</a>
          <a href="#next" title="切换到次日图谱；只读本地图谱 cache" aria-label="open next session from data capability tushare card">次日图谱</a>
        </div>
        <details className="developer-audit-details" aria-label="data capability tushare result handoff rows">
          <summary>这些数据去哪看结果</summary>
          <p className="risk-note">这张小表只把 Tushare 能力状态回流到普通投研入口；不提交刷新、不创建任务、不调用外部服务。</p>
          <DataLineageTable rows={dataCapabilityTushareResultHandoffRows} />
        </details>
        <p className="risk-note">这张卡只整理本地 data capability / data health cache；不会在页面打开时调用 Tushare、DeepSeek、GitHub，不会创建 task，不会把权限不足、空窗口或缓存降级解释成无风险，也不会生成买入、加仓或融资指令。</p>
      </PacketCard>

      <MetricGrid
        items={[
          { label: "available", value: counts.available as number | undefined },
          { label: "restricted", value: counts.restricted as number | undefined },
          { label: "pending", value: counts.pending as number | undefined },
          { label: "blocked", value: counts.blocked as number | undefined },
          { label: "manual", value: counts.manual as number | undefined },
          { label: "stale", value: counts.stale as number | undefined },
          { label: "cache only", value: cache.cache_only, tone: cache.cache_only === false ? "bad" : "good" },
          { label: "external calls", value: cache.external_calls_triggered === true ? "存在" : "无", tone: cache.external_calls_triggered === true ? "bad" : "good" },
          { label: "修改 action", value: cache.does_not_modify_strategy_action === false ? "可能" : "不会", tone: cache.does_not_modify_strategy_action === false ? "bad" : "good" },
          { label: "真实交易", value: cache.does_not_execute_trades === false ? "可能" : "禁止", tone: cache.does_not_execute_trades === false ? "bad" : "good" },
          { label: "cache envelope ledger", value: cacheEnvelopeLedger.length },
          { label: "cache warnings", value: cacheWarnings.length }
        ]}
      />

      <div className="grid">
        <PacketCard title="数据能力 cache" subtitle="GET /api/data-capability/cache 只读展示本地检测结果" status="cache_only">
          <p>{String(dashboard.summary ?? consolePacket.headline ?? "尚未检测数据能力；页面打开不会自动请求外部接口。")}</p>
          <p>{String(consolePacket.safe_mode_text ?? "只允许读取本地缓存；刷新必须通过按钮门控任务。")}</p>
          <p>cache API 永不外联：不 ping Tushare、AkShare、yfinance、Supabase，不调用 DeepSeek 或 GitHub。</p>
        </PacketCard>

        <PacketCard title="决策边界" subtitle="数据能力只影响证据置信度和手动恢复建议" status={String(consolePacket.decision_readiness ?? "missing")}>
          <p>readiness: {String(consolePacket.decision_readiness_label ?? "--")}</p>
          <p>short_answer: {String(consolePacket.short_answer ?? "--")}</p>
          <p>strategy action: {cache.does_not_modify_strategy_action === false ? "可能被修改" : "不会被修改"}</p>
        </PacketCard>
      </div>

      <PacketCard title="Provider 状态" subtitle="Tushare / AkShare / yfinance / Supabase 本地检测摘要" status="providers">
        <DataLineageTable rows={providerRows} />
      </PacketCard>

      <PacketCard title="接口级健康账本" subtitle="只读 rows；不会尝试恢复或探测接口" status={String(healthLedger.status ?? "missing")}>
        <DataLineageTable rows={healthRows} />
      </PacketCard>

      <div className="grid">
        <PacketCard title="手动恢复建议" subtitle="这里只展示建议；不触发刷新任务" status="manual_actions">
          <DataLineageTable rows={actionRows} />
        </PacketCard>

        <PacketCard title="API 边界" subtitle="GET cache 永不外联，POST task 才可能刷新" status="policy">
          <DataLineageTable rows={[policy]} />
        </PacketCard>
      </div>

      <PacketCard title="调用血缘" subtitle="payload 内部 local_data_capability_cache；不 ping 外部接口" status="call_ledger">
        <DataLineageTable rows={payloadCallLedger} />
      </PacketCard>

      <PacketCard title="GET data capability envelope call_ledger" subtitle="GET /api/data-capability/cache 顶层响应血缘；前端优先读取 res.call_ledger" status="lineage">
        <DataLineageTable rows={cacheEnvelopeLedger} />
      </PacketCard>

      <PacketCard title="GET data capability envelope warnings" subtitle="顶层响应提示；不包含 token/key/错误堆栈" status="warnings">
        <DataLineageTable rows={cacheWarnings.map((warning, index) => ({ index: index + 1, warning }))} />
      </PacketCard>

      <PacketCard title="原始 data capability cache payload" subtitle="调试用 JSON；不含 token/key/错误堆栈" status="safe">
        <JsonDetails title="data capability cache raw" data={cache} />
      </PacketCard>
    </>
  );
}
