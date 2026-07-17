const HOME_SYMBOL_PATTERN = /^\d{6}\.(SH|SZ|BJ)$/;
const HOME_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:-]*$/;
const HOME_FRESHNESS_PATTERN = /^[a-z][a-z0-9_]*$/;
const HOME_CANONICAL_RESULT_FRESHNESS_STATES = new Set(["fresh", "fresh_provider"]);

function strictHomeString(value, pattern, maxLength) {
  if (typeof value !== "string" || !value || value !== value.trim() || value.length > maxLength) return "";
  return pattern.test(value) ? value : "";
}

export function strictHomeSymbol(value) {
  return strictHomeString(value, HOME_SYMBOL_PATTERN, 16);
}

export function strictHomeIdentity(value, maxLength = 160) {
  return strictHomeString(value, HOME_ID_PATTERN, maxLength);
}

export function strictHomeFreshness(value) {
  return strictHomeString(value, HOME_FRESHNESS_PATTERN, 64);
}

export function isCanonicalHomeResultFreshness(value) {
  const freshness = strictHomeFreshness(value);
  return Boolean(freshness && HOME_CANONICAL_RESULT_FRESHNESS_STATES.has(freshness));
}

export function strictHomeResultDate(value, options = {}) {
  if (typeof value !== "string" || value !== value.trim()) return "";
  const allowIsoDate = options.allowIsoDate === true;
  const compact = /^\d{8}$/.test(value)
    ? value
    : allowIsoDate && /^\d{4}-\d{2}-\d{2}$/.test(value)
      ? value.replaceAll("-", "")
      : "";
  if (!compact) return "";
  const year = Number(compact.slice(0, 4));
  const month = Number(compact.slice(4, 6));
  const day = Number(compact.slice(6, 8));
  const parsed = new Date(Date.UTC(year, month - 1, day));
  return parsed.getUTCFullYear() === year &&
    parsed.getUTCMonth() === month - 1 &&
    parsed.getUTCDate() === day
    ? compact
    : "";
}

export function makeStrictHomeResultBinding(record, fields, source) {
  if (!record || typeof record !== "object" || Array.isArray(record)) return null;
  const binding = {
    source,
    symbol: strictHomeSymbol(record[fields.symbol]),
    taskId: strictHomeIdentity(record[fields.taskId], 160),
    resultVersion: strictHomeIdentity(record[fields.resultVersion], 120),
    dataDate: strictHomeResultDate(record[fields.dataDate]),
    freshness: strictHomeFreshness(record[fields.freshness]),
  };
  return binding.symbol && binding.taskId && binding.resultVersion && binding.dataDate && binding.freshness
    ? binding
    : null;
}

export function sameOrdinaryHomeResultBinding(left, right) {
  return left.symbol === right.symbol &&
    left.taskId === right.taskId &&
    left.resultVersion === right.resultVersion &&
    left.dataDate === right.dataDate &&
    left.freshness === right.freshness;
}

export function selectMatchingHomeResultBinding(bindings) {
  const complete = bindings.filter(Boolean);
  const incomplete = bindings.length === 0 || complete.length !== bindings.length;
  if (!complete.length) return { binding: null, conflict: false, incomplete };
  const first = complete[0];
  const conflict = complete.some((binding) => !sameOrdinaryHomeResultBinding(first, binding));
  return { binding: incomplete || conflict ? null : first, conflict, incomplete };
}

export function shouldKeepHomeResultPending({ pendingSymbol, pendingTaskId, binding }) {
  const symbol = strictHomeSymbol(pendingSymbol);
  const taskId = strictHomeIdentity(pendingTaskId, 160);
  if (!pendingSymbol && !pendingTaskId) return false;
  if (!symbol || !taskId || !binding) return true;
  return binding.symbol !== symbol || binding.taskId !== taskId;
}

export function shouldShowHomeSupportingDetails({ binding, inputGateClosed }) {
  return Boolean(binding && inputGateClosed === false);
}

export function makeStrictHomeConfirmedChain(record, fields, source) {
  if (!record || typeof record !== "object" || Array.isArray(record)) return null;
  const chain = {
    source,
    symbol: strictHomeSymbol(record[fields.symbol]),
    taskId: strictHomeIdentity(record[fields.taskId], 160),
  };
  return chain.symbol && chain.taskId ? chain : null;
}

export function selectMatchingHomeConfirmedChain(chains) {
  const complete = chains.filter(Boolean);
  const incomplete = chains.length === 0 || complete.length !== chains.length;
  if (!complete.length) return { chain: null, conflict: false, incomplete };
  const first = complete[0];
  const conflict = complete.some((chain) => chain.symbol !== first.symbol || chain.taskId !== first.taskId);
  return { chain: incomplete || conflict ? null : first, conflict, incomplete };
}

export function hasUnconfirmedHomeSymbolEdit({ touched, raw, valid, normalized, confirmedSymbol }) {
  if (!touched) return false;
  const value = typeof raw === "string" ? raw.trim() : "";
  if (!value || !valid) return true;
  return normalized !== confirmedSymbol;
}
