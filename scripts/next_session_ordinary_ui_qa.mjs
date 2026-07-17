import { createRequire } from "node:module";

const desktopRequire = createRequire(new URL("../desktop/package.json", import.meta.url));
const { chromium } = desktopRequire("playwright");
const baseUrl = process.env.NEXT_SESSION_QA_BASE_URL || "http://127.0.0.1:4194";
const scope = "a".repeat(64);
let warningMode = false;

const chartContract = {
  contract_key: "next_session_echarts_payload",
  schema_version: "next_session_echarts_payload.v1",
  renderer: "ECharts",
  source_packet: "command_center_next_session_projection_packet",
  cache_only: true,
  external_calls_triggered: false,
  tushare_called: false,
  deepseek_called: false,
  github_called: false,
  does_not_execute_trades: true,
  frontend_computes_trade_action: false,
  does_not_modify_action: true,
  does_not_modify_operation_zones: true,
  requires_button_task_for_refresh: true,
};

function nextPacket() {
  const warnings = warningMode ? ["canonical_warning"] : [];
  const chartPayload = {
    status: "ready",
    source_packet: "command_center_next_session_projection_packet",
    symbol: "000001.SZ",
    source_task_id: "local-abc123",
    result_version: "candidate-v05-0123456789abcdef",
    candidate_scope_hash: scope,
    data_date: "2026-07-16",
    candidate_radar_v05_lineage_status: "same_packet_lineage_ready",
    is_exact_next_session_packet: true,
    uses_real_daily_close: true,
    historical_points: [
      { x: "2026-07-15", price: 10.1 },
      { x: "2026-07-16", price: 10.3 },
    ],
    scenario_series: [{
      scenario_name: "基准路径",
      trigger_condition: "观察价格与成交变化",
      points: [{ x: "T+1", price: 10.4 }],
    }],
    reference_lines: [
      { key: "support", label: "支撑参考", value: 9.9 },
      { key: "resistance", label: "压力参考", value: 10.8 },
    ],
    operation_zones: [],
    warnings,
    chart_maturity: { status: "ready" },
    interaction_readiness_audit: { status: "interaction_ready" },
    chart_contract: chartContract,
  };
  const chartSummary = {
    status: "ready",
    symbol: "000001.SZ",
    renderer: "ECharts",
    source_packet: "command_center_next_session_projection_packet",
    is_exact_next_session_packet: true,
    uses_real_daily_close: true,
    has_drawable_data: true,
    historical_point_count: 2,
    scenario_series_count: 1,
    reference_line_count: 2,
    operation_zone_count: 0,
    frontend_computes_trade_action: false,
    does_not_modify_action: true,
    does_not_modify_operation_zones: true,
    cache_only: true,
    external_calls_triggered: false,
    tushare_called: false,
    deepseek_called: false,
    github_called: false,
    does_not_execute_trades: true,
    maturity_status: "ready",
  };
  return {
    packet_key: "command_center_next_session_projection_packet",
    schema_version: "next_session_projection.v1",
    status: "ready_cache_replay",
    cache_only: true,
    read_only: true,
    external_calls_triggered: false,
    tushare_called: false,
    deepseek_called: false,
    github_called: false,
    provider_or_model_calls: false,
    does_not_execute_trades: true,
    does_not_modify_action: true,
    does_not_modify_strategy_action: true,
    does_not_modify_operation_zones: true,
    contains_secret: false,
    warnings,
    latest_confirmed_symbol: "000001.SZ",
    ordinary_result_replay_summary: {
      status: "ready_cache_replay",
      chart_ready_for_confirmed_symbol: true,
      chart_stale_for_confirmed_symbol: false,
    },
    candidate_radar_v05_lineage: {
      status: "same_packet_lineage_ready",
      candidate_task_id: "local-abc123",
      candidate_scope_hash: scope,
      candidate_result_version: "candidate-v05-0123456789abcdef",
      symbol: "000001.SZ",
      data_date: "2026-07-16",
      freshness_state: {
        state: "fresh",
        freshness_state: "fresh",
        data_date: "2026-07-16",
        expected_trade_date: "2026-07-16",
        expected_trade_date_calendar_validated: true,
      },
      research_only: true,
      no_buy: true,
      no_action: true,
      no_trade: true,
      external_calls_triggered: false,
      tushare_called: false,
      deepseek_called: false,
      github_called: false,
      does_not_modify_strategy_action: true,
      does_not_modify_operation_zones: true,
      contains_secret: false,
    },
    next_session_durable_evidence_recipe: {
      schema_version: "next_session_durable_evidence_recipe.v1",
      status: "next_session_durable_evidence_recipe_ready_production_pending",
      provider_execution_implemented: false,
      model_execution_implemented: false,
      worker_execution_implemented: false,
    },
    chart_payload: chartPayload,
    chart_summary: chartSummary,
  };
}

function taskIndex() {
  return {
    packet_key: "command_center_3_task_status_index",
    schema_version: "command_center_3_task_status_index.v1",
    mode: "cache_only",
    status: "ready",
    tasks: [],
    latest_confirmed_task_id: "local-abc123",
    latest_confirmed_symbol: "000001.SZ",
    latest_confirmed_task_status: "success",
    external_calls_triggered: false,
    tushare_called: false,
    deepseek_called: false,
    github_called: false,
    readback_external_calls_triggered: false,
    does_not_execute_trades: true,
    does_not_modify_strategy_action: true,
    warnings: [],
    policy: {
      get_tasks_cache_only: true,
      does_not_create_tasks: true,
      does_not_call_external_sources: true,
      latest_confirmed_readback_calls_external_sources: false,
      latest_confirmed_readback_creates_task: false,
      does_not_execute_trades: true,
      does_not_modify_strategy_action: true,
      contains_secret: false,
    },
  };
}

const envelope = (data) => ({ ok: true, data, error: null, call_ledger: [], warnings: [] });
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
await page.route("**/api/next-session/cache", (route) => route.fulfill({
  status: 200,
  contentType: "application/json",
  body: JSON.stringify(envelope(nextPacket())),
}));
await page.route("**/api/tasks**", (route) => route.fulfill({
  status: 200,
  contentType: "application/json",
  body: JSON.stringify(envelope(taskIndex())),
}));

try {
  await page.goto(`${baseUrl}/#next`, { waitUntil: "networkidle" });
  const ordinary = page.locator('[aria-label="next session ordinary first screen"]');
  await ordinary.waitFor({ state: "visible" });
  if (await ordinary.getAttribute("data-chart-binding-ready") !== "true") {
    throw new Error("canonical current packet did not reach ordinary chart ready state");
  }
  if (await ordinary.locator("canvas").count() !== 1) {
    throw new Error("ordinary ECharts canvas missing");
  }
  const ordinaryText = await ordinary.innerText();
  for (const banned of ["fail-closed", "strategy action", "历史 close", "LTG-", "operation_zones"]) {
    if (ordinaryText.includes(banned)) throw new Error(`engineering wording leaked: ${banned}`);
  }
  const technical = page.locator('details[aria-label="next session research and technical details"]');
  if (await technical.getAttribute("open") !== null) throw new Error("technical details opened by default");

  await page.emulateMedia({ reducedMotion: "reduce" });
  const reduced = await page.evaluate(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  if (!reduced) throw new Error("reduced motion media was not applied");

  await page.setViewportSize({ width: 390, height: 844 });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  if (overflow > 0) throw new Error(`390px layout overflowed by ${overflow}px`);

  warningMode = true;
  await page.reload({ waitUntil: "networkidle" });
  const blocked = page.locator('[aria-label="next session ordinary first screen"]');
  await blocked.waitFor({ state: "visible" });
  if (await blocked.getAttribute("data-chart-binding-ready") !== "false") {
    throw new Error("warning packet did not fail closed");
  }
  if (await blocked.locator("canvas").count() !== 0) {
    throw new Error("warning packet still rendered chart canvas");
  }

  process.stdout.write(JSON.stringify({
    status: "passed",
    canonical_ready: true,
    warning_fail_closed: true,
    desktop_width: 1440,
    mobile_width: 390,
    reduced_motion: true,
    technical_details_default_closed: true,
  }, null, 2));
} finally {
  await browser.close();
}
