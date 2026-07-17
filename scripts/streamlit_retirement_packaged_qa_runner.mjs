#!/usr/bin/env node
/*
 * Fail-closed capability gate and source inspector for LTG-10 packaged QA.
 *
 * A successful attestation requires DOM/network automation of the actual
 * packaged Tauri WebView plus a nonce response emitted by that application.
 * The current macOS runtime has no supported reliable DOM/app-attestation
 * driver, so execution stops before launch and writes no evidence.  There is
 * deliberately no public raw-report input or output path.
 */

import { createHash, createHmac, timingSafeEqual } from "node:crypto";
import { spawn } from "node:child_process";
import { createRequire } from "node:module";
import {
  closeSync,
  constants as fsConstants,
  createReadStream,
  existsSync,
  fstatSync,
  fsyncSync,
  lstatSync,
  mkdirSync,
  openSync,
  readdirSync,
  readFileSync,
  readlinkSync,
  realpathSync,
  writeFileSync
} from "node:fs";
import { basename, dirname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { crc32, inflateRawSync } from "node:zlib";

const SCRIPT_PATH = fileURLToPath(import.meta.url);
const SCRIPT_DIR = dirname(SCRIPT_PATH);
const DEFAULT_PROJECT_ROOT = resolve(SCRIPT_DIR, "..");
const RUNNER_SCHEMA = "streamlit_retirement_packaged_runner.v4";
const ATTESTATION_SCHEMA = "streamlit_retirement_packaged_runner_attestation.v7";
const APP_ATTESTATION_SCHEMA = "streamlit_retirement_packaged_app_attestation.v7";
const CHALLENGE_SCHEMA = "streamlit_retirement_packaged_runner_challenge.v6";
const NATIVE_INPUT_SCHEMA = "streamlit_retirement_packaged_native_input.v1";
const NATIVE_OUTPUT_SCHEMA = "streamlit_retirement_packaged_native_output.v2";
const MAX_NATIVE_OUTPUT_BYTES = 192 * 1024 * 1024;
const MAX_NATIVE_JSON_FRAME_BYTES = 64 * 1024 * 1024;
const MAX_NATIVE_DECOMPRESSED_JSON_BYTES = 192 * 1024 * 1024;
const OUTPUT_FRAME_MAGIC = Buffer.from("LTG10QA1", "ascii");
const OUTPUT_FRAME_CODEC = 1;
const OUTPUT_FRAME_CODEC_NAME = "gzip_deterministic_v1";
const OUTPUT_FRAME_HEADER_BYTES = 96;
const QA_IN_FLAG = "--ltg10-qa-in-fd";
const QA_OUT_FLAG = "--ltg10-qa-out-fd";
const EXPECTED_ROUTES = [
  ["home", "CommandCenterHome", "今日作战台"],
  ["candidates", "CandidateRadar", "下一票雷达"],
  ["factor", "FactorQuantHub", "股票量化推演"],
  ["next", "NextSessionMap", "次日图谱"],
  ["marginEtf", "MarginEtf", "ETF / 融资"],
  ["qmt-replay", "QmtReplayLab", "QMT 本地回放"]
];
const FORBIDDEN_ORDINARY_COMPONENT_IDS = ["LegacyTools", "AdminTools", "SystemMigration", "legacy", "admin", "system"];
const APP_RENDER_COMPONENT_ALLOWLIST = new Set(["Layout", "Suspense", "ActiveRoute"]);
const FORBIDDEN_COMPONENT_NAME_PATTERN = /(?:Legacy|Admin|System)(?:Tools|Migration|Route|Page|Panel|View|Component)?/;
const DANGEROUS_RENDER_APIS = new Set([
  "createPortal",
  "createElement",
  "createElementNS",
  "cloneElement",
  "dangerouslySetInnerHTML",
  "innerHTML",
  "outerHTML",
  "append",
  "appendChild",
  "prepend",
  "insertAdjacentElement",
  "insertAdjacentHTML",
  "replaceChildren",
  "attachShadow"
]);
const FORBIDDEN_ORDINARY_TAGS = new Set(["iframe", "object", "embed", "webview", "portal"]);
const FORBIDDEN_ORDINARY_JSX_ATTRIBUTES = new Set(["srcDoc", "dangerouslySetInnerHTML"]);
const FORBIDDEN_NATIVE_ESCAPE_PROPERTIES = new Set([
  "prototype", "constructor", "getOwnPropertyDescriptor", "getOwnPropertyDescriptors", "getPrototypeOf",
  "__lookupGetter__", "__lookupSetter__", "lookupGetter", "lookupSetter", "call", "apply", "bind",
  "serviceWorker", "register"
]);
const NETWORK_NATIVE_IDENTIFIERS = new Set(["fetch", "XMLHttpRequest", "WebSocket", "EventSource", "Worker", "sendBeacon"]);
const TIMER_NATIVE_IDENTIFIERS = new Set(["setTimeout", "setInterval", "requestIdleCallback"]);
const NATIVE_REALM_IDENTIFIERS = new Set(["window", "globalThis", "self", "top", "parent", "navigator", "Object", "Reflect"]);
const NEW_REALM_ESCAPE_PROPERTIES = new Set(["open", "contentWindow", "frames"]);
const FORBIDDEN_COMPUTED_NATIVE_PROPERTIES = new Set([
  ...FORBIDDEN_NATIVE_ESCAPE_PROPERTIES,
  ...NETWORK_NATIVE_IDENTIFIERS,
  ...TIMER_NATIVE_IDENTIFIERS,
  ...NEW_REALM_ESCAPE_PROPERTIES,
  "Reflect"
]);
const TRUSTED_REACHABLE_SOURCE_PATHS = [
  "desktop/src/api/client.ts",
  "desktop/src/components/BackendOfflineNotice.tsx",
  "desktop/src/components/ChartSafetyStrip.tsx",
  "desktop/src/components/DataLineageTable.tsx",
  "desktop/src/components/DeepSeekModelStrategyLedger.tsx",
  "desktop/src/components/EChartPanel.tsx",
  "desktop/src/components/JsonDetails.tsx",
  "desktop/src/components/Layout.tsx",
  "desktop/src/components/MetricGrid.tsx",
  "desktop/src/components/NextSessionChart.tsx",
  "desktop/src/components/PacketCard.tsx",
  "desktop/src/components/PageStateBanner.tsx",
  "desktop/src/components/RouteCacheLoadingBoundary.tsx",
  "desktop/src/components/StateClarityRail.tsx",
  "desktop/src/components/StatusBadge.tsx",
  "desktop/src/components/TaskBoundarySummary.tsx",
  "desktop/src/components/TaskLaunchReceipt.tsx",
  "desktop/src/components/TaskStatusPanel.tsx"
];
const FORBIDDEN_ORDINARY_URL_PATTERN = /(?:tauri:\/\/(?:localhost)?\/?#legacy|https?:\/\/(?:127\.0\.0\.1|localhost|\[::1\]):8501(?:\/|$))/i;
const ORDINARY_COMPONENT_IMPORT_ALLOWLIST = {
  CommandCenterHome: new Set([
    "react",
    "../api/client",
    "../components/DataLineageTable",
    "../components/JsonDetails",
    "../components/MetricGrid",
    "../components/PacketCard",
    "../components/PageStateBanner",
    "../components/RouteCacheLoadingBoundary",
    "../components/StatusBadge",
    "../components/TaskLaunchReceipt",
    "../components/TaskStatusPanel"
  ]),
  CandidateRadar: new Set([
    "react",
    "../api/client",
    "../components/DataLineageTable",
    "../components/JsonDetails",
    "../components/MetricGrid",
    "../components/PacketCard",
    "../components/PageStateBanner",
    "../components/RouteCacheLoadingBoundary",
    "../components/StateClarityRail",
    "../components/StatusBadge",
    "../components/TaskLaunchReceipt",
    "../components/TaskStatusPanel"
  ]),
  FactorQuantHub: new Set([
    "react",
    "echarts",
    "../api/client",
    "../components/ChartSafetyStrip",
    "../components/DataLineageTable",
    "../components/EChartPanel",
    "../components/JsonDetails",
    "../components/MetricGrid",
    "../components/PacketCard",
    "../components/StateClarityRail",
    "../components/TaskLaunchReceipt",
    "../components/TaskStatusPanel"
  ]),
  NextSessionMap: new Set([
    "react",
    "../api/client",
    "../components/DataLineageTable",
    "../components/JsonDetails",
    "../components/MetricGrid",
    "../components/NextSessionChart",
    "../components/PacketCard",
    "../components/RouteCacheLoadingBoundary",
    "../components/StateClarityRail",
    "../components/TaskLaunchReceipt",
    "../components/TaskStatusPanel"
  ]),
  MarginEtf: new Set([
    "react",
    "../api/client",
    "../components/DataLineageTable",
    "../components/MetricGrid",
    "../components/PacketCard",
    "../components/TaskLaunchReceipt",
    "../components/TaskStatusPanel"
  ]),
  QmtReplayLab: new Set([
    "react",
    "../api/client",
    "../components/DataLineageTable",
    "../components/MetricGrid",
    "../components/PacketCard",
    "../components/PageStateBanner",
    "../components/StatusBadge",
    "../components/TaskLaunchReceipt",
    "../components/TaskStatusPanel"
  ])
};
const VIEWPORTS = [
  { name: "desktop", width: 1440, height: 820 },
  { name: "mobile", width: 390, height: 844 }
];
const EXPECTED_IMPORT_MANIFEST_DIGEST = "2136c935ff75b56ca26fc8ad48285afdcb3846d7cf8659f6e3feb9c6bb8e0df8";

function sha256(data) {
  return createHash("sha256").update(data).digest("hex");
}

function hmac256(key, value) {
  return createHmac("sha256", key).update(value).digest("hex");
}

function validSha(value) {
  return typeof value === "string" && /^[0-9a-f]{64}$/.test(value);
}

function validHead(value) {
  return typeof value === "string" && /^[0-9a-f]{40}$/.test(value);
}

function sameText(left, right) {
  const a = Buffer.from(String(left));
  const b = Buffer.from(String(right));
  return a.length === b.length && timingSafeEqual(a, b);
}

function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonical(value[key])]));
  }
  return value;
}

function digest(value) {
  return sha256(JSON.stringify(canonical(value)));
}

function fixedPathReady(projectRoot, path, kind) {
  if (lstatSync(projectRoot).isSymbolicLink() || realpathSync(projectRoot) !== projectRoot) return false;
  const rel = relative(projectRoot, path);
  if (!rel || rel === ".." || rel.startsWith(`..${sep}`) || resolve(projectRoot, rel) !== path) return false;
  let cursor = projectRoot;
  for (const part of rel.split(sep)) {
    cursor = join(cursor, part);
    const metadata = lstatSync(cursor);
    if (metadata.isSymbolicLink()) return false;
  }
  const metadata = lstatSync(path);
  return kind === "directory" ? metadata.isDirectory() : metadata.isFile();
}

function bundleFingerprint(bundlePath) {
  const entries = [];
  const visit = (directory) => {
    for (const name of readdirSync(directory).sort()) {
      const path = join(directory, name);
      const rel = relative(bundlePath, path).split(sep).join("/");
      const metadata = lstatSync(path);
      entries.push({ path, rel, metadata });
      if (metadata.isDirectory() && !metadata.isSymbolicLink()) visit(path);
    }
  };
  visit(bundlePath);
  entries.sort((left, right) => left.rel < right.rel ? -1 : left.rel > right.rel ? 1 : 0);
  const hash = createHash("sha256");
  let fileCount = 0;
  for (const entry of entries) {
    const relativeBytes = Buffer.from(entry.rel);
    const length = Buffer.alloc(4);
    length.writeUInt32BE(relativeBytes.length);
    hash.update(length).update(relativeBytes);
    if (entry.metadata.isSymbolicLink()) {
      hash.update("L").update(Buffer.from(readlinkSync(entry.path)));
    } else if (!entry.metadata.isFile()) {
      hash.update("D");
    } else {
      hash.update("F").update(readFileSync(entry.path));
      fileCount += 1;
    }
  }
  return fileCount > 0 ? hash.digest("hex") : "";
}

function canonicalArtifactSet(bundleSha, dmgSha, bundleIdentifier, bundleVersion) {
  return sha256([bundleSha, dmgSha, bundleIdentifier, bundleVersion].join("|"));
}

function parseArgs(argv) {
  const args = {
    projectRoot: DEFAULT_PROJECT_ROOT,
    mode: "execute",
    json: false,
    challengeFile: "",
    nonceFd: -1,
    appInReadFd: -1,
    appInWriteFd: -1,
    appOutReadFd: -1,
    appOutWriteFd: -1
  };
  for (let index = 2; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--project-root") args.projectRoot = resolve(argv[++index] || args.projectRoot);
    else if (arg === "--print-plan") args.mode = "plan";
    else if (arg === "--print-capability") args.mode = "capability";
    else if (arg === "--inspect-source") args.mode = "source";
    else if (arg === "--trusted-session") args.mode = "trusted-session";
    else if (arg === "--challenge-file") args.challengeFile = resolve(argv[++index] || "");
    else if (arg === "--nonce-fd") args.nonceFd = Number.parseInt(argv[++index] || "-1", 10);
    else if (arg === "--app-in-read-fd") args.appInReadFd = Number.parseInt(argv[++index] || "-1", 10);
    else if (arg === "--app-in-write-fd") args.appInWriteFd = Number.parseInt(argv[++index] || "-1", 10);
    else if (arg === "--app-out-read-fd") args.appOutReadFd = Number.parseInt(argv[++index] || "-1", 10);
    else if (arg === "--app-out-write-fd") args.appOutWriteFd = Number.parseInt(argv[++index] || "-1", 10);
    else if (arg === "--json") args.json = true;
    else if (arg === "--help") {
      process.stdout.write(
        "Usage: node scripts/streamlit_retirement_packaged_qa_runner.mjs " +
          "[--print-plan|--print-capability|--inspect-source] [--project-root PATH] [--json]\n" +
          "The private --trusted-session mode is recorder-owned and accepts its nonce only by inherited fd.\n"
      );
      process.exit(0);
    } else {
      throw new Error(`unknown argument: ${arg}`);
    }
  }
  return args;
}

function runnerHash(projectRoot) {
  const path = resolve(projectRoot, "scripts/streamlit_retirement_packaged_qa_runner.mjs");
  return sha256(readFileSync(path));
}

function capability(projectRoot) {
  const appPath = resolve(
    projectRoot,
    "desktop/src-tauri/target/release/bundle/macos/stock-MING Command Center.app"
  );
  const darwin = process.platform === "darwin";
  const adapterPath = resolve(projectRoot, "desktop/src-tauri/src/ltg10_packaged_qa.rs");
  const initPath = resolve(projectRoot, "desktop/src-tauri/src/ltg10_packaged_qa_init.js");
  const adapterReady = existsSync(adapterPath) && existsSync(initPath) && [
    "eval_with_callback",
    "set_size",
    "with_webview",
    "takeSnapshotWithConfiguration_completionHandler",
    "append_invoke_initialization_script"
  ].every((token) => `${readFileSync(adapterPath, "utf8")}\n${readFileSync(resolve(projectRoot, "desktop/src-tauri/src/main.rs"), "utf8")}`.includes(token));
  const blockers = [];
  if (!darwin) blockers.push("native_packaged_tauri_adapter_requires_macos");
  if (!adapterReady) blockers.push("native_packaged_tauri_adapter_source_incomplete");
  if (!existsSync(appPath)) blockers.push("packaged_tauri_app_missing");
  const ready = darwin && adapterReady && existsSync(appPath);
  return {
    schema_version: RUNNER_SCHEMA,
    status: ready ? "packaged_tauri_nonce_attestation_capable" : "packaged_tauri_dom_capability_blocked",
    mode: "capability_preflight_no_launch",
    platform: process.platform,
    packaged_app_present: existsSync(appPath),
    packaged_dom_driver_supported: ready,
    actual_packaged_tauri_launch_allowed: ready,
    production_nonce_attestation_supported: ready,
    challenge_transport: "inherited_fd_and_private_0700_session",
    public_raw_report_accepted: false,
    writes_evidence: false,
    creates_trust_key: false,
    starts_servers: false,
    opens_browser: false,
    runtime_surface_required: "actual_packaged_tauri_react",
    vite_or_browser_substitute_allowed: false,
    runner_source_sha256: runnerHash(projectRoot),
    blockers,
    external_calls_triggered: false,
    does_not_execute_trades: true
  };
}

function plan(projectRoot) {
  const rows = EXPECTED_ROUTES.flatMap(([route, component, expectedHeading]) =>
    VIEWPORTS.map((viewport) => ({
      route: `#${route}`,
      component,
      expected_heading: expectedHeading,
      viewport: viewport.name,
      width: viewport.width,
      height: viewport.height,
      runtime_surface: "actual_packaged_tauri_react",
      protocol: "tauri:",
      required_observations: [
        "raw_dom_ledger_from_packaged_webview",
        "route_heading_and_active_route_attributes",
        "actual_component_root_identity_matches_route_contract",
        "legacy_and_streamlit_not_active",
        "complete_body_dom_inventory_has_no_admin_system_or_portal_surface",
        "component_root_is_contained_by_root_and_no_visible_non_root_surface_exists",
        "task_post_count_before_and_after_absolute_zero",
        "complete_timestamped_local_network_ledger_no_post",
        "document_start_pending_request_and_quiet_window_seal",
        "no_frame_shadow_custom_element_or_dynamic_surface",
        "measured_inner_viewport_dpr_and_native_png_scale",
        "runner_owned_single_fd_png_screenshot",
        "packaged_app_nonce_attestation"
      ]
    }))
  );
  return {
    schema_version: RUNNER_SCHEMA,
    attestation_schema_version: ATTESTATION_SCHEMA,
    status: "packaged_tauri_ordinary_flow_plan_ready_capability_pending",
    mode: "read_only_plan_no_launch",
    route_count: EXPECTED_ROUTES.length,
    viewport_count: VIEWPORTS.length,
    qa_matrix_count: rows.length,
    rows,
    evidence_transport: "recorder_private_one_shot_session_only",
    public_raw_report_accepted: false,
    runner_source_sha256: runnerHash(projectRoot),
    runtime_surface_required: "actual_packaged_tauri_react",
    vite_or_browser_substitute_allowed: false,
    writes_evidence: false,
    creates_trust_key: false,
    starts_servers: false,
    opens_browser: false,
    external_calls_triggered: false,
    does_not_execute_trades: true
  };
}

function loadTypescript(projectRoot) {
  const packageJson = resolve(projectRoot, "desktop/package.json");
  const candidates = [createRequire(packageJson)];
  const explicitModules = process.env.STOCK_MING_DESKTOP_NODE_MODULES;
  if (explicitModules) candidates.push(createRequire(resolve(explicitModules, "package.json")));
  for (const candidate of candidates) {
    try {
      return candidate("typescript");
    } catch {
      // Try the next explicitly scoped package root.
    }
  }
  throw new Error("typescript compiler API unavailable; source contract fails closed");
}

function propertyName(ts, node) {
  if (!node) return "";
  if (ts.isIdentifier(node) || ts.isStringLiteral(node) || ts.isNumericLiteral(node)) return node.text;
  return "";
}

function unwrap(ts, node) {
  let value = node;
  while (
    value &&
    (ts.isAsExpression(value) ||
      ts.isSatisfiesExpression(value) ||
      ts.isParenthesizedExpression(value) ||
      ts.isTypeAssertionExpression(value))
  ) {
    value = value.expression;
  }
  return value;
}

function variableInitializer(ts, sourceFile, name) {
  for (const statement of sourceFile.statements) {
    if (!ts.isVariableStatement(statement)) continue;
    for (const declaration of statement.declarationList.declarations) {
      if (ts.isIdentifier(declaration.name) && declaration.name.text === name) {
        return unwrap(ts, declaration.initializer);
      }
    }
  }
  return null;
}

function objectProperties(ts, node) {
  const value = unwrap(ts, node);
  if (!value || !ts.isObjectLiteralExpression(value)) return null;
  const result = new Map();
  for (const property of value.properties) {
    if (!ts.isPropertyAssignment(property)) return null;
    const name = propertyName(ts, property.name);
    if (!name || result.has(name)) return null;
    result.set(name, unwrap(ts, property.initializer));
  }
  return result;
}

function stringValue(ts, node) {
  const value = unwrap(ts, node);
  return value && (ts.isStringLiteral(value) || ts.isNoSubstitutionTemplateLiteral(value))
    ? value.text
    : null;
}

function constantStringValue(ts, node, bindings = new Map(), visiting = new Set()) {
  const value = unwrap(ts, node);
  if (!value) return null;
  if (ts.isStringLiteral(value) || ts.isNoSubstitutionTemplateLiteral(value)) return value.text;
  if (ts.isIdentifier(value) && bindings.has(value.text) && !visiting.has(value.text)) {
    const nextVisiting = new Set(visiting);
    nextVisiting.add(value.text);
    return constantStringValue(ts, bindings.get(value.text), bindings, nextVisiting);
  }
  if (ts.isBinaryExpression(value) && value.operatorToken.kind === ts.SyntaxKind.PlusToken) {
    const left = constantStringValue(ts, value.left, bindings, visiting);
    const right = constantStringValue(ts, value.right, bindings, visiting);
    return left === null || right === null ? null : `${left}${right}`;
  }
  if (ts.isTemplateExpression(value)) {
    let result = value.head.text;
    for (const span of value.templateSpans) {
      const expression = constantStringValue(ts, span.expression, bindings, visiting);
      if (expression === null) return null;
      result += expression + span.literal.text;
    }
    return result;
  }
  return null;
}

function constantStringBindings(ts, sourceFile) {
  const candidates = new Map();
  const bindingCounts = new Map();
  const noteBinding = (name) => {
    if (name) bindingCounts.set(name, (bindingCounts.get(name) || 0) + 1);
  };
  const visit = (node) => {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name)) {
      noteBinding(node.name.text);
      const declarationList = node.parent;
      const isConst = ts.isVariableDeclarationList(declarationList) &&
        (declarationList.flags & ts.NodeFlags.Const) !== 0;
      if (isConst && node.initializer && !candidates.has(node.name.text)) {
        candidates.set(node.name.text, node.initializer);
      }
    } else if (
      (ts.isParameter(node) || ts.isBindingElement(node)) &&
      ts.isIdentifier(node.name)
    ) {
      noteBinding(node.name.text);
    } else if (
      (ts.isFunctionDeclaration(node) || ts.isClassDeclaration(node)) &&
      node.name
    ) {
      noteBinding(node.name.text);
    } else if (ts.isImportClause(node) && node.name) {
      noteBinding(node.name.text);
    } else if (ts.isImportSpecifier(node)) {
      noteBinding(node.name.text);
    } else if (ts.isNamespaceImport(node)) {
      noteBinding(node.name.text);
    }
    ts.forEachChild(node, visit);
  };
  visit(sourceFile);
  for (const name of candidates.keys()) {
    if (bindingCounts.get(name) !== 1) candidates.delete(name);
  }
  return candidates;
}

function dangerousNativeReceiverAliases(ts, sourceFile) {
  const aliases = new Set(NATIVE_REALM_IDENTIFIERS);
  const stringBindings = constantStringBindings(ts, sourceFile);
  const declarations = [];
  const visit = (node) => {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer) {
      declarations.push({ name: node.name.text, initializer: node.initializer });
    } else if (
      ts.isBinaryExpression(node) &&
      node.operatorToken.kind === ts.SyntaxKind.EqualsToken &&
      ts.isIdentifier(unwrap(ts, node.left))
    ) {
      declarations.push({ name: unwrap(ts, node.left).text, initializer: node.right });
    }
    ts.forEachChild(node, visit);
  };
  visit(sourceFile);
  const isDangerousReceiver = (node) => {
    const value = unwrap(ts, node);
    if (ts.isIdentifier(value)) return aliases.has(value.text);
    if (ts.isPropertyAccessExpression(value) || ts.isElementAccessExpression(value)) {
      const property = ts.isPropertyAccessExpression(value)
        ? value.name.text
        : constantStringValue(ts, value.argumentExpression, stringBindings);
      return ["contentWindow", "frames", "serviceWorker"].includes(property) || isDangerousReceiver(value.expression);
    }
    if (ts.isCallExpression(value)) {
      const callee = unwrap(ts, value.expression);
      if (ts.isPropertyAccessExpression(callee) || ts.isElementAccessExpression(callee)) {
        const property = ts.isPropertyAccessExpression(callee)
          ? callee.name.text
          : constantStringValue(ts, callee.argumentExpression, stringBindings);
        return property === "open" && isDangerousReceiver(callee.expression);
      }
    }
    return false;
  };
  let changed = true;
  while (changed) {
    changed = false;
    for (const declaration of declarations) {
      if (!aliases.has(declaration.name) && isDangerousReceiver(declaration.initializer)) {
        aliases.add(declaration.name);
        changed = true;
      }
    }
  }
  return { aliases, isDangerousReceiver };
}

function booleanValue(ts, node) {
  const value = unwrap(ts, node);
  if (value?.kind === ts.SyntaxKind.TrueKeyword) return true;
  if (value?.kind === ts.SyntaxKind.FalseKeyword) return false;
  return null;
}

function arrayValue(ts, node) {
  const value = unwrap(ts, node);
  return value && ts.isArrayLiteralExpression(value) ? value.elements : null;
}

function parseRouteGroups(ts, sourceFile) {
  const elements = arrayValue(ts, variableInitializer(ts, sourceFile, "ROUTE_GROUPS"));
  if (!elements) return null;
  const groups = [];
  for (const element of elements) {
    const properties = objectProperties(ts, element);
    if (!properties) return null;
    const title = stringValue(ts, properties.get("title"));
    const primary = properties.has("primary") ? booleanValue(ts, properties.get("primary")) : false;
    const routeElements = arrayValue(ts, properties.get("routes"));
    if (title === null || primary === null || !routeElements) return null;
    const routes = [];
    for (const routeElement of routeElements) {
      const route = objectProperties(ts, routeElement);
      if (!route || route.size !== 2) return null;
      const key = stringValue(ts, route.get("key"));
      const label = stringValue(ts, route.get("label"));
      if (key === null || label === null) return null;
      routes.push({ key, label });
    }
    groups.push({ title, primary, routes });
  }
  return groups;
}

function parseComponentMap(ts, sourceFile) {
  const properties = objectProperties(ts, variableInitializer(ts, sourceFile, "ROUTE_COMPONENTS"));
  if (!properties) return null;
  return Object.fromEntries(
    [...properties.entries()].map(([key, value]) => [
      key,
      ts.isIdentifier(unwrap(ts, value)) ? unwrap(ts, value).text : ""
    ])
  );
}

function parseRouteKeys(ts, sourceFile) {
  const elements = arrayValue(ts, variableInitializer(ts, sourceFile, "ROUTE_KEYS"));
  if (!elements) return null;
  const values = elements.map((element) => stringValue(ts, element));
  return values.every((value) => value !== null) ? values : null;
}

function parsesTauriDefaultHome(ts, sourceFile) {
  const declaration = sourceFile.statements.find(
    (statement) => ts.isFunctionDeclaration(statement) && statement.name?.text === "readInitialRoute"
  );
  if (!declaration?.body) return false;
  return declaration.body.statements.some((statement) => {
    if (!ts.isIfStatement(statement)) return false;
    const expression = unwrap(ts, statement.expression);
    const thenStatement = statement.thenStatement;
    const callReady =
      ts.isCallExpression(expression) &&
      ts.isIdentifier(expression.expression) &&
      expression.expression.text === "isTauriRuntime" &&
      expression.arguments.length === 0;
    const returned = ts.isReturnStatement(thenStatement)
      ? stringValue(ts, thenStatement.expression)
      : ts.isBlock(thenStatement) && thenStatement.statements.length === 1 && ts.isReturnStatement(thenStatement.statements[0])
      ? stringValue(ts, thenStatement.statements[0].expression)
      : null;
    return callReady && returned === "home";
  });
}

function lazyImportPath(ts, node) {
  const value = unwrap(ts, node);
  if (!value || !ts.isCallExpression(value) || !ts.isIdentifier(value.expression) || value.expression.text !== "lazy") return null;
  if (value.arguments.length !== 1) return null;
  const factory = unwrap(ts, value.arguments[0]);
  if (!factory || (!ts.isArrowFunction(factory) && !ts.isFunctionExpression(factory))) return null;
  const body = unwrap(ts, factory.body);
  if (!body || !ts.isCallExpression(body) || body.expression.kind !== ts.SyntaxKind.ImportKeyword || body.arguments.length !== 1) return null;
  return stringValue(ts, body.arguments[0]);
}

function lazyRouteImports(ts, sourceFile) {
  const result = new Map();
  for (const statement of sourceFile.statements) {
    if (!ts.isVariableStatement(statement)) continue;
    for (const declaration of statement.declarationList.declarations) {
      if (!ts.isIdentifier(declaration.name)) continue;
      const path = lazyImportPath(ts, declaration.initializer);
      if (path !== null) result.set(declaration.name.text, path);
    }
  }
  return result;
}

function hasModifier(ts, node, kind) {
  return Boolean(node.modifiers?.some((modifier) => modifier.kind === kind));
}

function defaultExportedFunction(ts, sourceFile, expectedName) {
  const matches = sourceFile.statements.filter(
    (statement) =>
      ts.isFunctionDeclaration(statement) &&
      statement.name?.text === expectedName &&
      hasModifier(ts, statement, ts.SyntaxKind.ExportKeyword) &&
      hasModifier(ts, statement, ts.SyntaxKind.DefaultKeyword)
  );
  return matches.length === 1 ? matches[0] : null;
}

function exactIdentifierJsxTag(ts, tagName) {
  return ts.isIdentifier(tagName) ? tagName.text : "";
}

function exactKeyRouteAttribute(ts, attributes) {
  if (attributes.properties.length !== 1) return false;
  const attribute = attributes.properties[0];
  if (!ts.isJsxAttribute(attribute) || propertyName(ts, attribute.name) !== "key") return false;
  if (!attribute.initializer || !ts.isJsxExpression(attribute.initializer)) return false;
  const expression = unwrap(ts, attribute.initializer.expression);
  return Boolean(expression && ts.isIdentifier(expression) && expression.text === "route");
}

function nodeContainsIdentifier(ts, node, identifier) {
  let found = false;
  const visit = (current) => {
    if (ts.isIdentifier(current) && current.text === identifier) found = true;
    if (!found) ts.forEachChild(current, visit);
  };
  visit(node);
  return found;
}

function activeRouteBindingIsExact(ts, sourceFile) {
  const app = defaultExportedFunction(ts, sourceFile, "App");
  if (!app?.body) return false;
  const declarations = [];
  const routeComponentAccesses = [];
  const activeRouteJsx = [];
  const appComponentTags = [];
  const visit = (node) => {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.name.text === "ActiveRoute") {
      declarations.push(node);
    }
    if (
      (ts.isElementAccessExpression(node) || ts.isPropertyAccessExpression(node)) &&
      ts.isIdentifier(unwrap(ts, node.expression)) &&
      unwrap(ts, node.expression).text === "ROUTE_COMPONENTS"
    ) {
      routeComponentAccesses.push(node);
    }
    ts.forEachChild(node, visit);
  };
  visit(sourceFile);
  if (declarations.length !== 1) return false;
  const declaration = declarations[0];
  const declarationList = declaration.parent;
  const declarationStatement = declarationList?.parent;
  const initializer = unwrap(ts, declaration.initializer);
  const exactDeclaration = Boolean(
    declarationList &&
      ts.isVariableDeclarationList(declarationList) &&
      (declarationList.flags & ts.NodeFlags.Const) !== 0 &&
      declarationList.declarations.length === 1 &&
      declarationStatement &&
      ts.isVariableStatement(declarationStatement) &&
      declarationStatement.parent === app.body &&
    initializer &&
      ts.isElementAccessExpression(initializer) &&
      !initializer.questionDotToken &&
      ts.isIdentifier(unwrap(ts, initializer.expression)) &&
      unwrap(ts, initializer.expression).text === "ROUTE_COMPONENTS" &&
      ts.isIdentifier(unwrap(ts, initializer.argumentExpression)) &&
      unwrap(ts, initializer.argumentExpression).text === "route"
  );
  if (!exactDeclaration || routeComponentAccesses.length !== 1 || routeComponentAccesses[0] !== initializer) return false;

  const inspectApp = (node) => {
    if (ts.isJsxSelfClosingElement(node) || ts.isJsxOpeningElement(node)) {
      const tag = exactIdentifierJsxTag(ts, node.tagName);
      if (tag && /^[A-Z]/.test(tag)) appComponentTags.push(tag);
      if (tag === "ActiveRoute") activeRouteJsx.push(node);
    }
    ts.forEachChild(node, inspectApp);
  };
  inspectApp(app.body);
  if (
    activeRouteJsx.length !== 1 ||
    !ts.isJsxSelfClosingElement(activeRouteJsx[0]) ||
    !exactKeyRouteAttribute(ts, activeRouteJsx[0].attributes) ||
    appComponentTags.some((tag) => !APP_RENDER_COMPONENT_ALLOWLIST.has(tag)) ||
    identifierReferenceCount(ts, sourceFile, "ActiveRoute") !== 2 ||
    identifierReferenceCount(ts, sourceFile, "ROUTE_COMPONENTS") !== 2
  ) {
    return false;
  }
  for (let parent = activeRouteJsx[0].parent; parent && parent !== app.body; parent = parent.parent) {
    if (
      ts.isConditionalExpression(parent) ||
      ts.isIfStatement(parent) ||
      ts.isSwitchStatement(parent) ||
      (ts.isBinaryExpression(parent) && [
        ts.SyntaxKind.AmpersandAmpersandToken,
        ts.SyntaxKind.BarBarToken,
        ts.SyntaxKind.QuestionQuestionToken
      ].includes(parent.operatorToken.kind))
    ) {
      return false;
    }
  }
  let assigned = false;
  const findWrites = (node) => {
    if (
      (ts.isBinaryExpression(node) && nodeContainsIdentifier(ts, node.left, "ActiveRoute") &&
        node.operatorToken.kind >= ts.SyntaxKind.FirstAssignment &&
        node.operatorToken.kind <= ts.SyntaxKind.LastAssignment) ||
      ((ts.isPrefixUnaryExpression(node) || ts.isPostfixUnaryExpression(node)) &&
        nodeContainsIdentifier(ts, node.operand, "ActiveRoute"))
    ) {
      assigned = true;
    }
    ts.forEachChild(node, findWrites);
  };
  findWrites(sourceFile);
  return !assigned;
}

function importContract(ts, sourceFile, expectedComponent) {
  const allowedSources = ORDINARY_COMPONENT_IMPORT_ALLOWLIST[expectedComponent];
  if (!allowedSources) return null;
  const observedSources = [];
  const bindings = new Set();
  const manifest = [];
  let unsafe = false;
  for (const statement of sourceFile.statements) {
    if (!ts.isImportDeclaration(statement)) continue;
    const source = stringValue(ts, statement.moduleSpecifier);
    if (source === null) return null;
    observedSources.push(source);
    const clause = statement.importClause;
    if (!clause || statement.assertClause || statement.attributes) {
      unsafe = true;
      continue;
    }
    const declaration = {
      specifier: source,
      declaration_kind: clause.isTypeOnly ? "type" : "value",
      default_local: clause.name?.text || "",
      namespace_local: "",
      named: []
    };
    if (clause.name) {
      if (bindings.has(clause.name.text)) unsafe = true;
      bindings.add(clause.name.text);
      if (
        DANGEROUS_RENDER_APIS.has(clause.name.text) ||
        (/^[A-Z]/.test(clause.name.text) && FORBIDDEN_COMPONENT_NAME_PATTERN.test(clause.name.text))
      ) {
        unsafe = true;
      }
    }
    const named = clause.namedBindings;
    if (named && ts.isNamespaceImport(named)) {
      declaration.namespace_local = named.name.text;
      if (bindings.has(named.name.text)) unsafe = true;
      bindings.add(named.name.text);
      unsafe = true;
    } else if (named && ts.isNamedImports(named)) {
      for (const element of named.elements) {
        const imported = (element.propertyName || element.name).text;
        const local = element.name.text;
        declaration.named.push({
          imported,
          local,
          kind: clause.isTypeOnly || element.isTypeOnly ? "type" : "value"
        });
        if (bindings.has(local)) unsafe = true;
        bindings.add(local);
        if (
          DANGEROUS_RENDER_APIS.has(imported) ||
          DANGEROUS_RENDER_APIS.has(local) ||
          (/^[A-Z]/.test(imported) && FORBIDDEN_COMPONENT_NAME_PATTERN.test(imported)) ||
          (/^[A-Z]/.test(local) && FORBIDDEN_COMPONENT_NAME_PATTERN.test(local))
        ) {
          unsafe = true;
        }
      }
    }
    manifest.push(declaration);
    if (/react-dom|(?:^|\/)(?:legacy|admin|system)(?:\/|$)/i.test(source)) unsafe = true;
    if (source.startsWith(".") && !source.startsWith("../api/") && !source.startsWith("../components/")) unsafe = true;
    if (!source.startsWith(".") && !["react", "echarts"].includes(source)) unsafe = true;
  }
  const sourceCounts = observedSources.reduce((counts, source) => counts.set(source, (counts.get(source) || 0) + 1), new Map());
  if ([...sourceCounts].some(([source, count]) => count > 1 && (source !== "../api/client" || count !== 2))) unsafe = true;
  if (
    unsafe ||
    new Set(observedSources).size !== allowedSources.size ||
    observedSources.some((source) => !allowedSources.has(source)) ||
    [...allowedSources].some((source) => !observedSources.includes(source))
  ) {
    return null;
  }
  return { bindings, manifest };
}

function componentOwnedReturns(ts, component) {
  const returns = [];
  const visit = (node) => {
    if (
      node !== component.body &&
      (ts.isFunctionDeclaration(node) ||
        ts.isFunctionExpression(node) ||
        ts.isArrowFunction(node) ||
        ts.isMethodDeclaration(node) ||
        ts.isGetAccessorDeclaration(node) ||
        ts.isSetAccessorDeclaration(node))
    ) {
      return;
    }
    if (ts.isReturnStatement(node)) returns.push(node);
    ts.forEachChild(node, visit);
  };
  visit(component.body);
  return returns;
}

function ordinaryComponentTreeIsClosed(ts, sourceFile, component, importedBindings) {
  let unsafe = false;
  const importedComponentBindings = new Set([...importedBindings].filter((name) => /^[A-Z]/.test(name)));
  const bindingNames = (name, output = []) => {
    if (!name) return output;
    if (ts.isIdentifier(name)) output.push(name.text);
    else if (ts.isObjectBindingPattern(name) || ts.isArrayBindingPattern(name)) {
      for (const element of name.elements) {
        if (ts.isBindingElement(element)) bindingNames(element.name, output);
      }
    }
    return output;
  };
  const visit = (node) => {
    if (
      (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) &&
      FORBIDDEN_ORDINARY_URL_PATTERN.test(node.text)
    ) {
      unsafe = true;
    }
    if (
      (ts.isVariableDeclaration(node) || ts.isParameter(node) || ts.isBindingElement(node)) &&
      bindingNames(node.name).some((name) => importedComponentBindings.has(name))
    ) {
      unsafe = true;
    }
    if (
      (ts.isFunctionDeclaration(node) || ts.isClassDeclaration(node)) &&
      node.name &&
      importedComponentBindings.has(node.name.text)
    ) {
      unsafe = true;
    }
    if (ts.isCallExpression(node)) {
      const expression = unwrap(ts, node.expression);
      if (
        expression?.kind === ts.SyntaxKind.ImportKeyword ||
        (ts.isIdentifier(expression) && (expression.text === "require" || DANGEROUS_RENDER_APIS.has(expression.text))) ||
        ((ts.isPropertyAccessExpression(expression) || ts.isElementAccessExpression(expression)) &&
          DANGEROUS_RENDER_APIS.has(
            ts.isPropertyAccessExpression(expression)
              ? expression.name.text
              : stringValue(ts, expression.argumentExpression) || ""
          ))
      ) {
        unsafe = true;
      }
    }
    if (ts.isPropertyAccessExpression(node) && (DANGEROUS_RENDER_APIS.has(node.name.text) || node.name.text === "customElements")) unsafe = true;
    if (ts.isElementAccessExpression(node) && DANGEROUS_RENDER_APIS.has(stringValue(ts, node.argumentExpression) || "")) unsafe = true;
    if (
      (ts.isPropertyAccessExpression(node) || ts.isElementAccessExpression(node)) &&
      ts.isIdentifier(unwrap(ts, node.expression)) &&
      unwrap(ts, node.expression).text === "customElements"
    ) {
      unsafe = true;
    }
    if (
      ts.isPropertyAccessExpression(node) &&
      ts.isIdentifier(unwrap(ts, node.expression)) &&
      unwrap(ts, node.expression).text === "document" &&
      node.name.text === "body"
    ) {
      unsafe = true;
    }
    if (
      ts.isJsxAttribute(node) &&
      (DANGEROUS_RENDER_APIS.has(propertyName(ts, node.name)) || FORBIDDEN_ORDINARY_JSX_ATTRIBUTES.has(propertyName(ts, node.name)))
    ) unsafe = true;
    if (ts.isJsxSelfClosingElement(node) || ts.isJsxOpeningElement(node)) {
      const tag = exactIdentifierJsxTag(ts, node.tagName);
      if (
        !tag ||
        FORBIDDEN_ORDINARY_TAGS.has(tag.toLowerCase()) ||
        tag.includes("-") ||
        (/^[A-Z]/.test(tag) && !importedBindings.has(tag)) ||
        FORBIDDEN_COMPONENT_NAME_PATTERN.test(tag)
      ) {
        unsafe = true;
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(sourceFile);
  const returns = componentOwnedReturns(ts, component);
  return !unsafe && returns.length === 1 && returns[0].parent === component.body;
}

function trustedSourceHasNativeEscape(ts, sourceFile, { allowDirectFetch = false } = {}) {
  let unsafe = false;
  const stringBindings = constantStringBindings(ts, sourceFile);
  const { isDangerousReceiver } = dangerousNativeReceiverAliases(ts, sourceFile);
  const computedProperty = (node) => constantStringValue(ts, node.argumentExpression, stringBindings);
  const visit = (node) => {
    if (ts.isIdentifier(node) && node.text === "Reflect") unsafe = true;
    if (ts.isPropertyAccessExpression(node) || ts.isElementAccessExpression(node)) {
      const property = ts.isPropertyAccessExpression(node)
        ? node.name.text
        : computedProperty(node);
      if (
        FORBIDDEN_NATIVE_ESCAPE_PROPERTIES.has(property) ||
        NETWORK_NATIVE_IDENTIFIERS.has(property) ||
        ["contentWindow", "frames"].includes(property) ||
        (property === "open" &&
          (ts.isElementAccessExpression(node) || isDangerousReceiver(node.expression))) ||
        (ts.isElementAccessExpression(node) && FORBIDDEN_COMPUTED_NATIVE_PROPERTIES.has(property))
      ) unsafe = true;
      if (
        ts.isElementAccessExpression(node) &&
        property === null &&
        (isDangerousReceiver(node.expression) ||
          (ts.isCallExpression(node.parent) && unwrap(ts, node.parent.expression) === node))
      ) unsafe = true;
    }
    if (ts.isIdentifier(node) && NETWORK_NATIVE_IDENTIFIERS.has(node.text)) {
      const directFetch = allowDirectFetch && node.text === "fetch" && ts.isCallExpression(node.parent) && node.parent.expression === node;
      if (!directFetch) unsafe = true;
    }
    if (ts.isCallExpression(node)) {
      const expression = unwrap(ts, node.expression);
      if (ts.isIdentifier(expression) && expression.text === "open") unsafe = true;
      const timerName = ts.isPropertyAccessExpression(expression)
        ? expression.name.text
        : ts.isElementAccessExpression(expression)
          ? computedProperty(expression)
          : ts.isIdentifier(expression) ? expression.text : "";
      if (TIMER_NATIVE_IDENTIFIERS.has(timerName)) {
        const callback = node.arguments[0];
        let containsNative = false;
        if (callback) {
          const inspectCallback = (current) => {
            if (
              (ts.isIdentifier(current) && NETWORK_NATIVE_IDENTIFIERS.has(current.text)) ||
              ((ts.isPropertyAccessExpression(current) || ts.isElementAccessExpression(current)) &&
                NETWORK_NATIVE_IDENTIFIERS.has(ts.isPropertyAccessExpression(current) ? current.name.text : computedProperty(current)))
            ) containsNative = true;
            ts.forEachChild(current, inspectCallback);
          };
          inspectCallback(callback);
        }
        if (containsNative) unsafe = true;
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(sourceFile);
  return unsafe;
}

function inspectTrustedReachableSources(ts, projectRoot) {
  const hashes = {};
  const blockers = [];
  for (const relativePath of TRUSTED_REACHABLE_SOURCE_PATHS) {
    const path = resolve(projectRoot, relativePath);
    let bytes;
    try { bytes = readFileSync(path); } catch { blockers.push(`trusted_reachable_source_missing:${relativePath}`); continue; }
    const source = ts.createSourceFile(
      path,
      bytes.toString("utf8"),
      ts.ScriptTarget.Latest,
      true,
      relativePath.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS
    );
    if (trustedSourceHasNativeEscape(ts, source, { allowDirectFetch: relativePath === "desktop/src/api/client.ts" })) {
      blockers.push(`trusted_reachable_native_escape:${relativePath}`);
    }
    hashes[relativePath] = sha256(bytes);
  }
  return { hashes, blockers };
}

function componentRootIdentity(
  ts,
  projectRoot,
  importPath,
  expectedComponent,
  enforceOrdinaryTree = true,
  expectedRoute = "",
  expectedHeading = ""
) {
  if (importPath !== `./routes/${expectedComponent}`) return null;
  const componentPath = resolve(projectRoot, "desktop/src/routes", `${expectedComponent}.tsx`);
  let bytes;
  try {
    bytes = readFileSync(componentPath);
  } catch {
    return null;
  }
  const source = ts.createSourceFile(
    componentPath,
    bytes.toString("utf8"),
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX
  );
  const component = defaultExportedFunction(ts, source, expectedComponent);
  if (!component?.body) return null;
  const importResult = enforceOrdinaryTree ? importContract(ts, source, expectedComponent) : { bindings: new Set(), manifest: [] };
  if (
    enforceOrdinaryTree &&
    (!importResult || ordinaryComponentTreeIsClosed(ts, source, component, importResult.bindings) === false ||
      trustedSourceHasNativeEscape(ts, source))
  ) return null;
  const returns = enforceOrdinaryTree
    ? componentOwnedReturns(ts, component)
    : component.body.statements.filter((statement) => ts.isReturnStatement(statement));
  if (returns.length !== 1) return null;
  const root = unwrap(ts, returns[0].expression);
  if (!root || !ts.isJsxElement(root)) return null;
  const identityAttributes = [];
  const headingAttributes = [];
  const headingElements = [];
  const visit = (node) => {
    if (ts.isJsxAttribute(node) && propertyName(ts, node.name) === "data-ltg10-component-id") {
      identityAttributes.push(node);
    }
    if (ts.isJsxAttribute(node) && propertyName(ts, node.name) === "data-ltg10-route-heading") {
      headingAttributes.push(node);
      const opening = node.parent?.parent;
      if (opening && ts.isJsxOpeningElement(opening)) headingElements.push(opening.parent);
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  const rootIdentity = root.openingElement.attributes.properties.filter(
    (attribute) => ts.isJsxAttribute(attribute) && propertyName(ts, attribute.name) === "data-ltg10-component-id"
  );
  if (
    identityAttributes.length !== 1 ||
    rootIdentity.length !== 1 ||
    stringValue(ts, rootIdentity[0].initializer) !== expectedComponent
  ) {
    return null;
  }
  if (enforceOrdinaryTree) {
    const heading = headingElements.length === 1 && ts.isJsxElement(headingElements[0]) ? headingElements[0] : null;
    const tag = heading ? exactIdentifierJsxTag(ts, heading.openingElement.tagName).toLowerCase() : "";
    const headingText = heading?.children.length === 1 && ts.isJsxText(heading.children[0])
      ? heading.children[0].text.trim()
      : "";
    if (
      headingAttributes.length !== 1 ||
      !heading ||
      !["h1", "h2"].includes(tag) ||
      stringValue(ts, headingAttributes[0].initializer) !== expectedRoute ||
      headingText !== expectedHeading
    ) {
      return null;
    }
  }
  return {
    component_id: expectedComponent,
    source_sha256: sha256(bytes),
    import_manifest: importResult.manifest,
    route_heading: enforceOrdinaryTree ? expectedHeading : ""
  };
}

function identifierReferenceCount(ts, sourceFile, identifier) {
  let count = 0;
  const visit = (node) => {
    if (ts.isIdentifier(node) && node.text === identifier) count += 1;
    ts.forEachChild(node, visit);
  };
  visit(sourceFile);
  return count;
}

function normalizeRouteAliases(ts, sourceFile) {
  const declaration = sourceFile.statements.find(
    (statement) => ts.isFunctionDeclaration(statement) && statement.name?.text === "normalizeRouteKey"
  );
  if (!declaration?.body) return null;
  const aliases = [];
  const visit = (node) => {
    if (ts.isIfStatement(node)) {
      const returned = ts.isReturnStatement(node.thenStatement)
        ? stringValue(ts, node.thenStatement.expression)
        : ts.isBlock(node.thenStatement) && node.thenStatement.statements.length === 1 && ts.isReturnStatement(node.thenStatement.statements[0])
          ? stringValue(ts, node.thenStatement.statements[0].expression)
          : null;
      if (returned !== null) aliases.push(returned);
    }
    ts.forEachChild(node, visit);
  };
  visit(declaration.body);
  return aliases;
}

function inspectSource(projectRoot) {
  const ts = loadTypescript(projectRoot);
  const layoutPath = resolve(projectRoot, "desktop/src/components/Layout.tsx");
  const appPath = resolve(projectRoot, "desktop/src/App.tsx");
  const layoutBytes = readFileSync(layoutPath);
  const appBytes = readFileSync(appPath);
  const layout = ts.createSourceFile(layoutPath, layoutBytes.toString("utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const app = ts.createSourceFile(appPath, appBytes.toString("utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const groups = parseRouteGroups(ts, layout);
  const componentMap = parseComponentMap(ts, app);
  const routeKeys = parseRouteKeys(ts, app);
  const routeImports = lazyRouteImports(ts, app);
  const routeAliases = normalizeRouteAliases(ts, app);
  const activeRouteBindingVerified = activeRouteBindingIsExact(ts, app);
  const blockers = [];
  const reachable = inspectTrustedReachableSources(ts, projectRoot);
  blockers.push(...reachable.blockers);
  const ordinary = groups?.filter((group) => group.primary === true) || [];
  const ordinaryKeys = ordinary.length === 1 ? ordinary[0].routes.map((row) => row.key) : [];
  const expectedKeys = EXPECTED_ROUTES.map(([route]) => route);
  if (JSON.stringify(ordinaryKeys) !== JSON.stringify(expectedKeys)) blockers.push("ordinary_route_allowlist_not_exact");
  if (ordinary.length !== 1 || ordinary[0].title !== "普通入口") blockers.push("ordinary_primary_group_invalid");
  const allRows = groups?.flatMap((group) => group.routes.map((route) => ({ ...route, group: group.title, primary: group.primary }))) || [];
  const allKeys = allRows.map((row) => row.key);
  if (new Set(allKeys).size !== allKeys.length) blockers.push("route_alias_or_duplicate_detected");
  const legacyRows = allRows.filter((row) => row.key === "legacy");
  if (legacyRows.length !== 1 || legacyRows[0].group !== "系统迁移" || legacyRows[0].primary) {
    blockers.push("legacy_route_not_system_only");
  }
  if (!componentMap) blockers.push("route_component_map_unparseable");
  for (const [route, component] of EXPECTED_ROUTES) {
    if (componentMap?.[route] !== component) blockers.push(`ordinary_component_mismatch:${route}`);
  }
  if (!activeRouteBindingVerified) blockers.push("active_route_binding_not_exact");
  if (componentMap?.legacy !== "LegacyTools") blockers.push("legacy_component_mapping_invalid");
  if (
    routeImports.get("LegacyTools") !== "./routes/LegacyTools" ||
    [...routeImports.entries()].filter(([, path]) => path === "./routes/LegacyTools").length !== 1 ||
    identifierReferenceCount(ts, app, "LegacyTools") !== 2
  ) {
    blockers.push("legacy_component_alias_or_import_invalid");
  }
  if (!routeKeys || new Set(routeKeys).size !== routeKeys.length) blockers.push("route_keys_invalid_or_duplicate");
  if (!routeKeys || !expectedKeys.every((key) => routeKeys.includes(key)) || !routeKeys.includes("legacy")) {
    blockers.push("route_keys_missing_required_entry");
  }
  if (
    !routeKeys ||
    !componentMap ||
    new Set(allKeys).size !== routeKeys.length ||
    allKeys.some((key) => !routeKeys.includes(key)) ||
    routeKeys.some((key) => !allKeys.includes(key)) ||
    Object.keys(componentMap).length !== routeKeys.length ||
    Object.keys(componentMap).some((key) => !routeKeys.includes(key)) ||
    Object.entries(componentMap).some(([key, component]) => component === "LegacyTools" && key !== "legacy")
  ) {
    blockers.push("route_inventory_or_legacy_reachability_invalid");
  }
  if (
    !componentMap ||
    Object.values(componentMap).some(
      (component) => !component || identifierReferenceCount(ts, app, component) !== 2
    )
  ) {
    blockers.push("route_component_direct_render_or_alias_detected");
  }
  if (!routeAliases || JSON.stringify(routeAliases) !== JSON.stringify(["next"])) {
    blockers.push("route_normalization_aliases_not_exact");
  }
  if (!parsesTauriDefaultHome(ts, app)) blockers.push("tauri_default_home_not_ast_verified");
  const ordinaryComponentRootIds = {};
  const ordinaryRouteHeadings = {};
  const ordinaryComponentSourceSha256 = {};
  const ordinaryComponentImportManifest = {};
  for (const [route, component, expectedHeading] of EXPECTED_ROUTES) {
    const identity = componentRootIdentity(
      ts,
      projectRoot,
      routeImports.get(component),
      component,
      true,
      route,
      expectedHeading
    );
    if (!identity) {
      blockers.push(`ordinary_component_root_identity_invalid:${route}`);
      continue;
    }
    ordinaryComponentRootIds[route] = identity.component_id;
    ordinaryRouteHeadings[route] = identity.route_heading;
    ordinaryComponentSourceSha256[route] = identity.source_sha256;
    ordinaryComponentImportManifest[route] = identity.import_manifest;
  }
  const ordinaryComponentImportManifestDigest = digest(ordinaryComponentImportManifest);
  if (ordinaryComponentImportManifestDigest !== EXPECTED_IMPORT_MANIFEST_DIGEST) {
    blockers.push("ordinary_component_import_manifest_not_exact");
  }
  const legacyIdentity = componentRootIdentity(ts, projectRoot, routeImports.get("LegacyTools"), "LegacyTools", false);
  if (!legacyIdentity) blockers.push("legacy_component_root_identity_invalid");
  const observedOrdinaryMap = Object.fromEntries(
    EXPECTED_ROUTES.map(([route]) => [route, componentMap?.[route] || ""])
  );
  const contract = {
    schema_version: "streamlit_retirement_source_ast_contract.v5",
    status: blockers.length ? "source_ast_contract_blocked" : "source_ast_contract_verified",
    ordinary_routes: expectedKeys,
    ordinary_components: Object.fromEntries(EXPECTED_ROUTES),
    ordinary_component_root_ids: ordinaryComponentRootIds,
    ordinary_route_headings: ordinaryRouteHeadings,
    ordinary_component_source_sha256: ordinaryComponentSourceSha256,
    ordinary_component_import_manifest: ordinaryComponentImportManifest,
    ordinary_component_import_manifest_digest: ordinaryComponentImportManifestDigest,
    ordinary_component_map_digest: digest(observedOrdinaryMap),
    active_route_binding: activeRouteBindingVerified ? "ROUTE_COMPONENTS[route]" : "unverified",
    component_root_identity_attribute: "data-ltg10-component-id",
    legacy_route_group: legacyRows.length === 1 ? legacyRows[0].group : "invalid",
    legacy_route_primary: legacyRows.length === 1 ? legacyRows[0].primary : true,
    legacy_component_root_id: legacyIdentity?.component_id || "unverified",
    legacy_component_source_sha256: legacyIdentity?.source_sha256 || "",
    forbidden_ordinary_component_ids: FORBIDDEN_ORDINARY_COMPONENT_IDS,
    tauri_default_route: blockers.includes("tauri_default_home_not_ast_verified") ? "unverified" : "home",
    layout_source_sha256: sha256(layoutBytes),
    app_source_sha256: sha256(appBytes),
    trusted_reachable_source_sha256: reachable.hashes,
    trusted_reachable_source_digest: digest(reachable.hashes),
    native_escape_policy: "no_prototype_descriptor_reflect_lookup_call_apply_bind_or_network_native_alias",
    runner_source_sha256: runnerHash(projectRoot),
    blockers
  };
  return { ...contract, source_contract_digest: digest(contract) };
}

function exactObject(value, fields) {
  return value && typeof value === "object" && !Array.isArray(value) &&
    Object.keys(value).length === fields.length && fields.every((field) => Object.hasOwn(value, field));
}

function securePrivateFile(path, expectedParent, expectedName, maxBytes) {
  if (resolve(dirname(path)) !== resolve(expectedParent) || basename(path) !== expectedName) {
    throw new Error("private session file identity invalid");
  }
  const metadata = lstatSync(path);
  if (!metadata.isFile() || metadata.isSymbolicLink() || (metadata.mode & 0o777) !== 0o600 || metadata.nlink !== 1 || metadata.size <= 0 || metadata.size > maxBytes) {
    throw new Error("private session file permissions invalid");
  }
  return readFileSync(path);
}

function assertPrivateRunner(challengePath) {
  const session = dirname(challengePath);
  const sessionMetadata = lstatSync(session);
  if (!sessionMetadata.isDirectory() || sessionMetadata.isSymbolicLink() || (sessionMetadata.mode & 0o777) !== 0o700) {
    throw new Error("private runner session directory invalid");
  }
  const runnerPath = fileURLToPath(import.meta.url);
  const runnerBytes = securePrivateFile(runnerPath, session, "trusted_runner.mjs", 2 * 1024 * 1024);
  const challengeBytes = securePrivateFile(challengePath, session, "challenge.json", 256 * 1024);
  return { session, runnerPath, runnerBytes, challengeBytes };
}

function readNonce(fd) {
  if (!Number.isInteger(fd) || fd < 3) throw new Error("private nonce descriptor invalid");
  const metadata = fstatSync(fd);
  if (!metadata.isFIFO()) throw new Error("private nonce descriptor is not a pipe");
  const value = readFileSync(fd);
  if (value.length !== 32) throw new Error("private nonce must be exactly 32 bytes");
  return value;
}

function validateInheritedPipeSet(args) {
  const descriptors = [args.appInReadFd, args.appInWriteFd, args.appOutReadFd, args.appOutWriteFd];
  if (descriptors.some((fd) => !Number.isInteger(fd) || fd < 3) || new Set(descriptors).size !== 4) {
    throw new Error("private app pipe descriptors invalid");
  }
  for (const fd of descriptors) {
    if (!fstatSync(fd).isFIFO()) throw new Error("private app descriptor is not a POSIX pipe");
  }
}

function validateChallenge(challenge, nonce, runnerBytes, projectRoot) {
  const required = [
    "schema_version", "challenge_id", "nonce_digest", "created_at_utc", "head_full",
    "runner_source_sha256", "source_contract_digest", "ordinary_component_map_digest",
    "package_head_full", "artifact_set_sha256", "app_bundle_sha256", "app_executable_sha256", "dmg_sha256",
    "app_executable_path", "app_bundle_path", "dmg_path", "bundle_identifier", "bundle_version", "expected_routes", "expected_viewports",
    "production_required", "browser_or_vite_substitute_allowed", "external_calls_allowed",
    "challenge_digest"
  ];
  if (!exactObject(challenge, required) || challenge.schema_version !== CHALLENGE_SCHEMA) {
    throw new Error("private challenge schema invalid");
  }
  const material = { ...challenge };
  delete material.challenge_digest;
  if (!sameText(challenge.challenge_digest, digest(material)) || !sameText(challenge.nonce_digest, sha256(nonce))) {
    throw new Error("private challenge digest or nonce invalid");
  }
  if (
    challenge.production_required !== true ||
    challenge.browser_or_vite_substitute_allowed !== false ||
    challenge.external_calls_allowed !== false ||
    challenge.runner_source_sha256 !== sha256(runnerBytes) ||
    challenge.package_head_full !== challenge.head_full ||
    !validHead(challenge.head_full) ||
    !validSha(challenge.artifact_set_sha256) ||
    !validSha(challenge.app_bundle_sha256) ||
    !validSha(challenge.app_executable_sha256) ||
    !validSha(challenge.dmg_sha256) ||
    typeof challenge.bundle_identifier !== "string" || !challenge.bundle_identifier ||
    typeof challenge.bundle_version !== "string" || !challenge.bundle_version ||
    digest(challenge.expected_routes) !== digest(EXPECTED_ROUTES.map(([route]) => `#${route}`)) ||
    digest(challenge.expected_viewports) !== digest(Object.fromEntries(VIEWPORTS.map((row) => [row.name, { width: row.width, height: row.height }])))
  ) {
    throw new Error("private challenge production contract invalid");
  }
  const expectedExecutable = resolve(
    projectRoot,
    "desktop/src-tauri/target/release/bundle/macos/stock-MING Command Center.app/Contents/MacOS/stock_ming_command_center"
  );
  const expectedBundle = resolve(projectRoot, "desktop/src-tauri/target/release/bundle/macos/stock-MING Command Center.app");
  const expectedDmg = resolve(projectRoot, "desktop/src-tauri/target/release/bundle/dmg/stock-MING Command Center_3.0.0_aarch64.dmg");
  if (challenge.app_executable_path !== expectedExecutable || challenge.app_bundle_path !== expectedBundle || challenge.dmg_path !== expectedDmg) {
    throw new Error("formal packaged app path binding invalid");
  }
  if (
    !fixedPathReady(projectRoot, expectedExecutable, "file") ||
    !fixedPathReady(projectRoot, expectedBundle, "directory") ||
    !fixedPathReady(projectRoot, expectedDmg, "file")
  ) {
    throw new Error("formal fixed packaged artifact path invalid");
  }
  const executableSha = sha256(readFileSync(expectedExecutable));
  const bundleSha = bundleFingerprint(expectedBundle);
  const dmgSha = sha256(readFileSync(expectedDmg));
  const artifactSetSha = canonicalArtifactSet(
    bundleSha,
    dmgSha,
    challenge.bundle_identifier,
    challenge.bundle_version
  );
  if (
    executableSha !== challenge.app_executable_sha256 ||
    bundleSha !== challenge.app_bundle_sha256 ||
    dmgSha !== challenge.dmg_sha256 ||
    artifactSetSha !== challenge.artifact_set_sha256
  ) {
    throw new Error("formal fixed packaged artifact identity invalid");
  }
  return { projectRoot, expectedExecutable, expectedBundle, expectedDmg };
}

function collectStream(stream, limit) {
  return new Promise((resolvePromise, reject) => {
    const chunks = [];
    let size = 0;
    stream.on("data", (chunk) => {
      size += chunk.length;
      if (size > limit) {
        reject(new Error("private native output exceeds limit"));
        stream.destroy();
      } else {
        chunks.push(chunk);
      }
    });
    stream.on("end", () => resolvePromise(Buffer.concat(chunks)));
    stream.on("error", reject);
  });
}

const NATIVE_FAILURE_CODE_RULES = [
  ["qa inherited descriptor", "qa_descriptor_invalid"],
  ["qa descriptors must be distinct", "qa_descriptor_invalid"],
  ["native input frame", "input_frame_invalid"],
  ["native input JSON", "input_contract_invalid"],
  ["native input fields", "input_contract_invalid"],
  ["native input schema", "input_contract_invalid"],
  ["native nonce", "input_contract_invalid"],
  ["native input trailing", "input_contract_invalid"],
  ["challenge ", "challenge_contract_invalid"],
  ["runner parent", "runner_parent_identity_invalid"],
  ["runner process path", "runner_parent_identity_invalid"],
  ["packaged executable identity", "package_identity_invalid"],
  ["fixed packaged artifact", "package_identity_invalid"],
  ["current executable unavailable", "package_identity_invalid"],
  ["packaged QA document-start instrumentation", "document_instrumentation_unavailable"],
  ["native viewport resize", "viewport_measurement_invalid"],
  ["WKWebView content geometry", "viewport_measurement_invalid"],
  ["WKWebView safe-area", "viewport_measurement_invalid"],
  ["WKWebView native scale", "viewport_measurement_invalid"],
  ["WKWebView native pixel", "viewport_measurement_invalid"],
  ["WebView actual inner viewport", "viewport_measurement_invalid"],
  ["native inner-size measurement", "viewport_measurement_invalid"],
  ["native inner size", "viewport_measurement_invalid"],
  ["packaged route navigation", "route_navigation_invalid"],
  ["WebView eval dispatch failed", "observation_invalid"],
  ["WebView eval callback", "observation_invalid"],
  ["WebView eval result", "observation_invalid"],
  ["WebView observation", "observation_invalid"],
  ["observation ", "observation_invalid"],
  ["packaged DOM observation", "observation_invalid"],
  ["native snapshot", "snapshot_invalid"],
  ["WKWebView native snapshot", "snapshot_invalid"],
  ["network activity occurred", "network_seal_invalid"],
  ["final global quiet seal", "network_seal_invalid"],
  ["post-seal final capture", "network_seal_invalid"],
  ["native output", "native_output_invalid"]
];

function nativeFailureCode(stderrBytes) {
  const text = Buffer.isBuffer(stderrBytes) ? stderrBytes.toString("utf8") : "";
  const marker = ["ltg10 packaged QA refused: ", "ltg10 packaged QA failed closed: "]
    .map((prefix) => text.lastIndexOf(prefix))
    .reduce((latest, index) => Math.max(latest, index), -1);
  if (marker < 0) return "unknown";
  const detail = text.slice(marker).split(/\r?\n/, 1)[0];
  const rule = NATIVE_FAILURE_CODE_RULES.find(([fragment]) => detail.includes(fragment));
  return rule ? rule[1] : "unknown";
}

function nativeJsonFrameLengthValid(jsonLength, bufferLength, maxBytes = MAX_NATIVE_JSON_FRAME_BYTES) {
  return (
    Number.isSafeInteger(jsonLength) &&
    Number.isSafeInteger(bufferLength) &&
    Number.isSafeInteger(maxBytes) &&
    jsonLength > 0 &&
    maxBytes > 0 &&
    jsonLength <= maxBytes &&
    8 + jsonLength <= bufferLength
  );
}

function strictDeterministicGunzip(frame, expectedLength, maxBytes = MAX_NATIVE_DECOMPRESSED_JSON_BYTES) {
  if (
    !Buffer.isBuffer(frame) || frame.length < 18 ||
    frame.subarray(0, 10).toString("hex") !== "1f8b08000000000000ff" ||
    !Number.isSafeInteger(expectedLength) || expectedLength <= 0 || expectedLength > maxBytes
  ) throw new Error("native output JSON compression invalid");
  const deflate = frame.subarray(10, frame.length - 8);
  let inflated;
  try {
    inflated = inflateRawSync(deflate, { info: true, maxOutputLength: maxBytes });
  } catch {
    throw new Error("native output JSON compression invalid");
  }
  const raw = inflated?.buffer;
  if (!Buffer.isBuffer(raw) || inflated?.engine?.bytesWritten !== deflate.length || raw.length !== expectedLength) {
    throw new Error("native output JSON compression invalid");
  }
  const footer = frame.subarray(frame.length - 8);
  if (footer.readUInt32LE(0) !== (Number(crc32(raw)) >>> 0) || footer.readUInt32LE(4) !== (raw.length >>> 0)) {
    throw new Error("native output JSON compression invalid");
  }
  return raw;
}

function parseNativeOutput(buffer, nonce) {
  if (buffer.length < OUTPUT_FRAME_HEADER_BYTES) throw new Error("native output frame missing");
  if (
    !buffer.subarray(0, 8).equals(OUTPUT_FRAME_MAGIC) || buffer[8] !== OUTPUT_FRAME_CODEC ||
    buffer[9] !== 0 || !buffer.subarray(10, 16).equals(Buffer.alloc(6))
  ) throw new Error("native output frame codec invalid");
  const compressedLength = Number(buffer.readBigUInt64BE(16));
  const uncompressedLength = Number(buffer.readBigUInt64BE(24));
  if (!nativeJsonFrameLengthValid(compressedLength, buffer.length - (OUTPUT_FRAME_HEADER_BYTES - 8))) {
    throw new Error("native output JSON frame invalid");
  }
  if (!Number.isSafeInteger(uncompressedLength) || uncompressedLength <= 0 || uncompressedLength > MAX_NATIVE_DECOMPRESSED_JSON_BYTES) {
    throw new Error("native output JSON frame invalid");
  }
  const rawSha256 = buffer.subarray(32, 64).toString("hex");
  const transportResponseSha256 = buffer.subarray(64, 96).toString("hex");
  const compressedEnd = OUTPUT_FRAME_HEADER_BYTES + compressedLength;
  if (compressedEnd > buffer.length) throw new Error("native output JSON frame invalid");
  const raw = strictDeterministicGunzip(
    buffer.subarray(OUTPUT_FRAME_HEADER_BYTES, compressedEnd), uncompressedLength
  );
  if (!sameText(sha256(raw), rawSha256)) throw new Error("native output JSON hash invalid");
  const transport = {
    output_frame_magic: "LTG10QA1",
    output_frame_version: 1,
    output_frame_codec: OUTPUT_FRAME_CODEC_NAME,
    output_frame_flags: 0,
    output_frame_reserved: 0,
    output_frame_compressed_bytes: compressedLength,
    output_frame_uncompressed_bytes: uncompressedLength,
    output_frame_raw_json_sha256: rawSha256
  };
  const expectedTransportResponse = sha256(
    Buffer.concat([nonce, Buffer.from(JSON.stringify(canonical(transport)))])
  );
  if (!sameText(transportResponseSha256, expectedTransportResponse)) {
    throw new Error("native output frame nonce response invalid");
  }
  let output;
  try {
    output = JSON.parse(raw.toString("utf8"));
  } catch {
    throw new Error("native output JSON invalid");
  }
  let offset = compressedEnd;
  const screenshots = [];
  const expected = Number(output?.qa_matrix_count || 0);
  for (let index = 0; index < expected; index += 1) {
    if (offset + 8 > buffer.length) throw new Error("native snapshot frame header missing");
    const length = Number(buffer.readBigUInt64BE(offset));
    offset += 8;
    if (!Number.isSafeInteger(length) || length <= 0 || length > 32 * 1024 * 1024 || offset + length > buffer.length) {
      throw new Error("native snapshot frame length invalid");
    }
    screenshots.push(buffer.subarray(offset, offset + length));
    offset += length;
  }
  if (offset !== buffer.length) throw new Error("native output contains trailing bytes");
  return {
    output,
    screenshots,
    transport: { ...transport, output_frame_transport_response_sha256: transportResponseSha256 }
  };
}

function nonceResponseValid(value, nonce, responseField) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const material = { ...value };
  const observed = material[responseField];
  delete material[responseField];
  return validSha(observed) && sameText(observed, sha256(Buffer.concat([nonce, Buffer.from(JSON.stringify(canonical(material)))])));
}

function exactTauriRoute(value, route) {
  try {
    const url = new URL(value);
    return url.protocol === "tauri:" && url.hostname === "localhost" && ["", "/"].includes(url.pathname) && !url.search && url.hash === route;
  } catch {
    return false;
  }
}

function pngDimensions(buffer) {
  if (buffer.length < 24 || buffer.subarray(0, 8).toString("hex") !== "89504e470d0a1a0a" || buffer.subarray(12, 16).toString("ascii") !== "IHDR") {
    return null;
  }
  const width = buffer.readUInt32BE(16);
  const height = buffer.readUInt32BE(20);
  return width > 0 && height > 0 ? { width, height } : null;
}

function expectedTaskRequest(method, url) {
  return ["POST", "PUT", "PATCH", "DELETE"].includes(method) || /\/api\/(?:tasks?|.*(?:task|review|execute|launch))/i.test(url);
}

function localNetworkLedgerComplete(rows) {
  const fields = [
    "sequence", "request_id", "observed_monotonic_ns", "phase", "method", "url", "resource_type",
    "status", "task_request", "pending_count_after"
  ];
  if (!Array.isArray(rows) || rows.length < 2) return false;
  const requests = new Map();
  let pendingCount = 0;
  for (let index = 0; index < rows.length; index += 1) {
    const row = rows[index];
    if (!exactObject(row, fields) || row.sequence !== index + 1 || !Number.isInteger(row.observed_monotonic_ns) || row.observed_monotonic_ns <= 0 ||
      !/^request-\d+$|^resource-\d+$/.test(row.request_id) || !["navigation", "settle"].includes(row.phase) ||
      !["GET", "OPTIONS"].includes(row.method) || !["document", "fetch", "xhr", "serviceworker", "script", "stylesheet", "image", "font", "other"].includes(row.resource_type) ||
      !Number.isInteger(row.status) || row.status < 0 || row.status > 599 || typeof row.task_request !== "boolean" ||
      row.task_request !== expectedTaskRequest(row.method, row.url) || !Number.isInteger(row.pending_count_after) || row.pending_count_after < 0) return false;
    let parsed;
    try { parsed = new URL(row.url); } catch { return false; }
    if (parsed.protocol === "tauri:") {
      if ((parsed.hostname && parsed.hostname !== "localhost") || parsed.port) return false;
      if (parsed.hash && !EXPECTED_ROUTES.some(([route]) => parsed.hash === `#${route}`)) return false;
    } else if (!["http:", "https:"].includes(parsed.protocol) || !["127.0.0.1", "localhost", "[::1]"].includes(parsed.hostname) || parsed.port === "8501") {
      return false;
    }
    if (["fetch", "xhr", "serviceworker"].includes(row.resource_type)) pendingCount += row.phase === "navigation" ? 1 : -1;
    if (pendingCount < 0 || row.pending_count_after !== pendingCount) return false;
    const request = requests.get(row.request_id) || [];
    request.push(row);
    requests.set(row.request_id, request);
  }
  return pendingCount === 0 && [...requests.values()].every((entries) =>
    entries.length === 2 && entries[0].phase === "navigation" && entries[1].phase === "settle" &&
    entries[0].method === entries[1].method && entries[0].resource_type === entries[1].resource_type
  );
}

function domLedgerReady(rows, expectedRoute, expectedComponent, expectedHeading) {
  if (!Array.isArray(rows) || !rows.length || rows.some((row, index) =>
    !exactObject(row, ["sequence", "kind", "selector", "value"]) || row.sequence !== index + 1
  )) return false;
  const exact = new Map(rows.map((row) => [`${row.kind}\0${row.selector}`, row.value]));
  const get = (kind, selector) => exact.get(`${kind}\0${selector}`);
  let computed;
  try { computed = JSON.parse(get("computed", "body@computed-style-tree")); } catch { return false; }
  const headingSelector = `[data-ltg10-route-heading=${JSON.stringify(expectedRoute.slice(1))}]`;
  const headingStyles = Array.isArray(computed) ? computed.filter((row) => row?.selector === headingSelector) : [];
  const computedFields = [
    "selector", "display", "visibility", "opacity", "overflow", "color", "background_color", "before", "after",
    "visible", "viewport_intersection", "clipped", "content_visibility", "occluded", "color_alpha"
  ];
  return exact.size === rows.length && get("exists", "#root") === true &&
    get("count", "button[data-route-active='true']") === 1 &&
    get("attribute", "button[data-route-active='true']@data-route-key") === expectedRoute.slice(1) &&
    get("count", "[data-ltg10-route-heading]") === 1 &&
    get("attribute", "[data-ltg10-route-heading]@data-ltg10-route-heading") === expectedRoute.slice(1) &&
    ["h1", "h2"].includes(get("attribute", "[data-ltg10-route-heading]@tagName")) &&
    get("text", "[data-ltg10-route-heading]") === expectedHeading &&
    Array.isArray(computed) && computed.every((row) => exactObject(row, computedFields)) &&
    headingStyles.length === 1 && headingStyles[0].visible === true && headingStyles[0].viewport_intersection > 0 &&
    headingStyles[0].content_visibility !== "hidden" && headingStyles[0].occluded === false && headingStyles[0].color_alpha > 0 &&
    get("count", "[data-ltg10-component-id]") === 1 &&
    get("attribute", "[data-ltg10-component-id]@data-ltg10-component-id") === expectedComponent &&
    get("count", "body@frame-surface-count") === 0 && get("count", "body@open-shadow-root-count") === 0 &&
    get("count", "body@attach-shadow-call-count") === 0 && get("count", "body@custom-element-event-count") === 0 &&
    get("count", "body@custom-element-surface-count") === 0 && get("count", "body@dynamic-frame-create-count") === 0;
}

function canvasPresentCount(rows) {
  const inventory = rows.find((row) => row?.kind === "canvas" && row?.selector === "body@canvas-inventory")?.value;
  try {
    const parsed = JSON.parse(inventory);
    return Array.isArray(parsed) ? parsed.length : -1;
  } catch {
    return -1;
  }
}

function sealAuditReady(value) {
  const fields = [
    "sealed", "pending_request_count", "quiet_window_ms", "quiet_elapsed_ms", "instrumentation_integrity",
    "late_event_count", "late_events", "deny_all_network_guard", "denied_attempt_count", "denied_attempts",
    "final_window_ms", "final_window_elapsed_ms", "ledger_count", "ledger_digest_material",
    "guard_mode", "interval_registration_count", "interval_clear_count", "tracked_interval_count",
    "quiesced_interval_count", "active_interval_count_after_quiesce", "interval_registry_integrity",
    "quiesce_started_at_monotonic_ns", "quiesce_completed_at_monotonic_ns", "quiesce_complete",
    "denied_interval_registration_count"
  ];
  return exactObject(value, fields) && value.sealed === true && value.pending_request_count === 0 &&
    Number.isInteger(value.quiet_window_ms) && value.quiet_window_ms >= 500 &&
    typeof value.quiet_elapsed_ms === "number" && value.quiet_elapsed_ms >= value.quiet_window_ms &&
    value.instrumentation_integrity === true && value.late_event_count === 0 && Array.isArray(value.late_events) && value.late_events.length === 0 &&
    value.deny_all_network_guard === true && value.denied_attempt_count === 0 && Array.isArray(value.denied_attempts) && value.denied_attempts.length === 0 &&
    value.guard_mode === "quiesce_tracked_intervals_then_deny_all_then_exit" &&
    Number.isInteger(value.interval_registration_count) && value.interval_registration_count >= 0 &&
    value.interval_registration_count === value.interval_clear_count &&
    Number.isInteger(value.tracked_interval_count) && value.tracked_interval_count >= 0 &&
    value.tracked_interval_count === value.quiesced_interval_count &&
    value.active_interval_count_after_quiesce === 0 && value.interval_registry_integrity === true &&
    Number.isInteger(value.quiesce_started_at_monotonic_ns) && value.quiesce_started_at_monotonic_ns > 0 &&
    Number.isInteger(value.quiesce_completed_at_monotonic_ns) &&
    value.quiesce_completed_at_monotonic_ns >= value.quiesce_started_at_monotonic_ns &&
    value.quiesce_complete === true && value.denied_interval_registration_count === 0 &&
    Number.isInteger(value.final_window_ms) && value.final_window_ms >= 10_500 &&
    typeof value.final_window_elapsed_ms === "number" && value.final_window_elapsed_ms >= value.final_window_ms &&
    Number.isInteger(value.ledger_count) && value.ledger_count === value.ledger_digest_material?.length &&
    localNetworkLedgerComplete(value.ledger_digest_material);
}

function validateNativeMatrix(output, screenshots, challenge, nonce, childPid, packagePaths, runnerPath, transport) {
  const fields = [
    "schema_version", "status", "app_attestation", "route_count", "viewport_count", "qa_matrix_count", "rows", "seal_audit",
    "external_calls_triggered", "tushare_called", "deepseek_called", "github_called",
    "does_not_execute_trades", "does_not_modify_strategy_action", "contains_secret"
  ];
  if (
    !exactObject(output, fields) || output.schema_version !== NATIVE_OUTPUT_SCHEMA ||
    output.status !== "actual_packaged_tauri_native_matrix_captured" ||
    output.route_count !== EXPECTED_ROUTES.length || output.viewport_count !== VIEWPORTS.length ||
    output.qa_matrix_count !== EXPECTED_ROUTES.length * VIEWPORTS.length || !Array.isArray(output.rows) ||
    output.rows.length !== output.qa_matrix_count || screenshots.length !== output.qa_matrix_count ||
    output.external_calls_triggered !== false || output.tushare_called !== false || output.deepseek_called !== false ||
    output.github_called !== false || output.does_not_execute_trades !== true ||
    output.does_not_modify_strategy_action !== true || output.contains_secret !== false
  ) throw new Error("native matrix envelope invalid");
  const app = output.app_attestation;
  const appFields = [
    "schema_version", "status", "pid", "parent_pid", "parent_executable_path", "executable_path",
    "executable_sha256", "bundle_sha256", "artifact_set_sha256", "dmg_sha256", "head_full", "challenge_digest", "nonce_digest",
    "source_contract_digest", "ordinary_component_map_digest", "route_payload_sha256", "network_seal_sha256", "native_snapshot_api",
    "final_network_guard", "final_window_ms", "exit_after_output", "expected_exit_code", "exit_contract_sha256", "response_sha256"
  ];
  const exitContract = {
    final_network_guard: "quiesce_tracked_intervals_then_deny_all_then_exit",
    final_window_ms: output.seal_audit?.final_window_ms,
    exit_after_output: true,
    expected_exit_code: 0
  };
  if (
    !fixedPathReady(packagePaths.projectRoot, packagePaths.expectedExecutable, "file") ||
    !fixedPathReady(packagePaths.projectRoot, packagePaths.expectedBundle, "directory") ||
    !fixedPathReady(packagePaths.projectRoot, packagePaths.expectedDmg, "file")
  ) throw new Error("post-launch fixed packaged artifact path invalid");
  const postExecutableSha = sha256(readFileSync(packagePaths.expectedExecutable));
  const postBundleSha = bundleFingerprint(packagePaths.expectedBundle);
  const postDmgSha = sha256(readFileSync(packagePaths.expectedDmg));
  const postArtifactSetSha = canonicalArtifactSet(
    postBundleSha,
    postDmgSha,
    challenge.bundle_identifier,
    challenge.bundle_version
  );
  if (
    !exactObject(app, appFields) || app.schema_version !== APP_ATTESTATION_SCHEMA ||
    app.status !== "packaged_tauri_app_nonce_attested" || app.pid !== childPid || app.parent_pid !== process.pid ||
    realpathSync(app.parent_executable_path) !== realpathSync(process.execPath) ||
    app.executable_path !== packagePaths.expectedExecutable || app.executable_sha256 !== challenge.app_executable_sha256 ||
    app.bundle_sha256 !== challenge.app_bundle_sha256 || app.artifact_set_sha256 !== challenge.artifact_set_sha256 ||
    app.dmg_sha256 !== challenge.dmg_sha256 ||
    postExecutableSha !== challenge.app_executable_sha256 || postBundleSha !== challenge.app_bundle_sha256 ||
    postDmgSha !== challenge.dmg_sha256 || postArtifactSetSha !== challenge.artifact_set_sha256 ||
    app.head_full !== challenge.head_full || app.challenge_digest !== challenge.challenge_digest ||
    app.nonce_digest !== sha256(nonce) || app.source_contract_digest !== challenge.source_contract_digest ||
    app.ordinary_component_map_digest !== challenge.ordinary_component_map_digest ||
    app.route_payload_sha256 !== digest(output.rows) ||
    app.network_seal_sha256 !== digest(output.seal_audit) ||
    app.native_snapshot_api !== "WKWebView.takeSnapshotWithConfiguration.afterScreenUpdates" ||
    app.final_network_guard !== "quiesce_tracked_intervals_then_deny_all_then_exit" || app.final_window_ms !== output.seal_audit.final_window_ms ||
    app.exit_after_output !== true || app.expected_exit_code !== 0 || app.exit_contract_sha256 !== digest(exitContract) ||
    !nonceResponseValid(app, nonce, "response_sha256")
  ) throw new Error("native packaged app attestation invalid");
  if (!sealAuditReady(output.seal_audit)) throw new Error("native global quiet seal invalid");
  const nativeRowFields = [
    "observed_url", "dom_ledger", "task_post_count_before", "task_post_count_after", "navigation_post_count", "network_ledger",
    "observed_inner_width", "observed_inner_height", "device_pixel_ratio", "pending_request_count", "quiet_window_ms", "quiet_elapsed_ms",
    "instrumentation_integrity", "attach_shadow_calls", "custom_element_events", "dynamic_frame_events", "network_ledger_complete",
    "post_seal_capture", "deny_all_network_guard_at_observation", "late_event_count_at_observation",
    "denied_attempt_count_at_observation", "denied_interval_registration_count_at_observation",
    "route", "component", "viewport", "width", "height", "runtime_surface", "protocol",
    "native_inner_width_px", "native_inner_height_px", "screenshot_pixel_width", "screenshot_pixel_height",
    "observation_started_monotonic_ns", "observation_finished_monotonic_ns", "screenshot_index",
    "screenshot_byte_length", "screenshot_sha256", "screenshot_native_snapshot"
  ];
  const expectedPairs = VIEWPORTS.flatMap((viewport) => EXPECTED_ROUTES.map(([route, component, expectedHeading]) => ({ route: `#${route}`, component, expectedHeading, ...viewport })));
  let observedCanvasCount = 0;
  output.rows.forEach((row, index) => {
    const expected = expectedPairs[index];
    const screenshot = screenshots[index];
    const png = pngDimensions(screenshot);
    const expectedPhysicalWidth = Math.round(expected.width * Number(row.device_pixel_ratio));
    const expectedPhysicalHeight = Math.round(expected.height * Number(row.device_pixel_ratio));
    const expectedPostSealCapture = index === output.rows.length - 1;
    if (
      !exactObject(row, nativeRowFields) || row.route !== expected.route || row.component !== expected.component ||
      row.viewport !== expected.name || row.width !== expected.width || row.height !== expected.height ||
      row.runtime_surface !== "actual_packaged_tauri_react" || row.protocol !== "tauri:" ||
      !exactTauriRoute(row.observed_url, expected.route) || row.screenshot_index !== index ||
      row.screenshot_byte_length !== screenshot.length || row.screenshot_sha256 !== sha256(screenshot) ||
      row.screenshot_native_snapshot !== true || !png ||
      row.observed_inner_width !== expected.width || row.observed_inner_height !== expected.height ||
      typeof row.device_pixel_ratio !== "number" || !Number.isFinite(row.device_pixel_ratio) || row.device_pixel_ratio < 1 || row.device_pixel_ratio > 4 ||
      row.native_inner_width_px !== expectedPhysicalWidth || row.native_inner_height_px !== expectedPhysicalHeight ||
      row.screenshot_pixel_width !== expectedPhysicalWidth || row.screenshot_pixel_height !== expectedPhysicalHeight ||
      png.width !== row.screenshot_pixel_width || png.height !== row.screenshot_pixel_height ||
      !Number.isInteger(row.task_post_count_before) || row.task_post_count_before !== 0 ||
      !Number.isInteger(row.task_post_count_after) || row.task_post_count_after !== 0 ||
      !Number.isInteger(row.navigation_post_count) || row.navigation_post_count !== 0 ||
      row.pending_request_count !== 0 || !Number.isInteger(row.quiet_window_ms) || row.quiet_window_ms < 500 ||
      typeof row.quiet_elapsed_ms !== "number" || row.quiet_elapsed_ms < row.quiet_window_ms || row.instrumentation_integrity !== true ||
      !Array.isArray(row.attach_shadow_calls) || row.attach_shadow_calls.length !== 0 ||
      !Array.isArray(row.custom_element_events) || row.custom_element_events.length !== 0 ||
      !Array.isArray(row.dynamic_frame_events) || row.dynamic_frame_events.length !== 0 ||
      row.post_seal_capture !== expectedPostSealCapture ||
      row.deny_all_network_guard_at_observation !== expectedPostSealCapture ||
      row.late_event_count_at_observation !== 0 || row.denied_attempt_count_at_observation !== 0 ||
      row.denied_interval_registration_count_at_observation !== 0 ||
      row.network_ledger_complete !== true || !localNetworkLedgerComplete(row.network_ledger) ||
      !domLedgerReady(row.dom_ledger, expected.route, expected.component, expected.expectedHeading)
    ) throw new Error(`native route matrix row invalid:${index}`);
    const rowCanvasCount = canvasPresentCount(row.dom_ledger);
    if (rowCanvasCount < 0) throw new Error(`native canvas inventory invalid:${index}`);
    observedCanvasCount += rowCanvasCount;
  });
  if (digest(output.seal_audit.ledger_digest_material) !== digest(output.rows.at(-1)?.network_ledger)) {
    throw new Error("native final seal observed late network activity");
  }
  return { app: { ...app, ...transport }, runnerPath, observedCanvasCount };
}

function writePrivateScreenshot(session, index, route, viewport, bytes) {
  const directory = resolve(session, "screenshots");
  if (!existsSync(directory)) mkdirSync(directory, { mode: 0o700 });
  const metadata = lstatSync(directory);
  if (!metadata.isDirectory() || metadata.isSymbolicLink() || (metadata.mode & 0o777) !== 0o700) {
    throw new Error("private screenshot directory invalid");
  }
  const safeRoute = route.replace(/^#/, "").replace(/[^a-zA-Z0-9_-]/g, "-");
  const path = resolve(directory, `${String(index + 1).padStart(2, "0")}-${safeRoute}-${viewport}.png`);
  const fd = openSync(path, fsConstants.O_WRONLY | fsConstants.O_CREAT | fsConstants.O_EXCL | fsConstants.O_NOFOLLOW, 0o600);
  try {
    writeFileSync(fd, bytes);
    fsyncSync(fd);
  } finally {
    closeSync(fd);
  }
  const relativePath = relative(session, path);
  if (relativePath.startsWith(`..${sep}`) || relativePath === "..") throw new Error("private screenshot escaped session");
  return relativePath;
}

async function trustedSession(args) {
  const { session, runnerPath, runnerBytes, challengeBytes } = assertPrivateRunner(args.challengeFile);
  const nonce = readNonce(args.nonceFd);
  validateInheritedPipeSet(args);
  let challenge;
  try { challenge = JSON.parse(challengeBytes.toString("utf8")); } catch { throw new Error("private challenge JSON invalid"); }
  const packagePaths = validateChallenge(challenge, nonce, runnerBytes, args.projectRoot);
  const { expectedExecutable } = packagePaths;
  const runnerExecutablePath = realpathSync(process.execPath);
  const child = spawn(expectedExecutable, [QA_IN_FLAG, "3", QA_OUT_FLAG, "4"], {
    cwd: dirname(expectedExecutable),
    env: Object.fromEntries(["HOME", "LANG", "LC_ALL", "PATH", "TMPDIR", "USER"].filter((key) => process.env[key] !== undefined).map((key) => [key, process.env[key]])),
    stdio: ["ignore", "ignore", "pipe", args.appInReadFd, args.appOutWriteFd]
  });
  closeSync(args.appInReadFd);
  closeSync(args.appOutWriteFd);
  const input = {
    schema_version: NATIVE_INPUT_SCHEMA,
    challenge,
    runner_pid: process.pid,
    runner_executable_path: runnerExecutablePath
  };
  const inputBytes = Buffer.from(JSON.stringify(canonical(input)));
  const frame = Buffer.concat([Buffer.alloc(8), inputBytes, nonce]);
  frame.writeBigUInt64BE(BigInt(inputBytes.length), 0);
  writeFileSync(args.appInWriteFd, frame);
  closeSync(args.appInWriteFd);
  const outputPromise = collectStream(createReadStream(null, { fd: args.appOutReadFd, autoClose: true }), MAX_NATIVE_OUTPUT_BYTES);
  const stderrPromise = collectStream(child.stderr, 64 * 1024).catch(() => Buffer.alloc(0));
  const exitPromise = new Promise((resolvePromise, reject) => {
    child.once("error", reject);
    child.once("exit", (code, signal) => resolvePromise({ code, signal }));
  });
  const timeout = setTimeout(() => child.kill("SIGKILL"), 240_000);
  const [{ code, signal }, nativeBuffer, nativeStderr] = await Promise.all([exitPromise, outputPromise, stderrPromise]);
  clearTimeout(timeout);
  if (code !== 0 || signal || nativeBuffer.length < 8) {
    throw new Error(`packaged Tauri native adapter failed closed:${nativeFailureCode(nativeStderr)}`);
  }
  const { output, screenshots, transport } = parseNativeOutput(nativeBuffer, nonce);
  const { app, observedCanvasCount } = validateNativeMatrix(
    output, screenshots, challenge, nonce, child.pid, packagePaths, runnerPath, transport
  );
  const rows = output.rows.map((nativeRow, index) => {
    const screenshotPath = writePrivateScreenshot(session, index, nativeRow.route, nativeRow.viewport, screenshots[index]);
    const row = { ...nativeRow, screenshot_path: screenshotPath };
    delete row.screenshot_index;
    const rowHmacSha256 = hmac256(nonce, Buffer.from(JSON.stringify(canonical(row))));
    return { ...row, row_hmac_sha256: rowHmacSha256 };
  });
  const report = {
    schema_version: ATTESTATION_SCHEMA,
    status: observedCanvasCount > 0
      ? "actual_packaged_tauri_ordinary_flow_awaiting_visual_review"
      : "actual_packaged_tauri_ordinary_flow_passed",
    attestation_mode: "production_packaged_tauri_nonce_bound",
    runner_identity: "scripts/streamlit_retirement_packaged_qa_runner.mjs",
    runner_pid: process.pid,
    runner_executable_path: runnerPath,
    runner_source_sha256: sha256(runnerBytes),
    generated_at: new Date().toISOString(),
    challenge_id: challenge.challenge_id,
    challenge_digest: challenge.challenge_digest,
    nonce_digest: sha256(nonce),
    source_contract_digest: challenge.source_contract_digest,
    ordinary_component_map_digest: challenge.ordinary_component_map_digest,
    head_full: challenge.head_full,
    runtime_surface: "actual_packaged_tauri_react",
    protocol: "tauri:",
    package_head_full: challenge.package_head_full,
    artifact_set_sha256: challenge.artifact_set_sha256,
    app_bundle_sha256: challenge.app_bundle_sha256,
    app_executable_sha256: challenge.app_executable_sha256,
    dmg_sha256: challenge.dmg_sha256,
    app_attestation: app,
    app_exit_confirmed: code === 0 && !signal,
    app_exit_code: code,
    app_exit_signal: signal || "",
    route_count: output.route_count,
    viewport_count: output.viewport_count,
    qa_matrix_count: output.qa_matrix_count,
    passed_count: output.qa_matrix_count,
    review_required_count: observedCanvasCount,
    network_ledger_complete: sealAuditReady(output.seal_audit) && output.rows.every((row) => row.network_ledger_complete === true),
    network_seal_audit: output.seal_audit,
    rows,
    external_calls_triggered: false,
    tushare_called: false,
    deepseek_called: false,
    github_called: false,
    does_not_execute_trades: true,
    does_not_modify_strategy_action: true,
    contains_secret: false,
    payload_size_bytes: nativeBuffer.length
  };
  report.runner_response_sha256 = sha256(Buffer.concat([nonce, Buffer.from(JSON.stringify(canonical(report)))]));
  return report;
}

async function emit(value, json) {
  const payload = json ? `${JSON.stringify(value)}\n` : `${JSON.stringify(value, null, 2)}\n`;
  await new Promise((resolvePromise, reject) => {
    process.stdout.write(payload, (error) => error ? reject(error) : resolvePromise());
  });
}

const args = parseArgs(process.argv);
try {
  if (args.mode === "plan") {
    await emit(plan(args.projectRoot), args.json);
    process.exit(0);
  }
  if (args.mode === "capability") {
    await emit(capability(args.projectRoot), args.json);
    process.exit(0);
  }
  if (args.mode === "source") {
    const result = inspectSource(args.projectRoot);
    await emit(result, args.json);
    process.exit(result.status === "source_ast_contract_verified" ? 0 : 2);
  }
  if (args.mode === "trusted-session") {
    const result = capability(args.projectRoot);
    if (
      !result.packaged_dom_driver_supported ||
      !result.actual_packaged_tauri_launch_allowed ||
      !result.production_nonce_attestation_supported
    ) {
      await emit(
        {
          schema_version: RUNNER_SCHEMA,
          status: "packaged_tauri_trusted_session_blocked_before_nonce_read_or_launch",
          attempted_launch: false,
          nonce_read: false,
          challenge_read: false,
          raw_report_written: false,
          hmac_attestation_recorded: false,
          blockers: result.blockers,
          external_calls_triggered: false,
          does_not_execute_trades: true
        },
        args.json
      );
      process.exit(2);
    }
    const report = await trustedSession(args);
    await emit(report, args.json);
    process.exit(0);
  }
  const result = capability(args.projectRoot);
  await emit(
    {
      ...result,
      status: "packaged_tauri_ordinary_flow_execution_blocked_fail_closed",
      attempted_launch: false,
      raw_report_written: false,
      hmac_attestation_recorded: false
    },
    args.json
  );
  process.exit(2);
} catch (error) {
  await emit(
    {
      schema_version: RUNNER_SCHEMA,
      status: "packaged_tauri_runner_failed_closed",
      error_safe: String(error?.message || error),
      writes_evidence: false,
      creates_trust_key: false,
      external_calls_triggered: false,
      does_not_execute_trades: true
    },
    true
  );
  process.exit(2);
}
