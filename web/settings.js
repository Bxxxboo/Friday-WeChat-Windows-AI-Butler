/* ================================================================= *
 *  settings.js — 设置页：加载 / 导航 / 移植 / 更新
 *  依赖 settings-theme.js、settings-providers.js
 * ================================================================= */

(function () {
  "use strict";

  const F = window.Friday;
  if (!F) { console.error("settings.js: window.Friday 未初始化"); return; }
  /* ── 加载设置 ── */

  async function loadSettings(options = {}) {
    const skipStartupTests = Boolean(options.skipStartupTests);
    const res = await F.apiFetchWithTimeout("/api/settings", {}, 15000);
    if (!res.ok) throw new Error(`加载设置失败 (${res.status})`);
    const data = await res.json();
    F.apiReady = data.api_ready;
    try {
      await F.initProviders?.(data);
    } catch (err) {
      console.warn("initProviders", err);
    }
    document.getElementById("baseUrl").value = data.base_url || "https://api.deepseek.com";
    const apiProxy = document.getElementById("apiProxy");
    if (apiProxy) apiProxy.value = data.api_proxy || "";
    const apiTrustEnv = document.getElementById("apiTrustEnv");
    if (apiTrustEnv) apiTrustEnv.checked = data.api_trust_env !== false;
    document.getElementById("workspace").value = data.workspace;
    document.getElementById("apiKeyHint").textContent = data.api_key_masked
      ? `当前已保存: ${data.api_key_masked}`
      : "尚未保存 API Key";
    const visionEnabled = document.getElementById("visionEnabled");
    if (visionEnabled) visionEnabled.checked = !!data.vision_enabled;
    F.applyVisionKeyHint?.(data);
    if (visionEnabled) {
      F.updateVisionStatus?.(data.vision_ready, data.vision_enabled, data.vision_status_hint);
    }
    const imageGenEnabled = document.getElementById("imageGenEnabled");
    if (imageGenEnabled) imageGenEnabled.checked = !!data.image_gen_enabled;
    const imageGenFallback = document.getElementById("imageGenFallbackUrls");
    if (imageGenFallback) imageGenFallback.value = data.image_gen_fallback_urls || "";
    const imageGenHint = document.getElementById("imageGenApiKeyHint");
    if (imageGenHint) {
      imageGenHint.textContent = data.image_gen_api_key_masked
        ? `当前已保存: ${data.image_gen_api_key_masked}`
        : "尚未保存生图 API Key";
    }
    if (imageGenEnabled) {
      F.updateImageGenStatus?.(
        data.image_gen_ready,
        data.image_gen_enabled,
        data.image_gen_status_hint || "",
      );
    }
    document.getElementById("themeMode").value = data.theme || "light";
    document.getElementById("fontSize").value = data.font_size || "medium";
    const langEl = document.getElementById("uiLanguage");
    if (langEl) langEl.value = data.ui_language || "zh";
    F.setInteractionMode?.(data.interaction_mode || "agent", { persist: false, skipYoloGate: true });
    void F.refreshYoloUnlockState?.();
    F.fillSecurityForm?.(data);
    F.applyAutostartUi?.(data);
    fillArtifactForm(data);
    fillContextSmartForm(data);
    void loadWorkspaceMemoryEditor();
    void loadUserMemoryList();
    F.applyUiSettings?.(data);
    F.updateApiStatus(data.api_ready);
    F.bootSettingsSnapshot = data;
    F.applyStatusFromSettings?.(data);
    F.updateInputState();
    if (!skipStartupTests) {
      void F.runStartupApiTests?.();
    }
    if (Array.isArray(data.portability_notices) && data.portability_notices.length && F.settingsResult) {
      F.settingsResult.className = "settings-result error";
      F.settingsResult.textContent = data.portability_notices.join("\n");
    }
    return data;
  }

  /* ── 设置面板切换 ── */

  let settingsReturnFocus = null;

  const SETTINGS_FOCUSABLE =
    'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

  function getSettingsNavTabs() {
    return Array.from(document.querySelectorAll(".settings-nav-item:not(:disabled)"));
  }

  function getVisibleSettingsFocusables() {
    const modal = F.settingsModal;
    if (!modal) return [];
    return Array.from(modal.querySelectorAll(SETTINGS_FOCUSABLE)).filter(
      (el) => el.offsetParent !== null
    );
  }

  function syncSettingsTabA11y(panel) {
    getSettingsNavTabs().forEach((btn) => {
      const selected = btn.dataset.panel === panel;
      btn.setAttribute("aria-selected", selected ? "true" : "false");
      btn.tabIndex = selected ? 0 : -1;
    });
    document.querySelectorAll(".settings-section").forEach((section) => {
      const active = section.id === `panel-${panel}`;
      section.setAttribute("aria-hidden", active ? "false" : "true");
    });
  }

  function initSettingsA11y() {
    const modal = F.settingsModal;
    if (!modal || modal.dataset.a11yBound === "1") return;
    modal.dataset.a11yBound = "1";

    getSettingsNavTabs().forEach((btn) => {
      const panel = btn.dataset.panel;
      btn.setAttribute("role", "tab");
      btn.setAttribute("id", `settings-tab-${panel}`);
      btn.setAttribute("aria-controls", `panel-${panel}`);
      btn.addEventListener("keydown", (event) => {
        const tabs = getSettingsNavTabs();
        const idx = tabs.indexOf(btn);
        if (idx < 0) return;
        if (event.key === "ArrowDown" || event.key === "ArrowRight") {
          event.preventDefault();
          const next = tabs[(idx + 1) % tabs.length];
          F.switchSettingsPanel(next.dataset.panel);
          next.focus();
        } else if (event.key === "ArrowUp" || event.key === "ArrowLeft") {
          event.preventDefault();
          const prev = tabs[(idx - 1 + tabs.length) % tabs.length];
          F.switchSettingsPanel(prev.dataset.panel);
          prev.focus();
        } else if (event.key === "Home") {
          event.preventDefault();
          F.switchSettingsPanel(tabs[0].dataset.panel);
          tabs[0].focus();
        } else if (event.key === "End") {
          event.preventDefault();
          const last = tabs[tabs.length - 1];
          F.switchSettingsPanel(last.dataset.panel);
          last.focus();
        }
      });
    });

    document.querySelectorAll(".settings-section").forEach((section) => {
      section.setAttribute("role", "tabpanel");
      const panelId = section.id.replace(/^panel-/, "");
      section.setAttribute("aria-labelledby", `settings-tab-${panelId}`);
    });

    modal.addEventListener("keydown", (event) => {
      if (event.key !== "Tab" || modal.classList.contains("hidden")) return;
      const nodes = getVisibleSettingsFocusables();
      if (nodes.length < 2) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    });
  }

  function initSettingsInputFocus() {
    const modal = F.settingsModal;
    if (!modal || modal.dataset.focusBound === "1") return;
    modal.dataset.focusBound = "1";

    modal.addEventListener(
      "mousedown",
      (event) => {
        const input = event.target.closest?.(
          "input:not([type=checkbox]):not([type=radio]), textarea, select"
        );
        if (!input || !modal.contains(input)) return;
        event.stopPropagation();
        if (document.activeElement !== input) {
          input.focus({ preventScroll: true });
        }
      },
      true
    );
  }

  function normalizeSettingsPanel(panel) {
    const aliases = {
      api: "llm",
      app: "about",
      logs: "about",
      "security-updates": "about",
      migration: "data",
    };
    return aliases[panel] || panel || "llm";
  }

  function openSettings(panel = "llm") {
    settingsReturnFocus = document.activeElement;
    initSettingsInputFocus();
    initSettingsA11y();
    switchSettingsPanel(normalizeSettingsPanel(panel));
    F.settingsModal.classList.remove("hidden");
    F.settingsModal.setAttribute("aria-hidden", "false");
    requestAnimationFrame(() => {
      document.querySelector(".settings-nav-item.active")?.focus();
    });
  }

  function closeSettings() {
    F.settingsModal.classList.add("hidden");
    F.settingsModal.setAttribute("aria-hidden", "true");
    const restore = settingsReturnFocus;
    settingsReturnFocus = null;
    if (restore && typeof restore.focus === "function") {
      restore.focus();
    }
  }

  function switchSettingsPanel(panel) {
    panel = normalizeSettingsPanel(panel);
    document.querySelectorAll(".settings-nav-item").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.panel === panel);
    });
    document.querySelectorAll(".settings-section").forEach((section) => {
      section.classList.toggle("active", section.id === `panel-${panel}`);
    });
    if (panel === "about") {
      void refreshLogPreview();
      void loadAppVersion();
    }
    if (panel === "data") {
      void refreshArtifactSummary();
    }
    if (panel === "agent") {
      void F.refreshPythonEnvStatus?.();
    }
    if (panel === "weixin") {
      void F.refreshWeixinSetup?.();
    }
    syncSettingsTabA11y(panel);
  }

  /* ── 数据移植 / 日志 ── */

  async function refreshLogPreview() {
    const preview = document.getElementById("logPreview");
    const pathHint = document.getElementById("appdataPathHint");
    if (!preview) return;
    try {
      const res = await F.apiFetch("/api/diagnostics/logs?lines=20");
      const data = await res.json();
      if (pathHint && data.path) {
        pathHint.textContent = data.path.replace(/[/\\]friday\.log$/i, "");
      }
      const lines = data.lines || [];
      preview.textContent = lines.length ? lines.join("\n") : F.t("logs.empty");
    } catch {
      preview.textContent = "无法读取日志，请稍后重试。";
    }
  }

  async function openLogFolder() {
    const resultEl = F.logsResult;
    if (window.pywebview?.api?.open_appdata_folder) {
      await window.pywebview.api.open_appdata_folder();
      if (resultEl) {
        resultEl.className = "settings-result ok";
        resultEl.textContent = F.t("logs.opened");
      }
      return;
    }
    try {
      const res = await F.apiFetch("/api/diagnostics/appdata");
      const data = await res.json();
      if (resultEl) {
        resultEl.className = "settings-result";
        resultEl.textContent = `日志目录：${data.path}`;
      }
    } catch {
      if (resultEl) {
        resultEl.className = "settings-result error";
        resultEl.textContent = "无法获取日志目录。";
      }
    }
  }

  /* ── 挂载 ── */

  function initModelStatusPreview() {
    const modelEl = document.getElementById("model");
    const customEl = document.getElementById("llmModelCustom");
    const bind = (el) => {
      if (!el || el.dataset.statusBound === "1") return;
      el.dataset.statusBound = "1";
      el.addEventListener("change", () => {
        const model = (F.collectLlmModel?.() || el.value || "").trim();
        if (!model) return;
        F.patchStatusBar?.({ model, api_checking: true });
      });
      el.addEventListener("input", () => {
        const model = (F.collectLlmModel?.() || el.value || "").trim();
        if (!model) return;
        F.patchStatusBar?.({ model, api_checking: true });
      });
    };
    bind(modelEl);
    bind(customEl);
  }

  initModelStatusPreview();

  F.loadSettings = loadSettings;
  F.openSettings = openSettings;
  F.closeSettings = closeSettings;
  F.switchSettingsPanel = switchSettingsPanel;
  F.refreshLogPreview = refreshLogPreview;
  F.openLogFolder = openLogFolder;

  function formatBytes(n) {
    const num = Number(n) || 0;
    if (num < 1024) return `${num} B`;
    if (num < 1024 * 1024) return `${(num / 1024).toFixed(1)} KB`;
    if (num < 1024 * 1024 * 1024) return `${(num / (1024 * 1024)).toFixed(1)} MB`;
    return `${(num / (1024 * 1024 * 1024)).toFixed(2)} GB`;
  }

  function fillArtifactForm(data) {
    const scratch = document.getElementById("artifactScratchTtlHours");
    const session = document.getElementById("artifactSessionTtlDays");
    const trash = document.getElementById("artifactTrashTtlDays");
    const autoGc = document.getElementById("artifactAutoGcEnabled");
    if (scratch) scratch.value = String(data.artifact_scratch_ttl_hours ?? 24);
    if (session) session.value = String(data.artifact_session_ttl_days ?? 30);
    if (trash) trash.value = String(data.artifact_trash_ttl_days ?? 7);
    if (autoGc) autoGc.checked = data.artifact_auto_gc_enabled !== false;
    void refreshArtifactSummary();
  }

  function artifactIsEmpty(data) {
    if (!data) return false;
    const active = Number(data.indexed_active_count) || 0;
    const trashed = Number(data.indexed_trashed_count) || 0;
    const dirBytes = Number(data.artifacts_dir_bytes) || 0;
    return active === 0 && trashed === 0 && dirBytes === 0;
  }

  function renderArtifactSummary(data) {
    const el = document.getElementById("artifactStorageSummary");
    const emptyEl = document.getElementById("artifactStorageEmpty");
    if (!el || !data) return;

    if (artifactIsEmpty(data)) {
      el.classList.add("hidden");
      emptyEl?.classList.remove("hidden");
      return;
    }

    el.classList.remove("hidden");
    emptyEl?.classList.add("hidden");
    el.textContent =
      `登记中 ${data.indexed_active_count} 个（${formatBytes(data.indexed_active_bytes)}）` +
      ` · 回收站 ${data.indexed_trashed_count} 个（${formatBytes(data.indexed_trashed_bytes)}）` +
      ` · artifacts 目录 ${formatBytes(data.artifacts_dir_bytes)}` +
      ` · trash 目录 ${formatBytes(data.trash_dir_bytes)}`;
  }

  async function refreshArtifactSummary() {
    const el = document.getElementById("artifactStorageSummary");
    const emptyEl = document.getElementById("artifactStorageEmpty");
    if (el) {
      el.classList.remove("hidden");
      el.textContent = F.t("settings.data.artifactsLoading") || "正在加载占用信息…";
    }
    emptyEl?.classList.add("hidden");
    try {
      const res = await F.apiFetch("/api/artifacts/summary");
      if (!res.ok) throw new Error("summary failed");
      const data = await res.json();
      renderArtifactSummary(data);
      return data;
    } catch {
      if (el) {
        el.classList.remove("hidden");
        el.textContent = F.t("settings.data.artifactsLoadError") || "无法加载占用信息。";
      }
      emptyEl?.classList.add("hidden");
      return null;
    }
  }

  async function saveArtifactPolicy() {
    const resultEl = document.getElementById("artifactStorageResult");
    if (resultEl) {
      resultEl.className = "settings-result";
      resultEl.textContent = "保存中…";
    }
    const payload = {
      artifact_scratch_ttl_hours: Number(document.getElementById("artifactScratchTtlHours")?.value || 24),
      artifact_session_ttl_days: Number(document.getElementById("artifactSessionTtlDays")?.value || 30),
      artifact_trash_ttl_days: Number(document.getElementById("artifactTrashTtlDays")?.value || 7),
      artifact_auto_gc_enabled: document.getElementById("artifactAutoGcEnabled")?.checked !== false,
    };
    try {
      const res = await F.apiFetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error("save failed");
      if (resultEl) {
        resultEl.className = "settings-result ok";
        resultEl.textContent = "回收策略已保存。";
      }
      void refreshArtifactSummary();
    } catch {
      if (resultEl) {
        resultEl.className = "settings-result error";
        resultEl.textContent = "保存失败。";
      }
    }
  }

  async function runArtifactGc() {
    const resultEl = document.getElementById("artifactStorageResult");
    if (resultEl) {
      resultEl.className = "settings-result";
      resultEl.textContent = "正在回收…";
    }
    try {
      const res = await F.apiFetch("/api/artifacts/gc", { method: "POST" });
      const data = await res.json();
      if (resultEl) {
        resultEl.className = "settings-result ok";
        resultEl.textContent =
          `已移入回收站 ${data.trashed || 0} 个，永久删除 ${data.purged || 0} 个，释放约 ${formatBytes(data.bytes_freed || 0)}。`;
      }
      void refreshArtifactSummary();
    } catch {
      if (resultEl) {
        resultEl.className = "settings-result error";
        resultEl.textContent = "回收失败。";
      }
    }
  }

  document.getElementById("openLogFolderBtn")?.addEventListener("click", openLogFolder);
  document.getElementById("refreshLogPreviewBtn")?.addEventListener("click", refreshLogPreview);
  document.getElementById("diagnosticsExportBtn")?.addEventListener("click", () => void exportDiagnosticBundle());
  document.getElementById("artifactRefreshSummaryBtn")?.addEventListener("click", () => {
    void refreshArtifactSummary();
  });
  document.getElementById("artifactRunGcBtn")?.addEventListener("click", () => {
    void runArtifactGc();
  });
  document.getElementById("artifactSavePolicyBtn")?.addEventListener("click", () => {
    void saveArtifactPolicy();
  });

  function fillContextSmartForm(data) {
    const smart = document.getElementById("contextSmartEnabled");
    const goal = document.getElementById("goalVerifierEnabled");
    const dream = document.getElementById("dreamMemoryEnabled");
    if (smart) smart.checked = data.context_smart_enabled !== false;
    if (goal) goal.checked = data.goal_verifier_enabled !== false;
    if (dream) dream.checked = !!data.dream_memory_enabled;
  }

  async function loadWorkspaceMemoryEditor() {
    const editor = document.getElementById("workspaceMemoryEditor");
    if (!editor) return;
    try {
      const res = await F.apiFetch("/api/workspace-memory");
      const data = await res.json();
      editor.value = data.content || "";
    } catch {
      editor.value = "";
    }
  }

  function renderUserMemoryList(facts) {
    const list = document.getElementById("userMemoryList");
    if (!list) return;
    list.innerHTML = "";
    if (!facts?.length) {
      const empty = document.createElement("p");
      empty.className = "settings-hint";
      empty.textContent = "暂无长期记忆。";
      list.appendChild(empty);
      return;
    }
    facts.forEach((item) => {
      const row = document.createElement("div");
      row.className = "user-memory-item";
      row.dataset.id = item.id || "";

      const input = document.createElement("input");
      input.type = "text";
      input.maxLength = 240;
      input.value = item.text || "";
      input.dataset.id = item.id || "";

      const saveBtn = document.createElement("button");
      saveBtn.type = "button";
      saveBtn.className = "ghost-btn";
      saveBtn.textContent = "保存";
      saveBtn.addEventListener("click", () => void saveUserMemoryItem(item.id, input.value));

      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.className = "ghost-btn";
      delBtn.textContent = "删除";
      delBtn.addEventListener("click", () => void deleteUserMemoryItem(item.id));

      row.appendChild(input);
      row.appendChild(saveBtn);
      row.appendChild(delBtn);
      list.appendChild(row);
    });
  }

  async function loadUserMemoryList() {
    const resultEl = document.getElementById("userMemoryResult");
    try {
      const res = await F.apiFetch("/api/user-memory");
      const data = await res.json();
      renderUserMemoryList(data.facts || []);
    } catch {
      renderUserMemoryList([]);
      if (resultEl) {
        resultEl.className = "settings-result error";
        resultEl.textContent = "加载用户记忆失败。";
      }
    }
  }

  async function addUserMemoryItem() {
    const input = document.getElementById("userMemoryNewText");
    const resultEl = document.getElementById("userMemoryResult");
    const text = (input?.value || "").trim();
    if (!text) return;
    if (resultEl) resultEl.textContent = "保存中…";
    try {
      const res = await F.apiFetch("/api/user-memory", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.message || "add failed");
      if (input) input.value = "";
      await loadUserMemoryList();
      if (resultEl) {
        resultEl.className = "settings-result ok";
        resultEl.textContent = data.message || "已添加。";
      }
    } catch (err) {
      if (resultEl) {
        resultEl.className = "settings-result error";
        resultEl.textContent = err?.message || "添加失败。";
      }
    }
  }

  async function saveUserMemoryItem(id, text) {
    const resultEl = document.getElementById("userMemoryResult");
    const cleaned = String(text || "").trim();
    if (!id || !cleaned) return;
    try {
      const res = await F.apiFetch(`/api/user-memory/${encodeURIComponent(id)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: cleaned }),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.message || "save failed");
      if (resultEl) {
        resultEl.className = "settings-result ok";
        resultEl.textContent = "已更新。";
      }
    } catch (err) {
      if (resultEl) {
        resultEl.className = "settings-result error";
        resultEl.textContent = err?.message || "保存失败。";
      }
    }
  }

  async function deleteUserMemoryItem(id) {
    const resultEl = document.getElementById("userMemoryResult");
    if (!id) return;
    try {
      const res = await F.apiFetch(`/api/user-memory/${encodeURIComponent(id)}`, {
        method: "DELETE",
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.message || "delete failed");
      await loadUserMemoryList();
      if (resultEl) {
        resultEl.className = "settings-result ok";
        resultEl.textContent = "已删除。";
      }
    } catch (err) {
      if (resultEl) {
        resultEl.className = "settings-result error";
        resultEl.textContent = err?.message || "删除失败。";
      }
    }
  }

  function renderHistorySearchHits(hits, query) {
    const box = document.getElementById("historySearchResults");
    if (!box) return;
    box.innerHTML = "";
    if (!hits?.length) {
      const empty = document.createElement("p");
      empty.className = "settings-hint";
      empty.textContent = query ? `未找到与「${query}」相关的历史消息。` : "请输入关键词。";
      box.appendChild(empty);
      return;
    }
    hits.forEach((hit) => {
      const item = document.createElement("div");
      item.className = "history-search-hit";
      const meta = document.createElement("div");
      meta.className = "history-search-hit-meta";
      const sid = String(hit.session_id || "").slice(0, 12);
      meta.textContent = `${hit.role || "msg"} · 会话 ${sid}…`;
      const body = document.createElement("div");
      const content = String(hit.content || "").trim();
      body.textContent = content.length > 220 ? `${content.slice(0, 217)}…` : content;
      item.appendChild(meta);
      item.appendChild(body);
      box.appendChild(item);
    });
  }

  async function runHistorySearch() {
    const input = document.getElementById("historySearchQuery");
    const resultEl = document.getElementById("historySearchResult");
    const query = (input?.value || "").trim();
    if (!query) {
      renderHistorySearchHits([], "");
      return;
    }
    if (resultEl) resultEl.textContent = "搜索中…";
    try {
      const res = await F.apiFetch(`/api/history/search?q=${encodeURIComponent(query)}&limit=20`);
      const data = await res.json();
      renderHistorySearchHits(data.hits || [], query);
      if (resultEl) {
        resultEl.className = "settings-result ok";
        resultEl.textContent = `找到 ${(data.hits || []).length} 条。`;
      }
    } catch {
      renderHistorySearchHits([], query);
      if (resultEl) {
        resultEl.className = "settings-result error";
        resultEl.textContent = "搜索失败。";
      }
    }
  }

  async function saveWorkspaceMemory() {
    const editor = document.getElementById("workspaceMemoryEditor");
    const resultEl = document.getElementById("workspaceMemoryResult");
    if (!editor) return;
    if (resultEl) resultEl.textContent = "保存中…";
    try {
      const res = await F.apiFetch("/api/workspace-memory", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: editor.value }),
      });
      if (!res.ok) throw new Error("save failed");
      if (resultEl) {
        resultEl.className = "settings-result ok";
        resultEl.textContent = "工作区记忆已保存。";
      }
    } catch {
      if (resultEl) {
        resultEl.className = "settings-result error";
        resultEl.textContent = "保存失败。";
      }
    }
  }

  async function saveContextSmartSettings() {
    const resultEl = document.getElementById("contextSmartResult");
    const payload = {
      context_smart_enabled: document.getElementById("contextSmartEnabled")?.checked !== false,
      goal_verifier_enabled: document.getElementById("goalVerifierEnabled")?.checked !== false,
      dream_memory_enabled: document.getElementById("dreamMemoryEnabled")?.checked === true,
    };
    try {
      const res = await F.apiFetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(String(res.status));
      if (resultEl) {
        resultEl.className = "settings-result success";
        resultEl.textContent = "上下文智能设置已保存。";
      }
    } catch {
      if (resultEl) {
        resultEl.className = "settings-result error";
        resultEl.textContent = "保存失败。";
      }
    }
  }

  document.getElementById("workspaceMemoryReloadBtn")?.addEventListener("click", () => {
    void loadWorkspaceMemoryEditor();
  });
  document.getElementById("workspaceMemorySaveBtn")?.addEventListener("click", () => {
    void saveWorkspaceMemory();
  });
  document.getElementById("userMemoryAddBtn")?.addEventListener("click", () => {
    void addUserMemoryItem();
  });
  document.getElementById("userMemoryNewText")?.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") void addUserMemoryItem();
  });
  document.getElementById("historySearchBtn")?.addEventListener("click", () => {
    void runHistorySearch();
  });
  document.getElementById("historySearchQuery")?.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") void runHistorySearch();
  });
  ["contextSmartEnabled", "goalVerifierEnabled", "dreamMemoryEnabled"].forEach((id) => {
    document.getElementById(id)?.addEventListener("change", () => {
      void saveContextSmartSettings();
    });
  });

  async function exportDiagnosticBundle() {
    const btn = document.getElementById("diagnosticsExportBtn");
    const resultEl = document.getElementById("logsResult");
    if (btn) btn.disabled = true;
    if (resultEl) resultEl.textContent = "正在打包诊断信息…";
    try {
      const res = await F.apiFetch("/api/diagnostics/export", { method: "POST" });
      if (!res.ok) throw new Error(String(res.status));
      const blob = await res.blob();
      const disposition = res.headers.get("Content-Disposition") || "";
      const match = disposition.match(/filename="?([^";]+)"?/i);
      const filename = match?.[1] || "Friday-diagnostic.zip";
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      if (resultEl) {
        resultEl.className = "settings-result ok";
        resultEl.textContent = "诊断包已下载";
      }
    } catch {
      if (resultEl) {
        resultEl.className = "settings-result error";
        resultEl.textContent = "导出诊断包失败";
      }
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  function portableSessionScopeNote(includeSessions) {
    return includeSessions
      ? "将包含对话历史与会话顺序"
      : "不含对话历史（侧栏会话不会迁移）";
  }

  function renderPortableAudit(items) {
    const listEl = document.getElementById("portableAuditList");
    if (!listEl) return;
    listEl.innerHTML = "";
    if (!items?.length) {
      listEl.classList.add("hidden");
      return;
    }
    listEl.classList.remove("hidden");
    const fixPanelById = {
      workspace: "workspace",
      encryption: "llm",
      "python-venv": "workspace",
    };
    items.forEach((item) => {
      const li = document.createElement("li");
      li.className = `portable-audit-item ${item.ok ? "ok" : "error"}`;
      const label = document.createElement("strong");
      label.textContent = item.label || item.id || "检查项";
      const detail = document.createElement("span");
      detail.className = "portable-audit-detail";
      detail.textContent = item.detail || "";
      li.appendChild(label);
      li.appendChild(detail);
      const panel = fixPanelById[String(item.id || "").split("-")[0]] || fixPanelById[item.id];
      if (!item.ok && panel) {
        const fixBtn = document.createElement("button");
        fixBtn.type = "button";
        fixBtn.className = "ghost-btn portable-audit-fix-btn";
        fixBtn.textContent = "去修复";
        fixBtn.addEventListener("click", () => switchSettingsPanel(panel));
        li.appendChild(fixBtn);
      }
      listEl.appendChild(li);
    });
  }

  async function loadPortableAudit() {
    const btn = document.getElementById("portableAuditBtn");
    const reportEl = document.getElementById("portableReport");
    if (btn) btn.disabled = true;
    if (reportEl) reportEl.textContent = "正在自检…";
    try {
      const res = await F.apiFetch("/api/portable/audit");
      const data = await res.json();
      const items = data.items || [];
      renderPortableAudit(items);
      const failed = items.filter((item) => !item.ok).length;
      if (reportEl) {
        reportEl.textContent = failed
          ? `自检完成：${failed} 项需处理`
          : "自检通过，可正常迁移";
      }
    } catch {
      if (reportEl) reportEl.textContent = "自检失败，请稍后重试";
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  async function exportPortableBundle() {
    const btn = document.getElementById("portableExportBtn");
    const resultEl = document.getElementById("logsResult");
    const reportEl = document.getElementById("portableReport");
    const includeSessions = document.getElementById("portableIncludeSessions")?.checked;
    const confirmLines = [
      portableSessionScopeNote(!!includeSessions),
      "不含微信扫码登录态，新机需重新配置微信端 AI",
      "请一并拷贝默认操作文件夹（Documents/星期五 等）",
    ];
    if (!window.confirm(`确认导出配置包？\n\n${confirmLines.join("\n")}`)) return;
    if (btn) btn.disabled = true;
    if (resultEl) resultEl.textContent = "正在打包…";
    try {
      const res = await F.apiFetch("/api/portable/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ include_sessions: !!includeSessions }),
      });
      if (!res.ok) throw new Error(String(res.status));
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "Friday-portable.zip";
      a.click();
      URL.revokeObjectURL(url);
      if (resultEl) {
        resultEl.className = "settings-result ok";
        resultEl.textContent = "配置包已下载";
      }
      if (reportEl) {
        reportEl.textContent = [
          "导出完成",
          portableSessionScopeNote(!!includeSessions),
          "已包含：设置、技能、规则、插件、定时任务",
        ].join("\n");
      }
    } catch {
      if (resultEl) {
        resultEl.className = "settings-result error";
        resultEl.textContent = "导出失败";
      }
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  async function importPortableBundle(file) {
    const resultEl = document.getElementById("logsResult");
    const reportEl = document.getElementById("portableReport");
    const includeSessions = document.getElementById("portableIncludeSessions")?.checked;
    if (!file) return;
    const confirmLines = [
      "将覆盖本机 AppData 配置（失败会自动回滚，成功前会备份）",
      portableSessionScopeNote(!!includeSessions),
      "导入后建议重启应用",
    ];
    if (!window.confirm(`确认导入配置包？\n\n${confirmLines.join("\n")}`)) return;
    if (resultEl) resultEl.textContent = "正在导入…";
    try {
      const zipBase64 = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
          const dataUrl = String(reader.result || "");
          resolve(dataUrl.split(",", 2)[1] || "");
        };
        reader.onerror = () => reject(new Error("读取文件失败"));
        reader.readAsDataURL(file);
      });
      const res = await F.apiFetch("/api/portable/import", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          zip_base64: zipBase64,
          filename: file.name || "Friday-portable.zip",
          include_sessions: !!includeSessions,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || String(res.status));
      const lines = [
        `已导入 ${(data.imported || []).length} 项`,
        data.backup_dir ? `备份：${data.backup_dir}` : "",
        ...(data.warnings || []),
      ].filter(Boolean);
      if (reportEl) reportEl.textContent = lines.join("\n");
      if (resultEl) {
        resultEl.className = "settings-result ok";
        resultEl.textContent = "导入完成，建议重启应用";
      }
      await loadSettings();
      await loadPortableAudit();
    } catch (err) {
      if (resultEl) {
        resultEl.className = "settings-result error";
        resultEl.textContent = err.message || "导入失败";
      }
    }
  }

  document.getElementById("portableAuditBtn")?.addEventListener("click", () => void loadPortableAudit());

  document.getElementById("portableExportBtn")?.addEventListener("click", () => void exportPortableBundle());
  document.getElementById("portableImportBtn")?.addEventListener("click", () => {
    document.getElementById("portableImportInput")?.click();
  });
  document.getElementById("portableImportInput")?.addEventListener("change", (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    void importPortableBundle(file);
  });

  document.querySelectorAll(".settings-goto-panel").forEach((btn) => {
    btn.addEventListener("click", () => {
      const panel = btn.dataset.gotoPanel;
      if (panel) switchSettingsPanel(panel);
    });
  });

  document.getElementById("refreshPythonEnvBtn")?.addEventListener("click", () => void F.refreshPythonEnvStatus?.());
  document.getElementById("setupPythonEnvBtn")?.addEventListener("click", () => void F.setupPythonEnv?.());

  function renderRuntimeAbout(data) {
    const statusEl = document.getElementById("runtimeAboutStatus");
    const hintEl = document.getElementById("runtimeAboutHint");
    if (!statusEl) return;
    if (!data) {
      statusEl.textContent = "无法加载运行信息。";
      if (hintEl) hintEl.classList.add("hidden");
      return;
    }
    const lines = [
      data.run_mode_label ? `运行模式：${data.run_mode_label}` : "",
      data.main_process_name ? `主进程：${data.main_process_name}` : "",
      data.main_executable ? `路径：${data.main_executable}` : "",
      data.pid != null ? `PID：${data.pid}` : "",
      data.agent_runner_name ? `Agent 解释器：${data.agent_runner_name}` : "",
      data.agent_runner && data.agent_runner !== data.main_executable
        ? `Agent 路径：${data.agent_runner}`
        : "",
    ].filter(Boolean);
    statusEl.textContent = lines.join("\n") || "—";
    if (!hintEl) return;
    const hint = data.task_manager_hint || "";
    if (!hint) {
      hintEl.classList.add("hidden");
      hintEl.textContent = "";
      return;
    }
    hintEl.textContent = hint;
    hintEl.classList.remove("hidden");
    hintEl.classList.toggle("settings-hint-warn", data.run_mode === "dev");
  }

  async function loadAppVersion() {
    const label = document.getElementById("appVersionLabel");
    const sourceLink = document.getElementById("updateSourceLink");
    const statusEl = document.getElementById("runtimeAboutStatus");
    if (statusEl && !statusEl.dataset.loaded) {
      statusEl.textContent = "加载中…";
    }
    try {
      const res = await F.apiFetch("/api/version");
      const data = await res.json();
      if (label) label.textContent = data.version || "—";
      if (sourceLink) {
        if (data.gitee_pages_home) {
          sourceLink.href = data.gitee_pages_home;
          sourceLink.textContent = "官网（国内）";
        } else if (data.website_home) {
          sourceLink.href = data.website_home;
          sourceLink.textContent = "官网下载";
        } else if (data.gitee_home) {
          sourceLink.href = `${data.gitee_home}/releases`;
          sourceLink.textContent = "Gitee Releases";
        }
      }
      renderRuntimeAbout(data);
      if (statusEl) statusEl.dataset.loaded = "1";
    } catch {
      if (label) label.textContent = "—";
      renderRuntimeAbout(null);
    }
  }

  let lastUpdateInfo = null;
  let updatePollTimer = null;

  function formatUpdateFailure(data) {
    if (!data) return "更新失败，请稍后重试或使用「手动下载」。";
    if (F.formatErrorResult) {
      const merged = {
        message: data.result_message || data.message || data.detail || "",
        hint: data.hint || "",
        detail: data.detail || "",
      };
      const text = F.formatErrorResult(merged);
      if (text && text !== "未知错误") return text;
    }
    const parts = [];
    const main = data.result_message || data.message || "";
    const detail = data.detail || "";
    const hint = data.hint || "";
    if (main) parts.push(main);
    if (detail && detail !== main) parts.push(detail);
    if (hint && !parts.join("\n").includes(hint)) parts.push(hint);
    const log = Array.isArray(data.log) ? data.log.filter(Boolean) : [];
    if (log.length) {
      const tail = log[log.length - 1];
      if (tail && !parts.join("\n").includes(tail)) parts.push(`最近步骤：${tail}`);
    }
    return parts.filter(Boolean).join("\n") || "更新失败，请稍后重试或使用「手动下载」。";
  }

  /** 当前阶段进度（与 detail 文案一致）；percent 为全链路权重，下载时会对不上 MB。 */
  function resolveUpdateDisplayPercent(data) {
    const phase = data?.phase;
    const detail = String(data?.detail || "");
    if (phase === "downloading") {
      const mb = detail.match(/([\d.]+)\s*\/\s*([\d.]+)\s*MB/i);
      if (mb) {
        const read = parseFloat(mb[1]);
        const total = parseFloat(mb[2]);
        if (total > 0 && Number.isFinite(read)) {
          return Math.max(0, Math.min(100, Math.round((read / total) * 100)));
        }
      }
    }
    if (phase === "extracting") {
      const parts = detail.match(/(\d+)\s*\/\s*(\d+)/);
      if (parts) {
        const cur = parseInt(parts[1], 10);
        const total = parseInt(parts[2], 10);
        if (total > 0) {
          return Math.max(0, Math.min(100, Math.round((cur / total) * 100)));
        }
      }
    }
    return Math.max(0, Math.min(100, Number(data?.percent) || 0));
  }

  function renderUpdateProgress(data) {
    const wrap = document.getElementById("updateProgress");
    const fill = document.getElementById("updateProgressFill");
    const pctEl = document.getElementById("updateProgressPct");
    const msgEl = document.getElementById("updateProgressMsg");
    const detailEl = document.getElementById("updateProgressDetail");
    if (!wrap || !fill || !pctEl || !msgEl) return;
    const running = !!data?.running;
    if (!running && data?.ok === true) {
      wrap.classList.add("hidden");
      return;
    }
    const pct = resolveUpdateDisplayPercent(data);
    wrap.classList.remove("hidden");
    fill.style.width = `${pct}%`;
    fill.style.setProperty("--progress", `${pct}%`);
    pctEl.textContent = `${pct}%`;
    msgEl.textContent = data?.message || (running ? "正在更新…" : "");
    if (detailEl) {
      detailEl.textContent = data?.detail || "";
      detailEl.style.display = data?.detail ? "block" : "none";
    }
  }

  function stopUpdatePoll() {
    if (updatePollTimer) {
      clearInterval(updatePollTimer);
      updatePollTimer = null;
    }
  }

  async function pollUpdateApplyProgress() {
    try {
      const res = await F.apiFetchWithTimeout("/api/updates/apply/progress", {}, 15000);
      const data = await res.json();
      renderUpdateProgress(data);
      const resultEl = document.getElementById("updateResult");
      if (data.running && resultEl) {
        resultEl.className = "settings-result";
        resultEl.textContent = [data.message, data.detail].filter(Boolean).join(" · ");
      }
      if (!data.running) {
        stopUpdatePoll();
        const applyBtn = document.getElementById("applyUpdateBtn");
        const checkBtn = document.getElementById("checkUpdateBtn");
        if (applyBtn) applyBtn.disabled = false;
        if (checkBtn) checkBtn.disabled = false;
        if (data.ok === true) {
          if (resultEl) {
            resultEl.className = "settings-result ok";
            resultEl.textContent = data.result_message || data.message || "更新完成，正在重启…";
          }
          window.setTimeout(() => {
            try {
              window.pywebview?.api?.close_window?.();
            } catch {
              /* 后端 force exit 为主；此处仅作 UI 兜底 */
            }
          }, 400);
          return false;
        }
        if (data.ok === false && resultEl) {
          resultEl.className = "settings-result error";
          resultEl.textContent = formatUpdateFailure(data);
        }
        document.getElementById("updateProgress")?.classList.add("hidden");
        return false;
      }
      return true;
    } catch (err) {
      const resultEl = document.getElementById("updateResult");
      if (resultEl) {
        resultEl.className = "settings-result error";
        resultEl.textContent = err?.name === "AbortError"
          ? "读取更新进度超时，请查看是否已在后台下载；若长时间无响应请重试。"
          : `无法获取更新进度：${err?.message || "网络异常"}`;
      }
      return false;
    }
  }

  function startUpdatePoll() {
    stopUpdatePoll();
    void pollUpdateApplyProgress();
    updatePollTimer = setInterval(() => {
      void pollUpdateApplyProgress();
    }, 800);
  }

  async function startApplyUpdate(info, options = {}) {
    const requireConfirm = options.requireConfirm !== false;
    if (!info?.update_available || !info.download_url) return false;
    if (!info.can_auto_update) {
      const resultEl = document.getElementById("updateResult");
      if (resultEl) {
        resultEl.className = "settings-result error";
        resultEl.textContent = info.auto_update_hint || "当前环境不支持一键更新，请使用手动下载。";
      }
      return false;
    }
    if (requireConfirm) {
      const confirmed = window.confirm(
        `即将下载并安装版本 ${info.latest}，完成后会自动重启星期五。\n\n更新过程中请勿关闭电脑，是否继续？`,
      );
      if (!confirmed) return false;
    }
    lastUpdateInfo = info;

    const applyBtn = document.getElementById("applyUpdateBtn");
    const checkBtn = document.getElementById("checkUpdateBtn");
    const resultEl = document.getElementById("updateResult");
    if (applyBtn) applyBtn.disabled = true;
    if (checkBtn) checkBtn.disabled = true;
    if (resultEl) {
      resultEl.className = "settings-result";
      resultEl.textContent = "正在准备更新…";
    }
    renderUpdateProgress({
      running: true,
      phase: "starting",
      percent: 0,
      message: "正在启动更新…",
      detail: "下载完成后将自动替换程序并重启",
    });
    try {
      const res = await F.apiFetchWithTimeout("/api/updates/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          download_url: info.download_url,
          version: info.latest,
          expected_sha256: info.download_sha256 || "",
        }),
      }, 30000);
      const data = await res.json().catch(() => ({}));
      if (!data.started) {
        if (resultEl) {
          resultEl.className = "settings-result error";
          resultEl.textContent = formatUpdateFailure(data);
        }
        document.getElementById("updateProgress")?.classList.add("hidden");
        if (applyBtn) applyBtn.disabled = false;
        if (checkBtn) checkBtn.disabled = false;
        return false;
      }
      if (data.already_running) {
        if (resultEl) resultEl.textContent = "更新已在进行中…";
      }
      startUpdatePoll();
    } catch (err) {
      if (resultEl) {
        resultEl.className = "settings-result error";
        resultEl.textContent = err?.name === "AbortError"
          ? "启动更新超时，请检查网络后重试。"
          : `无法启动更新：${err?.message || "请确认星期五后端正在运行"}`;
      }
      document.getElementById("updateProgress")?.classList.add("hidden");
      if (applyBtn) applyBtn.disabled = false;
      if (checkBtn) checkBtn.disabled = false;
      return false;
    }
    return true;
  }

  async function applyUpdate() {
    let info = lastUpdateInfo;
    if (!info?.update_available || !info.download_url || !info.download_sha256) {
      await checkForUpdates();
      info = lastUpdateInfo;
    }
    if (!info?.update_available || !info.download_url) return;
    if (!info.download_sha256) {
      const resultEl = document.getElementById("updateResult");
      if (resultEl) {
        resultEl.className = "settings-result error";
        resultEl.textContent = info.auto_update_hint
          || "无法获取更新包校验信息（SHA256）。请检查网络后重新「检查更新」，或手动下载安装包。";
      }
      return;
    }
    await startApplyUpdate(info);
  }

  async function checkForUpdates() {
    const resultEl = document.getElementById("updateResult");
    const downloadLink = document.getElementById("downloadUpdateLink");
    const applyBtn = document.getElementById("applyUpdateBtn");
    const sourceLink = document.getElementById("updateSourceLink");
    if (resultEl) {
      resultEl.className = "settings-result";
      resultEl.textContent = F.t("updates.checking");
    }
    applyBtn?.classList.add("hidden");
    try {
      const res = await F.apiFetch("/api/updates/check");
      const data = await res.json();
      lastUpdateInfo = data;
      if (data.last_apply_failed && data.last_apply_hint && resultEl) {
        resultEl.className = "settings-result error";
        resultEl.textContent = data.last_apply_hint;
      }
      if (!data.checked) {
        if (resultEl) resultEl.textContent = "无法读取更新源配置";
        downloadLink?.classList.add("hidden");
        return;
      }
      if (data.update_available) {
        if (resultEl) {
          resultEl.className = "settings-result ok";
          const hint = data.can_auto_update
            ? "可点「一键更新并重启」自动完成，无需手动解压。"
            : (data.auto_update_hint || data.manual_download_hint || "请下载安装程序 Friday-Setup 后运行。");
          resultEl.textContent = `${F.t("updates.found", { latest: data.latest, current: data.current })}\n${hint}`;
        }
        if (applyBtn && data.can_auto_update && data.download_url && data.download_sha256) {
          applyBtn.classList.remove("hidden");
        }
        if (downloadLink) {
          const manualUrl = data.manual_download_url || data.download_url;
          if (manualUrl) {
            downloadLink.href = manualUrl;
            downloadLink.classList.remove("hidden");
            downloadLink.title = data.manual_download_hint || "";
          } else {
            downloadLink.classList.add("hidden");
          }
        }
      } else if (data.release_notes && data.latest === data.current && !data.download_url) {
        if (resultEl) {
          const isError = /无法|暂无|不可达|失败/.test(data.release_notes);
          resultEl.className = isError ? "settings-result error" : "settings-result ok";
          resultEl.textContent = isError ? data.release_notes : `已是最新版本 ${data.current}`;
        }
        downloadLink?.classList.add("hidden");
      } else {
        if (resultEl) {
          resultEl.className = "settings-result ok";
          resultEl.textContent = F.t("updates.latest", { version: data.current });
        }
        downloadLink?.classList.add("hidden");
      }
      if (sourceLink && data.source_url) {
        const kind = data.source_kind === "github" ? "GitHub Releases" : "Gitee Releases";
        sourceLink.href = data.source_kind === "github"
          ? `${data.source_url}/releases`
          : `${data.source_url}/releases`;
        sourceLink.textContent = kind;
      }
    } catch (err) {
      if (resultEl) {
        resultEl.className = "settings-result error";
        resultEl.textContent = err?.name === "AbortError"
          ? "检查更新超时，请检查网络后重试。"
          : F.t("updates.fail");
      }
    }
  }

  F.checkForUpdates = checkForUpdates;
  F.startApplyUpdate = startApplyUpdate;

  document.getElementById("checkUpdateBtn")?.addEventListener("click", checkForUpdates);
  document.getElementById("applyUpdateBtn")?.addEventListener("click", () => void applyUpdate());
  document.getElementById("launchAtLogon")?.addEventListener("change", (event) => {
    void F.toggleAutostart?.(event.target.checked);
  });
  document.getElementById("viewChangelogBtn")?.addEventListener("click", () => {
    void F.showChangelogHistory?.();
  });
  loadAppVersion();
})();
