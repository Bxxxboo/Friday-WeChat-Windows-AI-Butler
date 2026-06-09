/* ================================================================= *
 *  errorHints.js — 前端异常文案（与 friday/error_hints.py 对齐）
 * ================================================================= */

(function () {
  "use strict";

  const F = window.Friday;
  if (!F) return;

  function classifyClientError(raw, context = "") {
    const text = String(raw || "").trim();
    const lower = text.toLowerCase();
    const ctx = String(context || "").toLowerCase();

    if (ctx === "backend_starting" || ctx === "health_starting") {
      return {
        code: "backend_starting",
        detail: "后端仍在启动，请稍候",
        hint: "就绪后再测试 API 连接",
      };
    }
    if (ctx === "health_timeout" || text.includes("启动超时")) {
      return {
        code: "health_timeout",
        detail: "后端仍在启动，请稍候",
        hint: "若长时间无响应，请重启应用；仍失败请打开 AppData 下的 friday.log",
      };
    }
    if (ctx === "auth_401" || lower.includes("unauthorized") || text === "401") {
      return {
        code: "auth_401",
        detail: "本地认证已过期",
        hint: "已尝试自动恢复；若仍失败，请完全退出星期五后重新打开",
      };
    }
    if (lower.includes("python.runtime") || lower.includes("pythonnet")) {
      return {
        code: "runtime_lib",
        detail: "运行库异常，请安装 VC++ 运行库或重新安装星期五",
        hint: "可安装 Microsoft Visual C++ 2015–2022 运行库；若安装路径含中文，请改到英文目录后重装",
      };
    }
    if (lower.includes("multipart") || lower.includes("python-multipart")) {
      return {
        code: "missing_multipart",
        detail: "安装包组件缺失，请下载最新版覆盖安装",
        hint: "从 Gitee Releases 下载最新 Friday-Windows.zip 覆盖安装",
      };
    }
    if (text) {
      return {
        code: "unknown",
        detail: text.slice(0, 240),
        hint: "可打开 设置 → 数据与日志 → 打开日志文件夹 查看详情",
      };
    }
    return {
      code: "unknown",
      detail: "操作失败",
      hint: "可打开 设置 → 数据与日志 → 打开日志文件夹 查看详情",
    };
  }

  function formatErrorResult(data) {
    if (!data) return "未知错误";
    const msg = data.message || data.detail || "";
    const hint = data.hint || "";
    if (msg && hint && !msg.includes(hint)) return `${msg}\n${hint}`;
    return msg || hint || "未知错误";
  }

  function applyApiTestResult(resultEl, data, { okClass = "settings-result ok", errClass = "settings-result error" } = {}) {
    if (!resultEl) return;
    resultEl.className = data?.ok ? okClass : errClass;
    resultEl.textContent = formatErrorResult(data);
  }

  F.classifyClientError = classifyClientError;
  F.formatErrorResult = formatErrorResult;
  F.applyApiTestResult = applyApiTestResult;
})();
