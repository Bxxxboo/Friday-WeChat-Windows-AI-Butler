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

  const POLL_MS = 12000;
  let pollTimer = null;

  const els = {
    apiDot: document.getElementById("statusApiDot"),
    apiText: document.getElementById("statusApiText"),
    visionDot: document.getElementById("statusVisionDot"),
    visionText: document.getElementById("statusVisionText"),
    tokens: document.getElementById("statusTokens"),
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

  function applyUsage(usage) {
    if (!usage || els.tokens == null) return;
    if (usage.tokens_total != null) {
      els.tokens.textContent = formatTokens(usage.tokens_total);
    }
  }

  function applyPayload(data) {
    if (!data) return;

    const apiOnline = Boolean(data.api_online);
    setDot(els.apiDot, apiOnline ? "online" : "offline");
    if (els.apiText) {
      els.apiText.textContent = F.t?.(apiOnline ? "status.api.online" : "status.api.offline") || "";
    }

    const visionEnabled = Boolean(data.vision_enabled);
    const visionOnline = Boolean(data.vision_online);
    if (!visionEnabled) {
      setDot(els.visionDot, "disabled");
      if (els.visionText) els.visionText.textContent = F.t?.("status.vision.disabled") || "";
    } else {
      setDot(els.visionDot, visionOnline ? "online" : "offline");
      if (els.visionText) {
        els.visionText.textContent = F.t?.(visionOnline ? "status.vision.on" : "status.vision.off") || "";
      }
    }

    if (els.tokens && data.tokens_total != null) {
      els.tokens.textContent = formatTokens(data.tokens_total);
    }
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

  function applyFromSettings(data) {
    if (!data) return;
    applyPayload({
      api_online: Boolean(data.api_ready),
      vision_enabled: Boolean(data.vision_enabled),
      vision_online: Boolean(data.vision_enabled && data.vision_ready),
      workspace: workspaceLabel(data.workspace),
      workspace_path: data.workspace,
      model: data.model || "—",
      tokens_total: undefined,
      tasks: undefined,
    });
  }

  async function refreshStatusBar() {
    if (!F.resolveApiToken?.()) return;
    try {
      const sessionId = F.activeSessionId || "";
      const qs = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : "";
      const res = await F.apiFetchWithTimeout(`/api/status-bar${qs}`, {}, 5000);
      if (!res.ok) return;
      const data = await res.json();
      applyPayload(data);
    } catch {
      // 保留已有状态（可能来自 applyFromSettings）
    }
  }

  function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(() => void refreshStatusBar(), POLL_MS);
  }

  F.applyStatusFromSettings = applyFromSettings;
  F.applyStatusUsage = applyUsage;
  F.refreshStatusBar = refreshStatusBar;

  startPolling();
  window.addEventListener("friday:languagechange", () => void refreshStatusBar());
})();
