/* ================================================================= *
 *  statusbar.js — 底部状态栏（参考 Reasonix）
 * ================================================================= */

(function () {
  "use strict";

  const F = window.Friday;
  if (!F) {
    console.error("statusbar.js: window.Friday 未初始化");
    return;
  }

  const POLL_MS = 30000;
  const REFRESH_TIMEOUT_MS = 12000;
  let pollTimer = null;
  let refreshInFlight = null;

  const els = {
    apiDot: document.getElementById("statusApiDot"),
    apiText: document.getElementById("statusApiText"),
    visionDot: document.getElementById("statusVisionDot"),
    visionText: document.getElementById("statusVisionText"),
    imageGenDot: document.getElementById("statusImageGenDot"),
    imageGenText: document.getElementById("statusImageGenText"),
    tokens: document.getElementById("statusTokens"),
    cacheWrap: document.getElementById("statusCacheWrap"),
    cacheHit: document.getElementById("statusCacheHit"),
    tasks: document.getElementById("statusTasks"),
    workspace: document.getElementById("statusWorkspace"),
    model: document.getElementById("statusModel"),
  };

  function formatTokens(n) {
    const num = Number(n) || 0;
    if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M`;
    if (num >= 1000) return `${(num / 1000).toFixed(1)}k`;
    return String(num);
  }

  function workspaceLabel(path) {
    if (!path) return "workspace";
    const parts = String(path).replace(/\\/g, "/").split("/").filter(Boolean);
    return parts[parts.length - 1] || path;
  }

  function setDot(el, state) {
    if (!el) return;
    el.dataset.state = state;
  }

  function formatCacheRate(hit, miss, rate) {
    const hitN = Number(hit) || 0;
    const missN = Number(miss) || 0;
    const total = hitN + missN;
    if (total <= 0) {
      return { text: "—", title: F.t?.("status.cacheHint") || "当前会话前缀缓存命中率" };
    }
    const pct = rate != null && !Number.isNaN(Number(rate))
      ? Number(rate) * 100
      : (hitN / total) * 100;
    const text = `${pct.toFixed(1)}%`;
    return {
      text,
      title: `缓存命中 ${formatTokens(hitN)} / ${formatTokens(total)} tokens（${text}）`,
    };
  }

  function applyCacheStats(hit, miss, rate) {
    if (!els.cacheWrap || !els.cacheHit) return;
    const { text, title } = formatCacheRate(hit, miss, rate);
    els.cacheHit.textContent = text;
    els.cacheWrap.title = title;
    els.cacheWrap.hidden = false;
  }

  function applyUsage(usage) {
    if (!usage || els.tokens == null) return;
    if (usage.tokens_total != null) {
      els.tokens.textContent = formatTokens(usage.tokens_total);
    }
    applyCacheStats(
      usage.cache_hit_tokens,
      usage.cache_miss_tokens,
      usage.cache_hit_rate,
    );
  }

  function applyServiceState({
    enabled,
    configured,
    online,
    detail,
    dotEl,
    textEl,
    labels,
  }) {
    if (!dotEl || !textEl) return;
    dotEl.title = detail || "";

    if (!enabled) {
      setDot(dotEl, "disabled");
      textEl.textContent = labels.disabled;
      return;
    }
    if (!configured) {
      setDot(dotEl, "disabled");
      textEl.textContent = labels.unconfigured;
      return;
    }
    setDot(dotEl, online ? "online" : "offline");
    textEl.textContent = online ? labels.online : labels.offline;
  }

  function applyPayload(data) {
    if (!data) return;

    applyServiceState({
      enabled: true,
      configured: Boolean(data.api_configured),
      online: Boolean(data.api_online),
      detail: data.api_reach_detail || "",
      dotEl: els.apiDot,
      textEl: els.apiText,
      labels: {
        unconfigured: F.t?.("status.api.unconfigured") || "API 未配置",
        online: F.t?.("status.api.online") || "API 在线",
        offline: F.t?.("status.api.offline") || "API 离线",
        disabled: F.t?.("status.api.offline") || "API 离线",
      },
    });

    applyServiceState({
      enabled: Boolean(data.vision_enabled),
      configured: Boolean(data.vision_configured),
      online: Boolean(data.vision_online),
      detail: data.vision_reach_detail || "",
      dotEl: els.visionDot,
      textEl: els.visionText,
      labels: {
        disabled: F.t?.("status.vision.disabled") || "视觉 关",
        unconfigured: F.t?.("status.vision.unconfigured") || "视觉 未配置",
        online: F.t?.("status.vision.on") || "视觉 在线",
        offline: F.t?.("status.vision.off") || "视觉 离线",
      },
    });

    applyServiceState({
      enabled: Boolean(data.image_gen_enabled),
      configured: Boolean(data.image_gen_configured),
      online: Boolean(data.image_gen_online),
      detail: data.image_gen_reach_detail || "",
      dotEl: els.imageGenDot,
      textEl: els.imageGenText,
      labels: {
        disabled: F.t?.("status.imageGen.disabled") || "生图 关",
        unconfigured: F.t?.("status.imageGen.unconfigured") || "生图 未配置",
        online: F.t?.("status.imageGen.on") || "生图 在线",
        offline: F.t?.("status.imageGen.off") || "生图 离线",
      },
    });

    if (els.tokens && data.tokens_total != null) {
      els.tokens.textContent = formatTokens(data.tokens_total);
    }
    applyCacheStats(data.cache_hit_tokens, data.cache_miss_tokens, data.cache_hit_rate);
    if (els.tasks && data.tasks != null) {
      els.tasks.textContent = String(data.tasks);
    }
    if (els.workspace) {
      const label = data.workspace || workspaceLabel(data.workspace_path);
      els.workspace.textContent = label;
      if (data.workspace_path) els.workspace.title = data.workspace_path;
    }
    if (els.model && data.model) {
      els.model.textContent = data.model;
    }
  }

  function patchImageGenStatus(partial = {}) {
    if (!partial) return;
    const enabled = partial.image_gen_enabled ?? Boolean(
      document.getElementById("imageGenEnabled")?.checked
    );
    const configured = partial.image_gen_configured ?? (
      enabled && Boolean(partial.image_gen_ready ?? partial.image_gen_configured)
    );
    if (partial.image_gen_checking) {
      applyServiceState({
        enabled,
        configured: configured || enabled,
        online: false,
        detail: partial.image_gen_reach_detail || F.t?.("status.imageGen.checkingHint") || "正在检测生图 API…",
        dotEl: els.imageGenDot,
        textEl: els.imageGenText,
        labels: {
          disabled: F.t?.("status.imageGen.disabled") || "生图 关",
          unconfigured: F.t?.("status.imageGen.unconfigured") || "生图 未配置",
          online: F.t?.("status.imageGen.on") || "生图 在线",
          offline: F.t?.("status.imageGen.checking") || "生图 检测中",
        },
      });
      return;
    }
    if (partial.image_gen_online != null || partial.image_gen_configured != null) {
      applyServiceState({
        enabled,
        configured: partial.image_gen_configured ?? configured,
        online: Boolean(partial.image_gen_online),
        detail: partial.image_gen_reach_detail || "",
        dotEl: els.imageGenDot,
        textEl: els.imageGenText,
        labels: {
          disabled: F.t?.("status.imageGen.disabled") || "生图 关",
          unconfigured: F.t?.("status.imageGen.unconfigured") || "生图 未配置",
          online: F.t?.("status.imageGen.on") || "生图 在线",
          offline: F.t?.("status.imageGen.off") || "生图 离线",
        },
      });
    }
  }

  function patchStatusBar(partial) {
    if (!partial) return;
    if (partial.model && els.model) {
      els.model.textContent = partial.model;
    }
    if (partial.workspace && els.workspace) {
      els.workspace.textContent = partial.workspace;
    }
    if (partial.api_reach_detail && els.apiDot) {
      els.apiDot.title = partial.api_reach_detail;
    }
    if (partial.api_checking && els.apiDot && els.apiText) {
      setDot(els.apiDot, "offline");
      els.apiText.textContent = F.t?.("status.api.checking") || "API 检测中";
      els.apiDot.title = F.t?.("status.api.checkingHint") || "正在检测新模型连接…";
    }
    if (partial.tokens_total != null && els.tokens) {
      els.tokens.textContent = formatTokens(partial.tokens_total);
    }
    if (
      partial.cache_hit_tokens != null
      || partial.cache_miss_tokens != null
      || partial.cache_hit_rate != null
    ) {
      applyCacheStats(
        partial.cache_hit_tokens,
        partial.cache_miss_tokens,
        partial.cache_hit_rate,
      );
    }
  }

  function applyFromSettings(data) {
    if (!data) return;
    const imageGenEnabled = Boolean(data.image_gen_enabled);
    const imageGenReady = Boolean(data.image_gen_enabled && data.image_gen_ready);
    applyPayload({
      api_online: false,
      api_configured: Boolean(data.api_ready),
      api_reach_detail: data.api_ready ? "正在检测连接…" : "未配置 API Key",
      vision_enabled: Boolean(data.vision_enabled),
      vision_configured: Boolean(data.vision_enabled && data.vision_ready),
      vision_online: false,
      vision_reach_detail: "",
      image_gen_enabled: imageGenEnabled,
      image_gen_configured: imageGenReady,
      image_gen_online: false,
      image_gen_reach_detail: imageGenReady ? "正在检测生图 API…" : "",
      workspace: workspaceLabel(data.workspace),
      workspace_path: data.workspace,
      model: data.model || "—",
      tokens_total: undefined,
      tasks: undefined,
    });
    if (imageGenReady) {
      patchImageGenStatus({
        image_gen_enabled: true,
        image_gen_configured: true,
        image_gen_checking: true,
      });
    }
    void refreshStatusBar({ force: true });
  }

  async function refreshStatusBar(options = {}) {
    if (!F.resolveApiToken?.()) return;
    if (refreshInFlight && !options.force) return refreshInFlight;
    refreshInFlight = (async () => {
      try {
        const sessionId = F.activeSessionId || "";
        const qs = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : "";
        const res = await F.apiFetchWithTimeout(`/api/status-bar${qs}`, {}, REFRESH_TIMEOUT_MS);
        if (!res.ok) return;
        const data = await res.json();
        applyPayload(data);
      } catch {
        // 保留已有状态
      }
    })();
    try {
      await refreshInFlight;
    } finally {
      refreshInFlight = null;
    }
  }

  function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(() => void refreshStatusBar(), POLL_MS);
  }

  F.applyStatusFromSettings = applyFromSettings;
  F.applyStatusUsage = applyUsage;
  F.patchStatusBar = patchStatusBar;
  F.patchImageGenStatus = patchImageGenStatus;
  F.refreshStatusBar = refreshStatusBar;

  startPolling();
  window.addEventListener("friday:languagechange", () => void refreshStatusBar());
})();
