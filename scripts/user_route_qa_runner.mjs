#!/usr/bin/env node
/*
 * Explicit local browser QA for ordinary Command Center 3 routes.
 *
 * This runner does not start FastAPI, Vite, providers, models, workers, or
 * trading paths. Start the local app first, then run this against 127.0.0.1.
 * Artifacts are written under .stock_ming_3/user_route_qa, which is ignored.
 */

import { createRequire } from "node:module";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

const require = createRequire(import.meta.url);

const SCHEMA_VERSION = "command_center_3_user_route_qa_result.v1";
const DEFAULT_BASE_URL = "http://127.0.0.1:5173";
const DEFAULT_API_BASE = "http://127.0.0.1:8710";
const DEFAULT_ARTIFACT_ROOT = ".stock_ming_3/user_route_qa";
const CHROMIUM_EXECUTABLE_PATH = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || "";

const QA_ROUTES = [
  { route: "#home", label: "Daily Command Center", focus: "first-card readiness, current symbol, next action, source state" },
  { route: "#candidates", label: "Candidate Radar", focus: "candidate pool, confirm button, local-only controls, no-buy boundary" },
  { route: "#marginEtf", label: "ETF / Margin", focus: "ETF row evidence, cash/leverage guardrail, degraded task reason" },
  { route: "#factor", label: "Stock Quant Projection", focus: "symbol result, factor support/suppression, provider gaps" },
  { route: "#next", label: "Next Session Map", focus: "operation zones as conditions, chart readability, no-action boundary" }
];

const QA_VIEWPORTS = [
  { name: "desktop", width: 1440, height: 900 },
  { name: "mobile", width: 390, height: 844 }
];

function parseArgs(argv) {
  const args = {
    baseUrl: DEFAULT_BASE_URL,
    apiBase: DEFAULT_API_BASE,
    artifactRoot: DEFAULT_ARTIFACT_ROOT,
    route: null,
    screenshots: true,
    json: false,
    printPlan: false
  };
  for (let index = 2; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--base-url") args.baseUrl = argv[++index] || args.baseUrl;
    else if (arg === "--api-base") args.apiBase = argv[++index] || args.apiBase;
    else if (arg === "--out") args.artifactRoot = argv[++index] || args.artifactRoot;
    else if (arg === "--route") args.route = argv[++index] || args.route;
    else if (arg === "--no-screenshots") args.screenshots = false;
    else if (arg === "--json") args.json = true;
    else if (arg === "--print-plan") args.printPlan = true;
    else if (arg === "--help") {
      console.log("Usage: node scripts/user_route_qa_runner.mjs [--base-url http://127.0.0.1:5173] [--api-base http://127.0.0.1:8710] [--out .stock_ming_3/user_route_qa] [--route #home] [--no-screenshots] [--json] [--print-plan]");
      process.exit(0);
    }
  }
  return args;
}

function selectedRoutes(args) {
  if (!args.route) return QA_ROUTES;
  const requested = args.route.startsWith("#") ? args.route : `#${args.route}`;
  const routes = QA_ROUTES.filter((route) => route.route === requested);
  if (!routes.length) throw new Error(`Unknown ordinary route: ${args.route}`);
  return routes;
}

function isLocalUrl(value) {
  try {
    const parsed = new URL(value);
    return ["127.0.0.1", "localhost", "::1", "[::1]"].includes(parsed.hostname);
  } catch {
    return false;
  }
}

function timestampId() {
  return new Date().toISOString().replace(/[:.]/g, "-");
}

function makePlan(args) {
  const routes = selectedRoutes(args);
  const qaMatrix = routes.flatMap((route) =>
    QA_VIEWPORTS.map((viewport) => ({
      route: route.route,
      label: route.label,
      viewport: viewport.name,
      width: viewport.width,
      height: viewport.height,
      url: `${args.baseUrl}/${route.route}`,
      focus: route.focus,
      visual_qa_complete: false,
      typing_silence_verified: false
    }))
  );
  return {
    schema_version: "command_center_3_user_route_qa_plan.v1",
    status: "user_route_qa_plan_ready",
    scope: "explicit_local_ordinary_route_browser_qa_plan",
    route_count: routes.length,
    viewport_count: QA_VIEWPORTS.length,
    qa_matrix_count: qaMatrix.length,
    qa_matrix: qaMatrix,
    checks: [
      "first viewport has a clear route title",
      "primary buttons and status labels do not clip",
      "audit details do not dominate the first viewport",
      "typing into visible inputs does not create a task",
      "visible editable inputs must be typed before typing silence is accepted",
      "screenshots and JSON report stay under ignored .stock_ming_3"
    ],
    base_url: args.baseUrl,
    api_base: args.apiBase,
    artifact_root: args.artifactRoot,
    local_urls_only: isLocalUrl(args.baseUrl) && isLocalUrl(args.apiBase),
    external_calls_triggered: false,
    tushare_called: false,
    deepseek_called: false,
    github_called: false,
    does_not_execute_trades: true,
    does_not_modify_strategy_action: true
  };
}

async function fetchTaskCount(apiBase) {
  const response = await fetch(`${apiBase.replace(/\/$/, "")}/api/tasks`);
  const payload = await response.json();
  const data = payload && typeof payload === "object" ? payload.data || payload : {};
  const taskCount = Number(data.task_count ?? (Array.isArray(data.tasks) ? data.tasks.length : 0));
  return Number.isFinite(taskCount) ? taskCount : 0;
}

async function inspectPage(page) {
  return page.evaluate(() => {
    const selectors = [
      "h1",
      "h2",
      "h3",
      "button",
      "a",
      "label",
      ".metric",
      ".status-badge",
      ".ordinary-status-note",
      ".risk-note",
      ".packet-card"
    ];
    const candidates = Array.from(document.querySelectorAll(selectors.join(",")));
    const isVisible = (element) => {
      const rect = element.getBoundingClientRect();
      const style = window.getComputedStyle(element);
      return rect.width > 0 && rect.height > 0 && style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity || 1) > 0.01;
    };
    const isClipped = (element) => {
      const tolerance = 4;
      return element.scrollWidth > Math.ceil(element.clientWidth) + tolerance || element.scrollHeight > Math.ceil(element.clientHeight) + tolerance;
    };
    const isEditableTextInput = (element) => {
      if (!(element instanceof HTMLInputElement) && !(element instanceof HTMLTextAreaElement)) return false;
      if (element.disabled || element.readOnly) return false;
      if (element instanceof HTMLTextAreaElement) return true;
      const type = (element.getAttribute("type") || "text").toLowerCase();
      return !["button", "checkbox", "color", "file", "hidden", "image", "radio", "range", "reset", "submit"].includes(type);
    };
    const rowFor = (element) => {
      const rect = element.getBoundingClientRect();
      return {
        tag: element.tagName.toLowerCase(),
        className: String(element.className || ""),
        text: (element.textContent || "").trim().replace(/\s+/g, " ").slice(0, 140),
        x: Math.round(rect.x),
        y: Math.round(rect.y),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
        clipped: isClipped(element),
        in_first_viewport: rect.bottom > 0 && rect.top < window.innerHeight && rect.right > 0 && rect.left < window.innerWidth
      };
    };
    const visibleRows = candidates.filter(isVisible).map(rowFor);
    const firstViewportRows = visibleRows.filter((row) => row.in_first_viewport);
    const clippedRows = firstViewportRows.filter((row) => row.clipped && row.text).slice(0, 12);
    const auditNoiseText = firstViewportRows
      .map((row) => row.text)
      .filter((text) => /审计|audit|developer|raw json|生产阻断|manifest/i.test(text));
    const disabledButtonsWithoutReason = Array.from(document.querySelectorAll("button:disabled"))
      .filter(isVisible)
      .map((button) => ({
        text: (button.textContent || "").trim().replace(/\s+/g, " ").slice(0, 80),
        title: button.getAttribute("title") || "",
        aria_label: button.getAttribute("aria-label") || ""
      }))
      .filter((button) => !button.title && !button.aria_label)
      .slice(0, 12);
    const visibleInputs = Array.from(document.querySelectorAll("input, textarea")).filter(isVisible);
    return {
      title: document.title,
      route_heading: document.querySelector("h1, h2, h3")?.textContent?.trim() || "",
      first_viewport_element_count: firstViewportRows.length,
      clipped_count: clippedRows.length,
      clipped_rows: clippedRows,
      audit_noise_count: auditNoiseText.length,
      audit_noise_text: auditNoiseText.slice(0, 8),
      disabled_buttons_without_reason_count: disabledButtonsWithoutReason.length,
      disabled_buttons_without_reason: disabledButtonsWithoutReason,
      visible_input_count: visibleInputs.length,
      editable_visible_input_count: visibleInputs.filter(isEditableTextInput).length
    };
  });
}

async function typeWithoutSubmit(page) {
  const target = await page.evaluate(() => {
    const isVisible = (element) => {
      const rect = element.getBoundingClientRect();
      const style = window.getComputedStyle(element);
      return rect.width > 0 && rect.height > 0 && style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity || 1) > 0.01;
    };
    const isEditableTextInput = (element) => {
      if (!(element instanceof HTMLInputElement) && !(element instanceof HTMLTextAreaElement)) return false;
      if (element.disabled || element.readOnly) return false;
      if (element instanceof HTMLTextAreaElement) return true;
      const type = (element.getAttribute("type") || "text").toLowerCase();
      return !["button", "checkbox", "color", "file", "hidden", "image", "radio", "range", "reset", "submit"].includes(type);
    };
    document.querySelectorAll("[data-user-route-qa-input]").forEach((element) => element.removeAttribute("data-user-route-qa-input"));
    const input = Array.from(document.querySelectorAll("input, textarea")).find((element) => isVisible(element) && isEditableTextInput(element));
    if (!input) return { found: false, selector: "", reason: "no_editable_visible_input" };
    input.setAttribute("data-user-route-qa-input", "true");
    const label = input.getAttribute("aria-label") || input.getAttribute("placeholder") || input.getAttribute("name") || input.id || input.tagName.toLowerCase();
    return { found: true, selector: label, reason: "editable_visible_input_found" };
  });
  if (!target.found) return { typed: false, selector: "", reason: target.reason };
  await page.locator("[data-user-route-qa-input='true']").first().fill("000001.SZ");
  await page.waitForTimeout(150);
  return { typed: true, selector: target.selector || "first editable visible input/textarea", reason: "typed_editable_visible_input" };
}

async function runQa(args) {
  if (!isLocalUrl(args.baseUrl) || !isLocalUrl(args.apiBase)) {
    throw new Error("base-url and api-base must be local 127.0.0.1/localhost URLs");
  }
  const { chromium } = require("playwright");
  const routes = selectedRoutes(args);
  const runId = timestampId();
  const outputDir = resolve(args.artifactRoot, runId);
  await mkdir(outputDir, { recursive: true });
  const browser = await chromium.launch({
    headless: true,
    ...(CHROMIUM_EXECUTABLE_PATH ? { executablePath: CHROMIUM_EXECUTABLE_PATH } : {})
  });
  const rows = [];
  const errors = [];
  try {
    for (const viewport of QA_VIEWPORTS) {
      const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height } });
      const page = await context.newPage();
      page.on("console", (message) => {
        if (message.type() === "error") errors.push({ viewport: viewport.name, console_error: message.text() });
      });
      page.on("pageerror", (error) => errors.push({ viewport: viewport.name, page_error: String(error.message || error) }));
      for (const route of routes) {
        const beforeTaskCount = await fetchTaskCount(args.apiBase);
        const startedAt = Date.now();
        const url = `${args.baseUrl.replace(/\/$/, "")}/${route.route}`;
        await page.goto(url, { waitUntil: "domcontentloaded", timeout: 20000 });
        await page.waitForSelector("h1, h2, h3", { state: "attached", timeout: 10000 });
        await page.waitForTimeout(800);
        const inspected = await inspectPage(page);
        const typing = await typeWithoutSubmit(page);
        const afterTaskCount = await fetchTaskCount(args.apiBase);
        const screenshotPath = resolve(outputDir, viewport.name, `${route.route.replace("#", "") || "home"}.png`);
        if (args.screenshots) {
          await mkdir(resolve(outputDir, viewport.name), { recursive: true });
          await page.screenshot({ path: screenshotPath, fullPage: false });
        }
        const elapsedMs = Date.now() - startedAt;
        const noTaskCreated = afterTaskCount === beforeTaskCount;
        const typingRequired = inspected.editable_visible_input_count > 0;
        const typingCovered = !typingRequired || typing.typed === true;
        const passed =
          Boolean(inspected.route_heading) &&
          inspected.clipped_count === 0 &&
          inspected.disabled_buttons_without_reason_count === 0 &&
          noTaskCreated &&
          typingCovered;
        rows.push({
          route: route.route,
          label: route.label,
          viewport: viewport.name,
          width: viewport.width,
          height: viewport.height,
          url,
          focus: route.focus,
          status: passed ? "passed" : "review_required",
          route_heading: inspected.route_heading,
          first_viewport_element_count: inspected.first_viewport_element_count,
          clipped_count: inspected.clipped_count,
          clipped_rows: inspected.clipped_rows,
          audit_noise_count: inspected.audit_noise_count,
          audit_noise_text: inspected.audit_noise_text,
          disabled_buttons_without_reason_count: inspected.disabled_buttons_without_reason_count,
          disabled_buttons_without_reason: inspected.disabled_buttons_without_reason,
          visible_input_count: inspected.visible_input_count,
          editable_visible_input_count: inspected.editable_visible_input_count,
          typing_required: typingRequired,
          typing_covered: typingCovered,
          typed_without_submit: typing.typed,
          typing_selector: typing.selector,
          typing_reason: typing.reason,
          task_count_before: beforeTaskCount,
          task_count_after: afterTaskCount,
          task_created_by_render_or_typing: !noTaskCreated,
          route_observed_ms: elapsedMs,
          screenshot_path: args.screenshots ? screenshotPath : null,
          visual_qa_complete: passed,
          typing_silence_verified: noTaskCreated
        });
      }
      await context.close();
    }
  } finally {
    await browser.close();
  }
  const reviewRows = rows.filter((row) => row.status !== "passed");
  const report = {
    schema_version: SCHEMA_VERSION,
    status: reviewRows.length || errors.length ? "user_route_qa_review_required" : "user_route_qa_passed",
    scope: "explicit_local_ordinary_route_browser_qa",
    run_id: runId,
    generated_at: new Date().toISOString(),
    base_url: args.baseUrl,
    api_base: args.apiBase,
    artifact_root: args.artifactRoot,
    output_dir: outputDir,
    route_count: routes.length,
    viewport_count: QA_VIEWPORTS.length,
    qa_matrix_count: rows.length,
    passed_count: rows.length - reviewRows.length,
    review_required_count: reviewRows.length,
    console_error_count: errors.length,
    visual_qa_complete: reviewRows.length === 0 && errors.length === 0,
    typing_silence_verified: rows.every((row) => row.task_created_by_render_or_typing === false && row.typing_covered === true),
    production_replacement_complete: false,
    streamlit_fallback_retirement_ready: false,
    rows,
    errors,
    cache_only: true,
    starts_no_servers: true,
    local_urls_only: true,
    screenshots_are_not_tracked: true,
    external_calls_triggered: false,
    tushare_called: false,
    deepseek_called: false,
    github_called: false,
    does_not_execute_trades: true,
    does_not_modify_strategy_action: true,
    note: "Local ordinary-route browser QA evidence. It is not provider/model evidence, not remote CI, and not Streamlit retirement proof."
  };
  const reportPath = resolve(outputDir, "user_route_qa_report.json");
  await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
  return { report, reportPath };
}

const args = parseArgs(process.argv);
if (args.printPlan) {
  console.log(JSON.stringify(makePlan(args), null, 2));
  process.exit(0);
}

try {
  const { report, reportPath } = await runQa(args);
  if (args.json) {
    console.log(JSON.stringify({ ...report, report_path: reportPath }, null, 2));
  } else {
    console.log(`user_route_qa_runner: ${report.status}`);
    console.log(`rows: ${report.qa_matrix_count}; passed: ${report.passed_count}; review_required: ${report.review_required_count}; console_errors: ${report.console_error_count}`);
    console.log(`typing_silence_verified: ${report.typing_silence_verified}`);
    console.log(`report: ${reportPath}`);
    console.log("external_calls_triggered: false; tushare_called: false; deepseek_called: false; github_called: false; does_not_execute_trades: true");
  }
  process.exit(report.status === "user_route_qa_passed" ? 0 : 1);
} catch (error) {
  const message = error && error.message ? error.message : String(error);
  console.error(`user_route_qa_runner: failed: ${message}`);
  console.error("Start local FastAPI/Vite first, set NODE_PATH to a Playwright install if needed, and set PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH to an installed Chrome/Chromium binary when Playwright browsers are not downloaded.");
  process.exit(1);
}
