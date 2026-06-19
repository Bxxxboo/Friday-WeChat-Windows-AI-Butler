/* ================================================================= *
 *  settings-providers.js — 大模型 / 视觉 / 生图 保存与测试
 *  依赖 utils.js / window.Friday
 * ================================================================= */

(function () {
  "use strict";

  const F = window.Friday;
  if (!F) { console.error("settings-providers.js: window.Friday 未初始化"); return; }

  /* ── 保存 ── */

  function collectNetworkSettings() {
    return {
      api_proxy: document.getElementById("apiProxy")?.value.trim() || "",
      api_trust_env: document.getElementById("apiTrustEnv")?.checked !== false,
    };
  }

  function collectSettings() {
    return {
      ...collectNetworkSettings(),
      ...F.collectCustomPayload?.("llm"),
      llm_provider: document.getElementById("llmProvider")?.value || "deepseek",
      api_key: document.getElementById("apiKey").value.trim(),
      base_url: document.getElementById("baseUrl").value.trim(),
      model: F.collectLlmModel?.() || document.getElementById("model")?.value || "",
      workspace: document.getElementById("workspace").value.trim(),
    };
  }

  function collectVisionSettings() {
    return {
      ...collectNetworkSettings(),
      ...F.collectCustomPayload?.("vision"),
      vision_enabled: document.getElementById("visionEnabled").checked,
      vision_provider: document.getElementById("visionProvider")?.value || "ark",
      vision_api_key: document.getElementById("visionApiKey").value.trim(),
      vision_base_url: document.getElementById("visionBaseUrl").value.trim(),
      vision_model: F.collectVisionModel?.() || "",
    };
  }

  function collectImageGenSettings() {
    return {
      ...collectNetworkSettings(),
      ...F.collectCustomPayload?.("image_gen"),
      image_gen_enabled: document.getElementById("imageGenEnabled").checked,
      image_gen_provider: document.getElementById("imageGenProvider").value,
      image_gen_api_key: document.getElementById("imageGenApiKey").value.trim(),
      image_gen_base_url: document.getElementById("imageGenBaseUrl").value.trim(),
      image_gen_fallback_urls: document.getElementById("imageGenFallbackUrls").value.trim(),
      image_gen_model: F.collectImageGenModel?.() || document.getElementById("imageGenModel")?.value.trim() || "",
    };
  }

  function updateImageGenStatus(ready, enabled, statusHint = "", verified = false) {
    const pill = document.getElementById("imageGenStatus");
    if (!pill) return;
    if (!enabled) {
      pill.textContent = "生图未启用";
      pill.classList.remove("ready");
      return;
    }
    if (verified) {
      pill.textContent = "生图 API 已验证";
      pill.classList.add("ready");
      return;
    }
    if (ready) {
      pill.textContent = "已配置 · 待测试";
      pill.classList.add("ready");
    } else {
      pill.textContent = statusHint || "生图 API 未配置";
      pill.classList.remove("ready");
    }
  }

  function onImageGenProviderChangeLegacy() {
    /* providers.js 已接管生图服务商切换 */
  }

  function updateVisionStatus(ready, enabled, statusHint = "", verified = false) {
    const pill = document.getElementById("visionStatus");
    if (!pill) return;
    if (!enabled) {
      pill.textContent = "视觉辅助未启用";
      pill.classList.remove("ready");
      window.Friday?.refreshStatusBar?.();
      return;
    }
    if (verified) {
      pill.textContent = "视觉 API 已验证";
      pill.classList.add("ready");
      window.Friday?.refreshStatusBar?.();
      return;
    }
    if (ready) {
      pill.textContent = "已配置 · 待测试";
      pill.classList.add("ready");
    } else {
      pill.textContent = statusHint || "视觉 API 未配置";
      pill.classList.remove("ready");
    }
    window.Friday?.refreshStatusBar?.();
  }

  function applyVisionKeyHint(data) {
    const hint = document.getElementById("visionApiKeyHint");
    if (!hint) return;
    const masked = data?.vision_api_key_masked;
    const base = masked ? `当前已保存: ${masked}` : "尚未保存视觉 API Key";
    const statusHint = data?.vision_status_hint || "";
    if (statusHint.includes("Key 格式不匹配")) {
      hint.textContent = `${base} · 火山方舟请改用 ark- 开头的 Key`;
      hint.classList.add("settings-hint-warn");
      return;
    }
    hint.classList.remove("settings-hint-warn");
    hint.textContent = base;
  }

  async function saveSettings(event) {
    event.preventDefault();
    F.settingsResult.className = "settings-result";
    F.settingsResult.textContent = "保存中...";
    const payload = collectSettings();
    const res = await F.apiFetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    document.getElementById("apiKey").value = "";
    document.getElementById("apiKeyHint").textContent = `当前已保存: ${data.api_key_masked}`;
    F.apiReady = data.api_ready;
    F.updateApiStatus(data.api_ready);
    await F.initProviders?.(data);
    F.settingsResult.className = "settings-result ok";
    F.settingsResult.textContent = "设置已保存。";
    F.updateInputState();
    F.syncStatusBarAfterSettingsSave?.(data);
  }

  async function pickWorkspaceFolder() {
    const input = document.getElementById("workspace");
    const btn = document.getElementById("pickWorkspaceBtn");
    F.workspaceResult.className = "settings-result";
    F.workspaceResult.textContent = "";

    if (!window.pywebview?.api?.pick_folder) {
      F.workspaceResult.className = "settings-result error";
      F.workspaceResult.textContent =
        "文件夹选择仅在桌面客户端（星期五.exe 或 python run.py）中可用。请直接在输入框填写路径，例如 D:/Documents/星期五，再点「保存」。";
      return;
    }

    if (btn) btn.disabled = true;
    F.workspaceResult.textContent = "正在打开文件夹选择…";

    try {
      const path = await window.pywebview.api.pick_folder(input.value.trim());
      if (path) {
        input.value = path;
        F.workspaceResult.className = "settings-result ok";
        F.workspaceResult.textContent = "已选择目录，请点击「保存」。";
      } else {
        F.workspaceResult.className = "settings-result";
        F.workspaceResult.textContent =
          "未选择文件夹（可能已取消）。也可直接在输入框填写路径，例如 D:/Documents/星期五，再点「保存」。";
      }
    } catch {
      F.workspaceResult.className = "settings-result error";
      F.workspaceResult.textContent =
        "打开文件夹选择器失败。请直接在输入框填写路径，例如 D:/Documents/星期五，再点「保存」。";
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  async function saveWorkspace(event) {
    event.preventDefault();
    F.workspaceResult.className = "settings-result";
    F.workspaceResult.textContent = "保存中...";
    const payload = {
      workspace: document.getElementById("workspace").value.trim(),
    };
    const res = await F.apiFetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    document.getElementById("workspace").value = data.workspace;
    F.workspaceResult.className = "settings-result ok";
    F.workspaceResult.textContent = "默认文件夹已保存。";
  }

  async function saveAppearanceSettings(event) {
    event.preventDefault();
    F.appearanceResult.className = "settings-result";
    F.appearanceResult.textContent = F.t("appearance.saving");
    const payload = {
      ui_language: document.getElementById("uiLanguage")?.value || "zh",
      theme: document.getElementById("themeMode").value,
      font_size: document.getElementById("fontSize").value,
    };
    const res = await F.apiFetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    F.applyUiSettings?.(data);
    F.appearanceResult.className = "settings-result ok";
    F.appearanceResult.textContent = F.t("appearance.saved");
  }

  async function saveSecuritySettings(event) {
    event.preventDefault();
    F.securityResult.className = "settings-result";
    F.securityResult.textContent = "保存中...";
    const res = await F.apiFetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(F.collectSecuritySettings?.() || {}),
    });
    if (!res.ok) {
      F.securityResult.className = "settings-result error";
      F.securityResult.textContent = "保存失败，请重试。";
      return;
    }
    const data = await res.json();
    F.fillSecurityForm?.(data);
    F.securityResult.className = "settings-result ok";
    F.securityResult.textContent = "安全设置已保存。";
  }

  async function testSettings() {
    F.settingsResult.className = "settings-result";
    F.settingsResult.textContent = "测试连接中...";
    const payload = collectSettings();
    const res = await F.apiFetchWithTimeout("/api/settings/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }, 60000);
    const data = await res.json();
    F.applyApiTestResult?.(F.settingsResult, data);
    if (data.ok) F.updateApiStatus(true);
    void F.refreshStatusBar?.();
  }

  function formatDiagnoseReport(report) {
    const sections = [
      ["对话大模型", report.llm],
      ["视觉 API", report.vision],
      ["生图 API", report.image_gen],
    ];
    const lines = [];
    for (const [title, block] of sections) {
      if (!block || !Array.isArray(block.steps) || !block.steps.length) continue;
      lines.push(`【${title}】${block.ok ? " ✓" : " ✗"}`);
      for (const step of block.steps) {
        const mark = step.ok ? "✓" : "✗";
        lines.push(`  ${mark} ${step.name}: ${step.detail}`);
        if (!step.ok && step.hint) lines.push(`     → ${step.hint}`);
      }
      lines.push("");
    }
    return lines.join("\n").trim();
  }

  async function diagnoseNetworkSettings() {
    F.settingsResult.className = "settings-result";
    F.settingsResult.textContent = "正在诊断网络（DNS / TCP / SSL）…";
    const payload = {
      ...collectSettings(),
      ...collectVisionSettings(),
      ...collectImageGenSettings(),
    };
    try {
      const res = await F.apiFetchWithTimeout("/api/settings/diagnose?full_api=false", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }, 90000);
      const data = await res.json();
      const text = formatDiagnoseReport(data);
      const allOk = data.llm?.ok && (!payload.vision_enabled || data.vision?.ok) && (!payload.image_gen_enabled || data.image_gen?.ok);
      F.settingsResult.className = allOk ? "settings-result ok" : "settings-result error";
      F.settingsResult.textContent = text || "诊断完成，无可用结果";
      void F.refreshStatusBar?.();
    } catch (err) {
      F.settingsResult.className = "settings-result error";
      F.settingsResult.textContent = `诊断请求失败：${err?.message || err}`;
    }
  }

  async function saveVisionSettings(event) {
    event.preventDefault();
    const resultEl = document.getElementById("visionResult");
    if (resultEl) {
      resultEl.className = "settings-result";
      resultEl.textContent = "保存中...";
    }
    const payload = collectVisionSettings();
    const res = await F.apiFetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      if (resultEl) {
        resultEl.className = "settings-result error";
        resultEl.textContent = F.formatApiErrorResponse?.(res, data) || "保存失败，请重试。";
      }
      return;
    }
    document.getElementById("visionApiKey").value = "";
    applyVisionKeyHint(data);
    updateVisionStatus(data.vision_ready, data.vision_enabled, data.vision_status_hint);
    await F.initProviders?.(data);
    if (resultEl) {
      resultEl.className = "settings-result ok";
      resultEl.textContent = "视觉设置已保存。";
    }
    F.syncStatusBarAfterSettingsSave?.(data);
  }

  async function testVisionSettings() {
    const resultEl = document.getElementById("visionResult");
    if (resultEl) {
      resultEl.className = "settings-result";
      resultEl.textContent = "测试视觉 API 中...";
    }
    const payload = collectVisionSettings();
    if (!payload.vision_enabled) {
      if (resultEl) {
        resultEl.className = "settings-result error";
        resultEl.textContent = "请先勾选「启用视觉辅助」。";
      }
      updateVisionStatus(false, false);
      return;
    }
    const res = await F.apiFetch("/api/settings/test-vision", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok) {
      if (res.status === 401) {
        await F.ensureApiToken?.();
      }
      if (resultEl) {
        resultEl.className = "settings-result error";
        resultEl.textContent = F.formatApiErrorResponse?.(res, data, { service: "视觉 API", context: "vision" })
          || F.formatErrorResult?.(data)
          || data.message
          || "视觉 API 测试失败";
      }
      const hint = payload.vision_provider === "ark" && payload.vision_api_key?.startsWith("sk-")
        ? "Key 格式不匹配：火山方舟需 ark- 开头"
        : (data.message || "");
      updateVisionStatus(false, payload.vision_enabled, hint);
      void F.refreshStatusBar?.();
      return;
    }

    const saveRes = await F.apiFetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const saved = await saveRes.json();
    document.getElementById("visionApiKey").value = "";
    applyVisionKeyHint(saved);
    updateVisionStatus(saved.vision_ready, saved.vision_enabled, saved.vision_status_hint, true);
    await F.initProviders?.(saved);
    if (resultEl) {
      resultEl.className = "settings-result ok";
      resultEl.textContent = `${data.message}（已自动保存，对话中可识图）`;
    }
    F.syncStatusBarAfterSettingsSave?.(saved);
  }

  async function saveImageGenSettings(event) {
    event.preventDefault();
    const resultEl = document.getElementById("imageGenResult");
    if (resultEl) {
      resultEl.className = "settings-result";
      resultEl.textContent = "保存中...";
    }
    const payload = collectImageGenSettings();
    const res = await F.apiFetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    document.getElementById("imageGenApiKey").value = "";
    document.getElementById("imageGenApiKeyHint").textContent = data.image_gen_api_key_masked
      ? `当前已保存: ${data.image_gen_api_key_masked}`
      : "尚未保存生图 API Key";
    updateImageGenStatus(
      data.image_gen_ready,
      data.image_gen_enabled,
      data.image_gen_status_hint || "",
    );
    await F.initProviders?.(data);
    if (resultEl) {
      resultEl.className = "settings-result ok";
      resultEl.textContent = "生图设置已保存。";
    }
    F.syncStatusBarAfterSettingsSave?.(data);
  }

  async function testImageGenSettings() {
    const resultEl = document.getElementById("imageGenResult");
    const btn = document.getElementById("testImageGenBtn");
    if (btn) btn.disabled = true;
    if (resultEl) {
      resultEl.className = "settings-result";
      resultEl.textContent = "正在验证生图端点与模型（约需半分钟至 2 分钟）…";
    }
    const payload = collectImageGenSettings();
    if (!payload.image_gen_enabled) {
      if (resultEl) {
        resultEl.className = "settings-result error";
        resultEl.textContent = "请先勾选「启用生图」。";
      }
      updateImageGenStatus(false, false);
      if (btn) btn.disabled = false;
      return;
    }
    if (!payload.image_gen_model) {
      if (resultEl) {
        resultEl.className = "settings-result error";
        resultEl.textContent = "请先填写生图模型名称。";
      }
      updateImageGenStatus(false, payload.image_gen_enabled, "请填写生图模型名称");
      if (btn) btn.disabled = false;
      return;
    }
    try {
      const res = await F.apiFetchWithTimeout("/api/settings/test-image-gen", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }, 180000);
      const data = await res.json();
      if (!data.ok) {
        F.applyApiTestResult?.(resultEl, data);
        updateImageGenStatus(false, payload.image_gen_enabled, "测试未通过");
        return;
      }

      const saveRes = await F.apiFetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const saved = await saveRes.json();
      document.getElementById("imageGenApiKey").value = "";
      document.getElementById("imageGenApiKeyHint").textContent = saved.image_gen_api_key_masked
        ? `当前已保存: ${saved.image_gen_api_key_masked}`
        : "尚未保存生图 API Key";
      updateImageGenStatus(saved.image_gen_ready, saved.image_gen_enabled, "", true);
      await F.initProviders?.(saved);
      if (resultEl) {
        resultEl.className = "settings-result ok";
        resultEl.textContent = `${data.message}（已自动保存）`;
      }
      F.syncStatusBarAfterSettingsSave?.(saved);
    } catch (err) {
      const timedOut = err?.name === "AbortError";
      if (resultEl) {
        resultEl.className = "settings-result error";
        resultEl.textContent = timedOut
          ? "生图测试超时（3 分钟）。端点可能响应过慢或不可达，请检查 Base URL 与模型名。"
          : "生图测试失败，请确认星期五后端已启动并重试。";
      }
      updateImageGenStatus(false, payload.image_gen_enabled, timedOut ? "测试超时" : "测试失败");
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  F.collectNetworkSettings = collectNetworkSettings;
  F.collectSettings = collectSettings;
  F.collectVisionSettings = collectVisionSettings;
  F.collectImageGenSettings = collectImageGenSettings;
  F.saveSettings = saveSettings;
  F.pickWorkspaceFolder = pickWorkspaceFolder;
  F.saveWorkspace = saveWorkspace;
  F.saveAppearanceSettings = saveAppearanceSettings;
  F.saveSecuritySettings = saveSecuritySettings;
  F.testSettings = testSettings;
  F.diagnoseNetworkSettings = diagnoseNetworkSettings;
  F.saveVisionSettings = saveVisionSettings;
  F.testVisionSettings = testVisionSettings;
  F.updateVisionStatus = updateVisionStatus;
  F.applyVisionKeyHint = applyVisionKeyHint;
  F.updateImageGenStatus = updateImageGenStatus;
  F.saveImageGenSettings = saveImageGenSettings;
  F.testImageGenSettings = testImageGenSettings;
  F.onImageGenProviderChangeLegacy = onImageGenProviderChangeLegacy;

})();
