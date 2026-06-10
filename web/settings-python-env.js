/* settings-python-env.js — 设置页 Python 环境面板 */

(function () {
  "use strict";

  const F = window.Friday;
  if (!F) return;

  let pythonEnvPollTimer = null;

  function hidePythonEnvProgress({ clearResult = false } = {}) {
    document.getElementById("pythonEnvProgress")?.classList.add("hidden");
    if (clearResult) {
      const resultEl = document.getElementById("pythonEnvResult");
      if (resultEl) {
        resultEl.textContent = "";
        resultEl.className = "settings-result";
      }
    }
  }

  function renderPythonEnvProgress(data) {
    const wrap = document.getElementById("pythonEnvProgress");
    const fill = document.getElementById("pythonEnvProgressFill");
    const pctEl = document.getElementById("pythonEnvProgressPct");
    const msgEl = document.getElementById("pythonEnvProgressMsg");
    const detailEl = document.getElementById("pythonEnvProgressDetail");
    const logEl = document.getElementById("pythonEnvProgressLog");
    const statusEl = document.getElementById("pythonEnvStatus");
    const resultEl = document.getElementById("pythonEnvResult");

    const running = !!data?.running;
    if (!running && data?.ok === true) {
      hidePythonEnvProgress({ clearResult: true });
      return;
    }

    const pct = Math.max(0, Math.min(100, Number(data?.percent) || 0));
    const message = data?.message || (running ? "正在初始化…" : "");
    const detail = data?.detail || "";
    const lines = Array.isArray(data?.log) ? data.log : [];

    if (running && statusEl) {
      statusEl.textContent = [
        `⏳ 初始化中 ${pct}%`,
        message,
        detail,
        lines.length ? lines[lines.length - 1] : "",
      ].filter(Boolean).join("\n");
    }

    if (!wrap || !fill || !pctEl || !msgEl) {
      if (running && resultEl) {
        resultEl.className = "settings-result";
        resultEl.textContent = [message, detail].filter(Boolean).join(" · ");
      }
      return;
    }

    if (!running && data?.phase === "idle" && data?.ok == null) {
      wrap.classList.add("hidden");
      return;
    }

    wrap.classList.remove("hidden");
    fill.style.width = `${pct}%`;
    fill.style.setProperty("--progress", `${pct}%`);
    pctEl.textContent = `${pct}%`;
    msgEl.textContent = message;
    if (detailEl) {
      detailEl.textContent = detail;
      detailEl.style.display = detail ? "block" : "none";
    }
    if (logEl) {
      logEl.textContent = lines.slice(-6).join("\n");
      logEl.style.display = lines.length ? "block" : "none";
    }
    if (running && resultEl) {
      resultEl.className = "settings-result";
      resultEl.textContent = [message, detail].filter(Boolean).join(" · ");
    }
  }

  function stopPythonEnvPoll() {
    if (pythonEnvPollTimer) {
      clearInterval(pythonEnvPollTimer);
      pythonEnvPollTimer = null;
    }
  }

  async function pollPythonEnvSetupProgress() {
    try {
      const res = await F.apiFetchWithTimeout("/api/python-env/setup/progress", {}, 15000);
      const data = await res.json();
      renderPythonEnvProgress(data);
      if (!data.running) {
        stopPythonEnvPoll();
        const resultEl = document.getElementById("pythonEnvResult");
        const btn = document.getElementById("setupPythonEnvBtn");
        if (btn) btn.disabled = false;
        if (data.ok === true) {
          hidePythonEnvProgress({ clearResult: true });
          await refreshPythonEnvStatus();
          return false;
        }
        if (resultEl && data.ok != null) {
          resultEl.className = "settings-result error";
          resultEl.textContent = data.result_message || data.message || "失败";
        }
        hidePythonEnvProgress();
        await refreshPythonEnvStatus();
        return false;
      }
      return true;
    } catch {
      return true;
    }
  }

  function startPythonEnvPoll() {
    stopPythonEnvPoll();
    void pollPythonEnvSetupProgress();
    pythonEnvPollTimer = setInterval(() => {
      void pollPythonEnvSetupProgress();
    }, 900);
  }

  async function refreshPythonEnvStatus() {
    const statusEl = document.getElementById("pythonEnvStatus");
    const resultEl = document.getElementById("pythonEnvResult");
    if (!statusEl) return;
    statusEl.textContent = "加载中…";
    try {
      const res = await F.apiFetchWithTimeout("/api/python-env", {}, 20000);
      const data = await res.json();
      const lines = [
        data.ready ? "✓ 已就绪" : "○ 未就绪",
        data.version ? `版本：${data.version}` : "",
        data.python_exe ? `解释器：${data.python_exe}` : "",
        `目录：${data.env_dir || "—"}`,
        data.message || "",
      ].filter(Boolean);
      statusEl.textContent = lines.join("\n");
      if (data.setup_running || pythonEnvPollTimer) {
        startPythonEnvPoll();
      } else if (
        data.setup_progress?.running
        || (data.setup_progress?.ok === false && data.setup_progress?.phase === "error")
      ) {
        renderPythonEnvProgress(data.setup_progress);
      } else if (!data.ready && data.last_setup_error) {
        hidePythonEnvProgress();
        if (resultEl) {
          resultEl.className = "settings-result error";
          resultEl.textContent = String(data.last_setup_error);
        }
      } else {
        hidePythonEnvProgress({ clearResult: data.ready });
      }
      if (resultEl && !resultEl.classList.contains("ok") && !resultEl.classList.contains("error")) {
        resultEl.textContent = "";
        resultEl.className = "settings-result";
      }
    } catch {
      statusEl.textContent = "无法读取 Python 环境状态。若正在初始化，请等待数分钟后再点「刷新状态」。";
    }
  }

  async function setupPythonEnv() {
    const btn = document.getElementById("setupPythonEnvBtn");
    const resultEl = document.getElementById("pythonEnvResult");
    if (btn) btn.disabled = true;
    if (resultEl) {
      resultEl.className = "settings-result";
      resultEl.textContent = "";
    }
    renderPythonEnvProgress({
      running: true,
      phase: "starting",
      percent: 0,
      message: "正在启动初始化…",
      detail: "首次安装 pandas 等依赖可能需 3–10 分钟，请保持网络畅通",
      log: [],
    });
    try {
      const res = await F.apiFetchWithTimeout("/api/python-env/setup", { method: "POST" }, 30000);
      const data = await res.json();
      if (data.already_running) {
        if (resultEl) resultEl.textContent = "初始化已在进行中…";
      }
      startPythonEnvPoll();
    } catch {
      stopPythonEnvPoll();
      if (resultEl) {
        resultEl.className = "settings-result error";
        resultEl.textContent = "无法启动初始化，请检查应用是否在运行。";
      }
      if (btn) btn.disabled = false;
    }
  }

  F.refreshPythonEnvStatus = refreshPythonEnvStatus;
  F.setupPythonEnv = setupPythonEnv;
})();
