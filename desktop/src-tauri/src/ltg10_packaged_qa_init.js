;(() => {
  "use strict";
  if (Object.prototype.hasOwnProperty.call(window, "__STOCK_MING_LTG10_QA__")) return;

  const QUIET_WINDOW_MS = 650;
  const MAX_QUIET_WAIT_MS = 20_000;
  const FINAL_DENY_WINDOW_MS = 10_750;
  const mutationMethods = new Set(["POST", "PUT", "PATCH", "DELETE"]);
  const frameTags = new Set(["iframe", "object", "embed", "webview", "portal"]);
  const ledger = [];
  const pending = new Map();
  const observations = new Map();
  const attachShadowCalls = [];
  const customElementEvents = [];
  const frameCreateEvents = [];
  const lateEvents = [];
  const deniedNetworkAttempts = [];
  const lockedHooks = [];
  let sequence = 0;
  let requestSequence = 0;
  let observationSequence = 0;
  let taskPostCount = 0;
  let lastActivityMs = performance.now();
  let sealed = false;
  let sealStartedMs = 0;
  let intervalRegistrationCount = 0;
  let intervalClearCount = 0;
  let deniedIntervalRegistrationCount = 0;
  const activeIntervals = new Set();
  let intervalQuiescence = null;

  const nowNs = () => Math.max(1, Math.floor(performance.now() * 1e6));
  const absoluteUrl = (value) => {
    try { return new URL(String(value), location.href).href; } catch { return String(value || ""); }
  };
  const isTaskRequest = (method, url) =>
    mutationMethods.has(String(method || "GET").toUpperCase()) || /\/api\/(?:tasks?|.*(?:task|review|execute|launch))/i.test(String(url || ""));
  const markActivity = (kind) => {
    lastActivityMs = performance.now();
    if (sealed) lateEvents.push({ sequence: lateEvents.length + 1, kind, observed_monotonic_ns: nowNs() });
  };
  const lockValue = (owner, key, value, label) => {
    if (!owner) return false;
    try {
      Object.defineProperty(owner, key, { value, writable: false, configurable: false });
    } catch {
      return false;
    }
    const descriptor = Object.getOwnPropertyDescriptor(owner, key);
    const ready = Boolean(descriptor?.value === value && descriptor.writable === false && descriptor.configurable === false);
    if (ready) lockedHooks.push({ owner, key, value, label });
    return ready;
  };
  const originalSetInterval = window.setInterval;
  const originalClearInterval = window.clearInterval;
  const wrappedSetInterval = function(...args) {
    if (sealed) {
      deniedIntervalRegistrationCount += 1;
      markActivity("interval-registration-denied");
      throw new DOMException("ltg10_final_interval_guard_denied_registration", "InvalidStateError");
    }
    const handle = Reflect.apply(originalSetInterval, window, args);
    activeIntervals.add(handle);
    intervalRegistrationCount += 1;
    return handle;
  };
  const wrappedClearInterval = function(handle) {
    if (activeIntervals.delete(handle)) intervalClearCount += 1;
    return Reflect.apply(originalClearInterval, window, [handle]);
  };
  const intervalOwners = [window, typeof Window === "function" ? Window.prototype : null]
    .filter((owner, index, owners) => owner && owners.indexOf(owner) === index);
  for (const owner of intervalOwners) {
    lockValue(owner, "setInterval", wrappedSetInterval, owner === window ? "window.setInterval" : "Window.prototype.setInterval");
    lockValue(owner, "clearInterval", wrappedClearInterval, owner === window ? "window.clearInterval" : "Window.prototype.clearInterval");
  }
  const quiesceIntervals = () => {
    const started = nowNs();
    const tracked = activeIntervals.size;
    for (const handle of [...activeIntervals]) {
      Reflect.apply(originalClearInterval, window, [handle]);
      if (activeIntervals.delete(handle)) intervalClearCount += 1;
    }
    const completed = nowNs();
    const integrity = activeIntervals.size === 0 && intervalRegistrationCount === intervalClearCount && tracked >= 0;
    return {
      guard_mode: "quiesce_tracked_intervals_then_deny_all_then_exit",
      interval_registration_count: intervalRegistrationCount,
      interval_clear_count: intervalClearCount,
      tracked_interval_count: tracked,
      quiesced_interval_count: tracked,
      active_interval_count_after_quiesce: activeIntervals.size,
      interval_registry_integrity: integrity,
      quiesce_started_at_monotonic_ns: started,
      quiesce_completed_at_monotonic_ns: completed,
      quiesce_complete: integrity && completed >= started,
      denied_interval_registration_count: deniedIntervalRegistrationCount
    };
  };
  const denyNetworkAttempt = (method, url, resourceType) => {
    const row = {
      sequence: deniedNetworkAttempts.length + 1,
      method: String(method || "GET").toUpperCase(),
      url: absoluteUrl(url),
      resource_type: resourceType,
      observed_monotonic_ns: nowNs()
    };
    deniedNetworkAttempts.push(row);
    markActivity(`network-denied:${resourceType}:${row.method}`);
    return row;
  };
  const record = (phase, method, url, resourceType, status, requestId) => {
    const normalizedMethod = String(method || "GET").toUpperCase();
    const normalizedUrl = absoluteUrl(url);
    if (phase === "navigation" && mutationMethods.has(normalizedMethod)) taskPostCount += 1;
    ledger.push({
      sequence: ++sequence,
      request_id: String(requestId || ""),
      observed_monotonic_ns: nowNs(),
      phase,
      method: normalizedMethod,
      url: normalizedUrl,
      resource_type: resourceType,
      status: Number.isInteger(status) ? status : 0,
      task_request: isTaskRequest(normalizedMethod, normalizedUrl),
      pending_count_after: pending.size
    });
    markActivity(`network:${resourceType}:${phase}`);
  };
  const startRequest = (method, url, resourceType) => {
    const requestId = `request-${++requestSequence}`;
    pending.set(requestId, { method: String(method || "GET").toUpperCase(), url: absoluteUrl(url), resourceType });
    record("navigation", method, url, resourceType, 0, requestId);
    return requestId;
  };
  const finishRequest = (requestId, status = 0, url = "") => {
    const request = pending.get(requestId);
    if (!request) return;
    pending.delete(requestId);
    record("settle", request.method, url || request.url, request.resourceType, status, requestId);
  };

  const documentRequestId = `request-${++requestSequence}`;
  record("navigation", "GET", location.href, "document", 0, documentRequestId);
  record("settle", "GET", location.href, "document", 200, documentRequestId);

  const originalFetch = window.fetch;
  const wrappedFetch = async (...args) => {
    const input = args[0];
    const init = args[1] || {};
    const method = String(init.method || (input && input.method) || "GET").toUpperCase();
    const url = absoluteUrl(input && input.url ? input.url : input);
    if (sealed) {
      denyNetworkAttempt(method, url, "fetch");
      throw new TypeError("ltg10_final_network_guard_denied_fetch");
    }
    const requestId = startRequest(method, url, "fetch");
    try {
      const response = await Reflect.apply(originalFetch, window, args);
      finishRequest(requestId, response.status, response.url || url);
      return response;
    } catch (error) {
      finishRequest(requestId, 0, url);
      throw error;
    }
  };
  const fetchOwners = [window, typeof Window === "function" ? Window.prototype : null]
    .filter((owner, index, owners) => owner && owners.indexOf(owner) === index);
  for (const owner of fetchOwners) lockValue(owner, "fetch", wrappedFetch, owner === window ? "window.fetch" : "Window.prototype.fetch");

  const OriginalXMLHttpRequest = window.XMLHttpRequest;
  const originalOpen = XMLHttpRequest.prototype.open;
  const originalSend = XMLHttpRequest.prototype.send;
  const wrappedOpen = function(method, url, ...rest) {
    this.__ltg10_request = { method: String(method || "GET").toUpperCase(), url: absoluteUrl(url) };
    return originalOpen.call(this, method, url, ...rest);
  };
  const wrappedSend = function(...args) {
    const request = this.__ltg10_request || { method: "GET", url: location.href };
    if (sealed) {
      denyNetworkAttempt(request.method, request.url, "xhr");
      throw new DOMException("ltg10_final_network_guard_denied_xhr", "NetworkError");
    }
    const requestId = startRequest(request.method, request.url, "xhr");
    let finished = false;
    const finish = () => {
      if (finished) return;
      finished = true;
      finishRequest(requestId, Number(this.status || 0), this.responseURL || request.url);
    };
    this.addEventListener("loadend", finish, { once: true });
    try { return originalSend.apply(this, args); } catch (error) { finish(); throw error; }
  };
  const WrappedXMLHttpRequest = new Proxy(OriginalXMLHttpRequest, {
    construct(target, args, newTarget) { return Reflect.construct(target, args, newTarget); }
  });
  lockValue(XMLHttpRequest.prototype, "open", wrappedOpen, "XMLHttpRequest.prototype.open");
  lockValue(XMLHttpRequest.prototype, "send", wrappedSend, "XMLHttpRequest.prototype.send");
  lockValue(XMLHttpRequest.prototype, "constructor", WrappedXMLHttpRequest, "XMLHttpRequest.prototype.constructor");
  lockValue(window, "XMLHttpRequest", WrappedXMLHttpRequest, "window.XMLHttpRequest");

  const navigatorPrototype = typeof Navigator === "function" ? Navigator.prototype : Object.getPrototypeOf(navigator);
  const originalBeacon = navigatorPrototype?.sendBeacon || navigator.sendBeacon;
  let wrappedBeacon = null;
  if (originalBeacon) {
    wrappedBeacon = function(url, data) {
      if (sealed) {
        denyNetworkAttempt("POST", url, "beacon");
        return false;
      }
      const requestId = startRequest("POST", url, "beacon");
      try { return Reflect.apply(originalBeacon, this, [url, data]); } finally { finishRequest(requestId, 0, url); }
    };
    lockValue(navigatorPrototype, "sendBeacon", wrappedBeacon, "Navigator.prototype.sendBeacon");
    lockValue(navigator, "sendBeacon", wrappedBeacon, "navigator.sendBeacon");
  }

  let serviceWorkerContainer = null;
  try { serviceWorkerContainer = navigator.serviceWorker || null; } catch { serviceWorkerContainer = null; }
  const serviceWorkerPrototype = typeof ServiceWorkerContainer === "function"
    ? ServiceWorkerContainer.prototype
    : serviceWorkerContainer ? Object.getPrototypeOf(serviceWorkerContainer) : null;
  const originalServiceWorkerRegister = serviceWorkerPrototype?.register || serviceWorkerContainer?.register;
  let wrappedServiceWorkerRegister = null;
  if (typeof originalServiceWorkerRegister === "function") {
    wrappedServiceWorkerRegister = function(scriptURL, options) {
      const url = absoluteUrl(scriptURL);
      if (sealed) {
        denyNetworkAttempt("GET", url, "serviceworker");
        return Promise.reject(new DOMException("ltg10_final_network_guard_denied_serviceworker", "NetworkError"));
      }
      const requestId = startRequest("GET", url, "serviceworker");
      let result;
      try { result = Reflect.apply(originalServiceWorkerRegister, this, [scriptURL, options]); }
      catch (error) { finishRequest(requestId, 0, url); throw error; }
      return Promise.resolve(result).then(
        (value) => { finishRequest(requestId, 200, url); return value; },
        (error) => { finishRequest(requestId, 0, url); throw error; }
      );
    };
    lockValue(serviceWorkerPrototype, "register", wrappedServiceWorkerRegister, "ServiceWorkerContainer.prototype.register");
    lockValue(serviceWorkerContainer, "register", wrappedServiceWorkerRegister, "navigator.serviceWorker.register");
  }

  const wrappedConstructors = new Map();
  for (const [name, method, resourceType] of [["WebSocket", "CONNECT", "websocket"], ["EventSource", "GET", "eventsource"], ["Worker", "GET", "worker"]]) {
    const Original = window[name];
    if (typeof Original !== "function") continue;
    const Wrapped = new Proxy(Original, {
      construct(target, args, newTarget) {
        if (sealed) {
          denyNetworkAttempt(method, args[0], resourceType);
          throw new DOMException(`ltg10_final_network_guard_denied_${resourceType}`, "NetworkError");
        }
        const requestId = startRequest(method, args[0], resourceType);
        let instance;
        try { instance = Reflect.construct(target, args, newTarget); } catch (error) { finishRequest(requestId, 0, args[0]); throw error; }
        if (resourceType === "websocket" || resourceType === "eventsource") {
          instance.addEventListener("open", () => record("settle", method, args[0], resourceType, 101, requestId), { once: true });
          instance.addEventListener("close", () => finishRequest(requestId, 0, args[0]), { once: true });
        } else {
          const originalTerminate = instance.terminate?.bind(instance);
          if (originalTerminate) instance.terminate = () => { finishRequest(requestId, 0, args[0]); return originalTerminate(); };
        }
        return instance;
      }
    });
    wrappedConstructors.set(name, Wrapped);
    lockValue(Original.prototype, "constructor", Wrapped, `${name}.prototype.constructor`);
    lockValue(window, name, Wrapped, `window.${name}`);
  }

  const originalAttachShadow = Element.prototype.attachShadow;
  const wrappedAttachShadow = function(init) {
    const mode = init && init.mode === "closed" ? "closed" : "open";
    attachShadowCalls.push({ sequence: attachShadowCalls.length + 1, mode, tag: this.tagName.toLowerCase(), observed_monotonic_ns: nowNs() });
    markActivity(`attachShadow:${mode}`);
    return originalAttachShadow.call(this, init);
  };
  Object.defineProperty(Element.prototype, "attachShadow", { value: wrappedAttachShadow, writable: false, configurable: false });

  const originalCreateElement = Document.prototype.createElement;
  const originalCreateElementNS = Document.prototype.createElementNS;
  const recordElementCreation = (name, options) => {
    const normalized = String(name || "").toLowerCase();
    if (frameTags.has(normalized)) {
      frameCreateEvents.push({ sequence: frameCreateEvents.length + 1, tag: normalized, observed_monotonic_ns: nowNs() });
      markActivity(`createElement:${normalized}`);
    }
    if (normalized.includes("-") || options?.is) {
      customElementEvents.push({ sequence: customElementEvents.length + 1, kind: "create", name: normalized, observed_monotonic_ns: nowNs() });
      markActivity(`customElement:create:${normalized}`);
    }
  };
  const wrappedCreateElement = function(name, options) {
    recordElementCreation(name, options);
    return originalCreateElement.call(this, name, options);
  };
  const wrappedCreateElementNS = function(namespace, name, options) {
    recordElementCreation(name, options);
    return originalCreateElementNS.call(this, namespace, name, options);
  };
  Object.defineProperty(Document.prototype, "createElement", { value: wrappedCreateElement, writable: false, configurable: false });
  Object.defineProperty(Document.prototype, "createElementNS", { value: wrappedCreateElementNS, writable: false, configurable: false });

  const customElementPrototype = typeof CustomElementRegistry === "function"
    ? CustomElementRegistry.prototype
    : Object.getPrototypeOf(window.customElements);
  const originalCustomDefine = customElementPrototype?.define || window.customElements?.define;
  let wrappedCustomDefine = null;
  if (originalCustomDefine) {
    wrappedCustomDefine = function(name, constructor, options) {
      customElementEvents.push({ sequence: customElementEvents.length + 1, kind: "define", name: String(name || "").toLowerCase(), observed_monotonic_ns: nowNs() });
      markActivity(`customElement:define:${name}`);
      return Reflect.apply(originalCustomDefine, this, [name, constructor, options]);
    };
    lockValue(customElementPrototype, "define", wrappedCustomDefine, "CustomElementRegistry.prototype.define");
    lockValue(window.customElements, "define", wrappedCustomDefine, "customElements.define");
  }

  let performanceObserverReady = false;
  if (typeof PerformanceObserver === "function") {
    try {
      const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (entry.entryType !== "resource") continue;
          const type = ["fetch", "xmlhttprequest", "script", "css", "img", "font"].includes(entry.initiatorType)
            ? ({ xmlhttprequest: "xhr", css: "stylesheet", img: "image" }[entry.initiatorType] || entry.initiatorType)
            : "other";
          if (type === "fetch" || type === "xhr") continue;
          const requestId = `resource-${++requestSequence}`;
          record("navigation", "GET", entry.name, type, 0, requestId);
          record("settle", "GET", entry.name, type, 200, requestId);
        }
      });
      observer.observe({ type: "resource", buffered: true });
      performanceObserverReady = true;
    } catch { performanceObserverReady = false; }
  }

  const recordInsertedSurface = (node) => {
    const elements = node?.nodeType === Node.ELEMENT_NODE
      ? [node, ...Array.from(node.querySelectorAll?.("*") || [])]
      : [];
    for (const element of elements) {
      const tag = element.tagName?.toLowerCase?.() || "";
      if (frameTags.has(tag)) {
        frameCreateEvents.push({ sequence: frameCreateEvents.length + 1, tag, observed_monotonic_ns: nowNs() });
        markActivity(`inserted-frame:${tag}`);
      }
      if (tag.includes("-")) {
        customElementEvents.push({ sequence: customElementEvents.length + 1, kind: "insert", name: tag, observed_monotonic_ns: nowNs() });
        markActivity(`customElement:insert:${tag}`);
      }
    }
  };
  const mutationObserver = new MutationObserver((records) => {
    if (records.length) markActivity("dom-mutation");
    for (const record of records) for (const node of record.addedNodes || []) recordInsertedSurface(node);
  });
  mutationObserver.observe(document, { childList: true, subtree: true, attributes: true, characterData: true });

  const hookIntegrity = () => {
    const attach = Object.getOwnPropertyDescriptor(Element.prototype, "attachShadow");
    const create = Object.getOwnPropertyDescriptor(Document.prototype, "createElement");
    const createNs = Object.getOwnPropertyDescriptor(Document.prototype, "createElementNS");
    return Boolean(
      attach?.value === wrappedAttachShadow && attach.writable === false && attach.configurable === false &&
      create?.value === wrappedCreateElement && create.writable === false && create.configurable === false &&
      createNs?.value === wrappedCreateElementNS && createNs.writable === false && createNs.configurable === false &&
      XMLHttpRequest.prototype.open === wrappedOpen && XMLHttpRequest.prototype.send === wrappedSend &&
      XMLHttpRequest.prototype.constructor === WrappedXMLHttpRequest && window.XMLHttpRequest === WrappedXMLHttpRequest &&
      [...wrappedConstructors].every(([name, value]) => window[name] === value && value.prototype.constructor === value) &&
      (!wrappedBeacon || navigator.sendBeacon === wrappedBeacon) &&
      (!wrappedServiceWorkerRegister || serviceWorkerContainer?.register === wrappedServiceWorkerRegister) &&
      (!wrappedCustomDefine || window.customElements.define === wrappedCustomDefine) &&
      lockedHooks.length >= 8 && lockedHooks.every(({ owner, key, value }) => {
        const descriptor = Object.getOwnPropertyDescriptor(owner, key);
        return descriptor?.value === value && descriptor.writable === false && descriptor.configurable === false;
      }) &&
      performanceObserverReady
    );
  };

  const collectScopes = () => {
    const elements = [];
    const frames = [];
    const shadows = [];
    const documents = new Set();
    const walkRoot = (root) => {
      if (!root || documents.has(root)) return;
      documents.add(root);
      const rootElements = root.querySelectorAll ? Array.from(root.querySelectorAll("*")) : [];
      for (const element of rootElements) {
        elements.push(element);
        const tag = element.tagName?.toLowerCase?.() || "";
        if (frameTags.has(tag)) {
          frames.push(element);
          try { if (element.contentDocument) walkRoot(element.contentDocument); } catch { /* frame remains forbidden */ }
        }
        if (element.shadowRoot) {
          shadows.push(element.shadowRoot);
          walkRoot(element.shadowRoot);
        }
      }
    };
    walkRoot(document);
    return { elements, frames, shadows };
  };
  const colorAlpha = (value) => {
    const normalized = String(value || "").trim().toLowerCase();
    if (normalized === "transparent") return 0;
    const slashAlpha = normalized.match(/\/\s*([0-9.]+)(%)?\s*\)$/);
    const commaAlpha = normalized.startsWith("rgba(") ? normalized.match(/,\s*([0-9.]+)(%)?\s*\)$/) : null;
    const match = slashAlpha || commaAlpha;
    if (!match) return 1;
    const parsed = Number(match[1]);
    return Number.isFinite(parsed) ? Math.max(0, Math.min(1, match[2] ? parsed / 100 : parsed)) : 0;
  };
  const visibilityDetails = (element) => {
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    let left = Math.max(0, rect.left);
    let top = Math.max(0, rect.top);
    let right = Math.min(window.innerWidth, rect.right);
    let bottom = Math.min(window.innerHeight, rect.bottom);
    let clipped = false;
    let hiddenByAncestor = false;
    for (let ancestor = element.parentElement; ancestor; ancestor = ancestor.parentElement) {
      const ancestorStyle = getComputedStyle(ancestor);
      if (
        ancestorStyle.display === "none" || ancestorStyle.visibility === "hidden" ||
        ancestorStyle.contentVisibility === "hidden" || Number(ancestorStyle.opacity || 1) <= 0
      ) {
        hiddenByAncestor = true;
        break;
      }
      if ([ancestorStyle.overflowX, ancestorStyle.overflowY].some((value) => ["hidden", "clip", "scroll", "auto"].includes(value))) {
        const ancestorRect = ancestor.getBoundingClientRect();
        const nextLeft = Math.max(left, ancestorRect.left);
        const nextTop = Math.max(top, ancestorRect.top);
        const nextRight = Math.min(right, ancestorRect.right);
        const nextBottom = Math.min(bottom, ancestorRect.bottom);
        clipped ||= nextLeft !== left || nextTop !== top || nextRight !== right || nextBottom !== bottom;
        left = nextLeft;
        top = nextTop;
        right = nextRight;
        bottom = nextBottom;
      }
    }
    const viewportIntersection = Math.max(0, right - left) * Math.max(0, bottom - top);
    const samplePoints = viewportIntersection > 0
      ? [
          [(left + right) / 2, (top + bottom) / 2],
          [left + Math.min(2, Math.max(0, right - left) / 2), top + Math.min(2, Math.max(0, bottom - top) / 2)],
          [right - Math.min(2, Math.max(0, right - left) / 2), bottom - Math.min(2, Math.max(0, bottom - top) / 2)]
        ]
      : [];
    const unobscured = samplePoints.some(([x, y]) => {
      const topElement = typeof document.elementFromPoint === "function"
        ? document.elementFromPoint(Math.max(0, Math.min(window.innerWidth - 1, x)), Math.max(0, Math.min(window.innerHeight - 1, y)))
        : null;
      return Boolean(topElement && (topElement === element || element.contains(topElement) || topElement.contains(element)));
    });
    const heading = element.hasAttribute("data-ltg10-route-heading");
    const alpha = colorAlpha(style.color);
    const contentVisible = style.contentVisibility !== "hidden";
    const basic = !hiddenByAncestor && style.display !== "none" && style.visibility !== "hidden" &&
      contentVisible && Number(style.opacity || 1) > 0 && rect.width > 0 && rect.height > 0 && viewportIntersection > 0;
    return {
      visible: basic && unobscured && (!heading || alpha > 0),
      viewport_intersection: viewportIntersection,
      clipped,
      content_visibility: style.contentVisibility || "visible",
      occluded: !unobscured,
      color_alpha: alpha
    };
  };
  const visible = (element) => visibilityDetails(element).visible;
  const accessibleName = (element) => {
    const labelledBy = element.getAttribute("aria-labelledby");
    if (labelledBy) return labelledBy.split(/\s+/).map((id) => document.getElementById(id)?.textContent || "").join(" ").trim();
    const explicit = element.getAttribute("aria-label") || element.getAttribute("alt") || element.getAttribute("title");
    if (explicit) return explicit.trim();
    const tag = element.tagName.toLowerCase();
    const ownsTextName = ["a", "button", "h1", "h2", "h3", "h4", "h5", "h6", "label", "legend", "option", "summary"].includes(tag) || element.hasAttribute("role");
    return ownsTextName ? (element.textContent || "").trim() : "";
  };
  const stableSelector = (element, index) => {
    if (element.id) return `#${CSS.escape(element.id)}`;
    const component = element.getAttribute("data-ltg10-component-id");
    if (component) return `[data-ltg10-component-id=${JSON.stringify(component)}]`;
    const heading = element.getAttribute("data-ltg10-route-heading");
    if (heading) return `[data-ltg10-route-heading=${JSON.stringify(heading)}]`;
    return `${element.tagName.toLowerCase()}:nth-document(${index + 1})`;
  };
  const collectAccessibility = (elements) => elements.map((element, index) => ({
    selector: stableSelector(element, index), tag: element.tagName.toLowerCase(), role: element.getAttribute("role") || "",
    name: accessibleName(element), aria_hidden: element.getAttribute("aria-hidden") || "", aria_current: element.getAttribute("aria-current") || "",
    disabled: Boolean(element.disabled || element.getAttribute("aria-disabled") === "true"), visible: visible(element)
  }));
  const collectComputed = (elements) => elements.map((element, index) => {
    const style = getComputedStyle(element);
    const details = visibilityDetails(element);
    return { selector: stableSelector(element, index), display: style.display, visibility: style.visibility, opacity: style.opacity,
      overflow: style.overflow, color: style.color, background_color: style.backgroundColor,
      before: getComputedStyle(element, "::before").content, after: getComputedStyle(element, "::after").content,
      visible: details.visible, viewport_intersection: details.viewport_intersection, clipped: details.clipped,
      content_visibility: details.content_visibility, occluded: details.occluded, color_alpha: details.color_alpha };
  });
  const collectCanvas = (elements) => elements.filter((element) => element.tagName.toLowerCase() === "canvas").map((canvas, index) => {
    const rect = canvas.getBoundingClientRect();
    return { index, width: canvas.width, height: canvas.height, css_width: rect.width, css_height: rect.height, visible: visible(canvas) };
  });
  const quietState = () => ({
    pending_request_count: pending.size,
    quiet_elapsed_ms: Math.max(0, performance.now() - lastActivityMs),
    quiet_window_ms: QUIET_WINDOW_MS,
    hook_integrity: hookIntegrity(),
    sealed,
    late_event_count: lateEvents.length,
    deny_all_network_guard: sealed,
    denied_attempt_count: deniedNetworkAttempts.length,
    denied_attempts: deniedNetworkAttempts.map((row) => ({ ...row })),
    final_window_ms: FINAL_DENY_WINDOW_MS,
    final_window_elapsed_ms: sealed ? Math.max(0, performance.now() - sealStartedMs) : 0
  });
  const waitForQuiet = async () => {
    const deadline = performance.now() + MAX_QUIET_WAIT_MS;
    while (performance.now() < deadline) {
      const state = quietState();
      if (document.querySelector("#root") && state.pending_request_count === 0 && state.hook_integrity && state.quiet_elapsed_ms >= QUIET_WINDOW_MS) return state;
      await new Promise((resolve) => setTimeout(resolve, 50));
    }
    throw new Error("ltg10_dom_network_quiet_timeout");
  };
  const ledgerRows = () => {
    const active = document.querySelector("button[data-route-active='true']");
    const componentRoot = document.querySelector("[data-ltg10-component-id]");
    const heading = document.querySelector("[data-ltg10-route-heading]");
    const scopes = collectScopes();
    const computed = collectComputed(scopes.elements);
    const rows = [
      ["exists", "#root", Boolean(document.querySelector("#root"))],
      ["count", "button[data-route-active='true']", document.querySelectorAll("button[data-route-active='true']").length],
      ["attribute", "button[data-route-active='true']@data-route-key", active?.getAttribute("data-route-key") || ""],
      ["count", "[data-ltg10-route-heading]", document.querySelectorAll("[data-ltg10-route-heading]").length],
      ["attribute", "[data-ltg10-route-heading]@data-ltg10-route-heading", heading?.getAttribute("data-ltg10-route-heading") || ""],
      ["attribute", "[data-ltg10-route-heading]@tagName", heading?.tagName?.toLowerCase?.() || ""],
      ["text", "[data-ltg10-route-heading]", heading?.textContent?.trim() || ""],
      ["count", "[data-ltg10-component-id]", document.querySelectorAll("[data-ltg10-component-id]").length],
      ["attribute", "[data-ltg10-component-id]@data-ltg10-component-id", componentRoot?.getAttribute("data-ltg10-component-id") || ""],
      ["count", "[data-ltg10-component-id='LegacyTools'],[data-ltg10-component-id='AdminTools'],[data-ltg10-component-id='SystemMigration'],[data-ltg10-component-id='legacy'],[data-ltg10-component-id='admin'],[data-ltg10-component-id='system']", document.querySelectorAll("[data-ltg10-component-id='LegacyTools'],[data-ltg10-component-id='AdminTools'],[data-ltg10-component-id='SystemMigration'],[data-ltg10-component-id='legacy'],[data-ltg10-component-id='admin'],[data-ltg10-component-id='system']").length],
      ["count", "button[data-route-key='legacy'][data-route-active='true']", document.querySelectorAll("button[data-route-key='legacy'][data-route-active='true']").length],
      ["count", "[data-streamlit-surface],iframe[src*='streamlit']", document.querySelectorAll("[data-streamlit-surface],iframe[src*='streamlit']").length],
      ["count", "#root [data-ltg10-component-id]", document.querySelectorAll("#root [data-ltg10-component-id]").length],
      ["count", "body > :not(#root):not(script):not(style):not(link):not(meta):not(template)", document.querySelectorAll("body > :not(#root):not(script):not(style):not(link):not(meta):not(template)").length],
      ["count", "body@frame-surface-count", scopes.frames.length],
      ["count", "body@open-shadow-root-count", scopes.shadows.length],
      ["count", "body@attach-shadow-call-count", attachShadowCalls.length],
      ["count", "body@custom-element-event-count", customElementEvents.length],
      ["count", "body@custom-element-surface-count", scopes.elements.filter((element) => element.tagName.toLowerCase().includes("-")).length],
      ["count", "body@dynamic-frame-create-count", frameCreateEvents.length],
      ["html", "body", document.body.innerHTML],
      ["text", "body@innerText", document.body.innerText],
      ["accessibility", "body@accessibility-tree", JSON.stringify(collectAccessibility(scopes.elements))],
      ["computed", "body@computed-style-tree", JSON.stringify(computed)],
      ["pseudo", "body@pseudo-content", JSON.stringify(computed.map(({ selector, before, after, visible: isVisible }) => ({ selector, before, after, visible: isVisible })))],
      ["canvas", "body@canvas-inventory", JSON.stringify(collectCanvas(scopes.elements))]
    ];
    return rows.map(([kind, selector, value], index) => ({ sequence: index + 1, kind, selector, value }));
  };

  const api = Object.freeze({
    async observe(expected) {
      const before = taskPostCount;
      const quiet = await waitForQuiet();
      const result = {
        observed_url: location.href,
        observed_inner_width: window.innerWidth,
        observed_inner_height: window.innerHeight,
        device_pixel_ratio: window.devicePixelRatio,
        dom_ledger: ledgerRows(),
        task_post_count_before: before,
        task_post_count_after: taskPostCount,
        navigation_post_count: ledger.filter((row) => mutationMethods.has(row.method) || row.method === "CONNECT").length,
        pending_request_count: pending.size,
        quiet_window_ms: QUIET_WINDOW_MS,
        quiet_elapsed_ms: quiet.quiet_elapsed_ms,
        instrumentation_integrity: quiet.hook_integrity,
        attach_shadow_calls: attachShadowCalls.map((row) => ({ ...row })),
        custom_element_events: customElementEvents.map((row) => ({ ...row })),
        dynamic_frame_events: frameCreateEvents.map((row) => ({ ...row })),
        network_ledger_complete: quiet.hook_integrity && pending.size === 0 && quiet.quiet_elapsed_ms >= QUIET_WINDOW_MS,
        network_ledger: ledger.map((row) => ({ ...row }))
      };
      if (String(expected?.route || "") !== location.hash || result.pending_request_count !== 0) throw new Error("ltg10_route_or_pending_changed_during_observation");
      return result;
    },
    beginObservation(expected) {
      const token = `observation-${++observationSequence}`;
      observations.set(token, { status: "pending" });
      this.observe(expected).then((value) => observations.set(token, { status: "ready", value })).catch((error) => observations.set(token, { status: "failed", error: String(error?.message || error) }));
      return token;
    },
    takeObservation(token) {
      const result = observations.get(String(token));
      if (!result) return { status: "missing" };
      if (result.status !== "pending") observations.delete(String(token));
      return result;
    },
    beginSeal() {
      const token = `seal-${++observationSequence}`;
      observations.set(token, { status: "pending" });
      waitForQuiet().then((quiet) => {
        intervalQuiescence = quiesceIntervals();
        sealed = true;
        sealStartedMs = performance.now();
        observations.set(token, { status: "ready", value: {
          ...quiet,
          ...intervalQuiescence,
          sealed: true,
          deny_all_network_guard: true,
          denied_attempt_count: 0,
          denied_attempts: [],
          final_window_ms: FINAL_DENY_WINDOW_MS,
          final_window_elapsed_ms: 0,
          ledger_count: ledger.length,
          ledger_digest_material: ledger.map((row) => ({ ...row }))
        } });
      }).catch((error) => observations.set(token, { status: "failed", error: String(error?.message || error) }));
      return token;
    },
    verifySeal() {
      const quiet = quietState();
      return {
        ...(intervalQuiescence || {}),
        sealed: quiet.sealed,
        pending_request_count: quiet.pending_request_count,
        quiet_window_ms: quiet.quiet_window_ms,
        quiet_elapsed_ms: quiet.quiet_elapsed_ms,
        instrumentation_integrity: quiet.hook_integrity,
        late_event_count: lateEvents.length,
        late_events: lateEvents.map((row) => ({ ...row })),
        deny_all_network_guard: quiet.deny_all_network_guard,
        denied_attempt_count: quiet.denied_attempt_count,
        denied_attempts: quiet.denied_attempts,
        denied_interval_registration_count: deniedIntervalRegistrationCount,
        final_window_ms: quiet.final_window_ms,
        final_window_elapsed_ms: quiet.final_window_elapsed_ms,
        ledger_count: ledger.length,
        ledger_digest_material: ledger.map((row) => ({ ...row }))
      };
    }
  });
  Object.defineProperty(window, "__STOCK_MING_LTG10_QA__", { value: api, writable: false, configurable: false });
})();
