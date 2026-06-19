/* ================================================================= *
 *  settings-theme.js — 主题 / 外观 / 安全 / 自启
 *  依赖 utils.js / window.Friday
 * ================================================================= */

(function () {
  "use strict";

  const F = window.Friday;
  if (!F) { console.error("settings-theme.js: window.Friday 未初始化"); return; }

  /* ── 主题 / UI 偏好 ── */

  function cacheUiPrefs(theme, fontSize, uiLanguage) {
    localStorage.setItem(
      "friday_ui_prefs",
      JSON.stringify({
        theme,
        font_size: fontSize,
        ui_language: uiLanguage || window.FridayI18n?.getLanguage?.() || "zh",
      })
    );
  }

  function t(key, params) {
    return window.FridayI18n?.t?.(key, params) ?? key;
  }

  function resolveTheme(mode) {
    if (mode === "system") {
      return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }
    return mode === "light" ? "light" : "dark";
  }

  function applyTheme(mode) {
    const themeMode = mode || "light";
    document.documentElement.dataset.themeMode = themeMode;
    document.documentElement.dataset.theme = resolveTheme(themeMode);
    const resolved = resolveTheme(themeMode);
    document.documentElement.style.backgroundColor = resolved === "light" ? "#f0ebe3" : "#0a0d12";
    if (document.documentElement.classList.contains("desktop")) {
      window.pywebview?.api?.sync_window_chrome?.(
        resolved === "light" ? "#f0ebe3" : "#0a0d12",
        resolved === "dark"
      );
    }
  }

  function applyFontSize(size) {
    document.documentElement.dataset.fontSize = size || "medium";
  }

  function initThemeWatcher() {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => {
      if (document.documentElement.dataset.themeMode === "system") {
        applyTheme("system");
      }
    };
    if (media.addEventListener) media.addEventListener("change", handler);
    else media.addListener(handler);
  }

  function applyUiSettings(data) {
    applyTheme(data.theme || "light");
    applyFontSize(data.font_size || "medium");
    const lang = data.ui_language || "zh";
    window.FridayI18n?.setLanguage?.(lang);
    cacheUiPrefs(data.theme || "light", data.font_size || "medium", lang);
    F.refreshProviderLabels?.();
  }

  /* ── 安全表单 ── */

  function fillSecurityForm(data) {
    document.getElementById("restrictToWorkspace").checked = data.restrict_to_workspace;
    const allowRead = document.getElementById("allowReadUserFolders");
    if (allowRead) allowRead.checked = data.allow_read_user_folders !== false;
    document.getElementById("requireApprovalWrites").checked = data.require_approval_writes;
    document.getElementById("requireApprovalExec").checked = data.require_approval_exec;
    document.getElementById("approveOncePerTurn").checked = data.approve_once_per_turn !== false;
    document.getElementById("allowWriteFiles").checked = data.allow_write_files;
    document.getElementById("allowMoveFiles").checked = data.allow_move_files;
    document.getElementById("allowOrganize").checked = data.allow_organize;
    document.getElementById("allowCreateDocuments").checked = data.allow_create_documents;
    document.getElementById("allowPowershell").checked = data.allow_powershell;
    document.getElementById("allowPython").checked = data.allow_python !== false;
    document.getElementById("allowWebBrowse").checked = data.allow_web_browse;
    document.getElementById("allowDownloads").checked = data.allow_downloads;
    document.getElementById("requireTrustedDownloads").checked = data.require_trusted_downloads;
  }

  let autostartBusy = false;

  function applyAutostartUi(data) {
    const checkbox = document.getElementById("launchAtLogon");
    const hint = document.getElementById("launchAtLogonHint");
    if (!checkbox) return;
    checkbox.disabled = data.launch_at_logon_available === false;
    checkbox.checked = !!data.launch_at_logon;
    if (hint) {
      hint.textContent = data.launch_at_logon_detail || "";
    }
  }

  async function toggleAutostart(enabled) {
    if (autostartBusy) return;
    autostartBusy = true;
    const checkbox = document.getElementById("launchAtLogon");
    const resultEl = document.getElementById("autostartResult");
    if (resultEl) {
      resultEl.className = "settings-result";
      resultEl.textContent = enabled ? "正在开启…" : "正在关闭…";
    }
    try {
      const res = await F.apiFetch("/api/autostart", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: !!enabled }),
      });
      const data = await res.json();
      applyAutostartUi({
        launch_at_logon: !!data.enabled,
        launch_at_logon_available: data.available !== false,
        launch_at_logon_detail: data.detail || data.message || "",
      });
      if (resultEl) {
        resultEl.className = data.ok ? "settings-result ok" : "settings-result error";
        if (data.ok) {
          resultEl.textContent = data.enabled ? t("autostart.enabled") : t("autostart.disabled");
        } else {
          resultEl.textContent = data.message || t("autostart.failed");
          if (checkbox) checkbox.checked = !enabled;
        }
      } else if (!data.ok && checkbox) {
        checkbox.checked = !enabled;
      }
    } catch {
      if (resultEl) {
        resultEl.className = "settings-result error";
        resultEl.textContent = t("autostart.failed");
      }
      if (checkbox) checkbox.checked = !enabled;
    } finally {
      autostartBusy = false;
    }
  }

  function collectSecuritySettings() {
    return {
      restrict_to_workspace: document.getElementById("restrictToWorkspace").checked,
      allow_read_user_folders: document.getElementById("allowReadUserFolders")?.checked !== false,
      require_approval_writes: document.getElementById("requireApprovalWrites").checked,
      require_approval_exec: document.getElementById("requireApprovalExec").checked,
      approve_once_per_turn: document.getElementById("approveOncePerTurn").checked,
      allow_write_files: document.getElementById("allowWriteFiles").checked,
      allow_move_files: document.getElementById("allowMoveFiles").checked,
      allow_organize: document.getElementById("allowOrganize").checked,
      allow_create_documents: document.getElementById("allowCreateDocuments").checked,
      allow_powershell: document.getElementById("allowPowershell").checked,
      allow_python: document.getElementById("allowPython").checked,
      allow_web_browse: document.getElementById("allowWebBrowse").checked,
      allow_downloads: document.getElementById("allowDownloads").checked,
      require_trusted_downloads: document.getElementById("requireTrustedDownloads").checked,
    };
  }

  function applyStrictSecurityPreset() {
    document.getElementById("restrictToWorkspace").checked = true;
    const allowRead = document.getElementById("allowReadUserFolders");
    if (allowRead) allowRead.checked = false;
    document.getElementById("requireApprovalWrites").checked = true;
    document.getElementById("requireApprovalExec").checked = true;
    document.getElementById("allowWriteFiles").checked = true;
    document.getElementById("allowMoveFiles").checked = false;
    document.getElementById("allowOrganize").checked = false;
    document.getElementById("allowCreateDocuments").checked = true;
    document.getElementById("allowPowershell").checked = false;
    document.getElementById("allowPython").checked = true;
    document.getElementById("allowWebBrowse").checked = true;
    document.getElementById("allowDownloads").checked = false;
    document.getElementById("requireTrustedDownloads").checked = true;
  }

  F.t = t;
  F.cacheUiPrefs = cacheUiPrefs;
  F.resolveTheme = resolveTheme;
  F.applyTheme = applyTheme;
  F.applyFontSize = applyFontSize;
  F.initThemeWatcher = initThemeWatcher;
  F.applyUiSettings = applyUiSettings;
  F.fillSecurityForm = fillSecurityForm;
  F.collectSecuritySettings = collectSecuritySettings;
  F.applyStrictSecurityPreset = applyStrictSecurityPreset;
  F.applyAutostartUi = applyAutostartUi;
  F.toggleAutostart = toggleAutostart;

})();
