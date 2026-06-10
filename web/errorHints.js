/* ================================================================= *
 *  errorHints.js — 前端异常文案（与 friday/error_hints.py 对齐）
 * ================================================================= */

(function () {
  "use strict";

  const F = window.Friday;
  if (!F) return;

  function remoteAuthFailure(text, lower) {
    if (text === "401") return true;
    if (["401", "403"].some((c) => lower.includes(c))) {
      return ["api", "key", "error code", "http", "openai", "invalid", "authentication"].some(
        (k) => lower.includes(k),
      );
    }
    return ["unauthorized", "invalid api key", "incorrect api key", "invalid_api_key", "authentication"].some(
      (k) => lower.includes(k),
    );
  }

  function inferContextFromText(text) {
    const head = text.slice(0, 32);
    if (head.includes("生图")) return "image_gen";
    if (head.includes("视觉")) return "vision";
    return "";
  }

  function resolveErrorContext(service = "", context = "") {
    const svc = String(service || "").trim();
    if (svc.includes("生图")) return "image_gen";
    if (svc.includes("视觉")) return "vision";
    const ctx = String(context || "").trim().toLowerCase();
    if (["image_gen", "vision", "llm", "auth_401", "local_auth"].includes(ctx)) return ctx;
    if (svc && svc !== "API") return "llm";
    return ctx || "api_test";
  }

  function classifyClientError(raw, context = "", service = "") {
    const text = String(raw || "").trim();
    const lower = text.toLowerCase();
    let ctx = resolveErrorContext(service, context);
    const textCtx = inferContextFromText(text);
    if (textCtx) ctx = textCtx;

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
    if (ctx === "auth_401" || ctx === "local_auth") {
      return {
        code: "auth_401",
        detail: "本地认证已过期",
        hint: "已尝试自动恢复；若仍失败，请完全退出星期五后重新打开",
      };
    }
    if (remoteAuthFailure(text, lower)) {
      if (ctx === "image_gen" || text.includes("生图")) {
        return {
          code: "image_gen_auth",
          detail: "生图 API Key 无效",
          hint: "请在 设置 → 生图 检查 Key、Base URL 与模型是否与当前服务商匹配",
        };
      }
      if (ctx === "vision" || text.includes("视觉")) {
        return {
          code: "vision_auth",
          detail: "视觉 API Key 无效",
          hint: "请在 设置 → 视觉 检查 Key、Base URL 与 ep- 推理接入点是否正确",
        };
      }
      return {
        code: "api_auth",
        detail: lower.includes("llm") || text.includes("大模型") ? "大模型 API Key 无效" : "API Key 无效或已失效",
        hint: "请在 设置 → 大模型 检查当前服务商与 Key 是否匹配（MiMo / DeepSeek 等需分别配置）",
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
    if (
      lower.includes("readtimeout")
      || lower.includes("read timeout")
      || lower.includes("read timed out")
      || lower.includes("apitimeouterror")
    ) {
      const imageGen = ctx === "image_gen" || text.includes("生图");
      return {
        code: "api_timeout",
        detail: imageGen ? "生图 API 响应超时" : "API 响应超时",
        hint: imageGen
          ? "生图端点可能较慢，请检查 Base URL 与模型名；可在设置页重试或换备用 URL"
          : "服务器可能繁忙或网络较慢，请稍后重试；若仅偶发可忽略，反复出现请点「网络诊断」",
      };
    }
    if (text.includes("429") || lower.includes("too many requests") || lower.includes("rate limit")) {
      return {
        code: "api_rate_limit",
        detail: "API 请求过于频繁（429 Too Many Requests）",
        hint: "请稍等 1–2 分钟后重试；若持续出现，请检查当前服务商的配额/并发限制，或降低对话频率",
      };
    }
    if (
      lower.includes("connection")
      || lower.includes("timed out")
      || lower.includes("network")
      || lower.includes("connect")
      || lower.includes("refused")
      || lower.includes("unreachable")
    ) {
      if (lower.includes("proxy") || lower.includes("407")) {
        return {
          code: "api_proxy",
          detail: "无法通过代理连接 API",
          hint: "在 设置 → API 连接 → 网络代理 填写公司代理地址（如 http://127.0.0.1:7890），或取消系统代理后重试",
        };
      }
      if (lower.includes("ssl") || lower.includes("certificate") || lower.includes("tls")) {
        return {
          code: "api_ssl",
          detail: "SSL 证书验证失败",
          hint: "检查系统时间是否正确；企业网络需导入代理根证书，或配置正确的 HTTPS 代理",
        };
      }
      const imageGen = ctx === "image_gen" || text.includes("生图");
      const vision = ctx === "vision" || text.includes("视觉");
      return {
        code: "api_network",
        detail: vision ? "无法连接视觉 API 服务器" : imageGen ? "无法连接生图 API 服务器" : "无法连接 API 服务器",
        hint: "请检查网络与防火墙；公司/校园网请在设置中配置 HTTP 代理，并点击「网络诊断」查看详情",
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

  function formatClientApiError(res, data, { service = "", context = "api_test" } = {}) {
    const payload = data && typeof data === "object" ? data : {};
    const code = payload.code || "";
    if (res?.status === 401 || code === "auth_401") {
      return "本地会话已失效，请关闭设置页后重试；仍失败请完全退出星期五再打开";
    }
    if (payload.message || payload.hint) {
      return formatErrorResult(payload);
    }
    const raw = payload.detail || payload.message || "";
    if (raw) {
      const classified = classifyClientError(raw, context, service);
      return formatErrorResult({ message: classified.detail, hint: classified.hint });
    }
    return res ? `HTTP ${res.status}` : "请求失败";
  }

  function applyApiTestResult(resultEl, data, { okClass = "settings-result ok", errClass = "settings-result error" } = {}) {
    if (!resultEl) return;
    resultEl.className = data?.ok ? okClass : errClass;
    resultEl.textContent = formatErrorResult(data);
  }

  F.classifyClientError = classifyClientError;
  F.formatErrorResult = formatErrorResult;
  F.formatClientApiError = formatClientApiError;
  F.applyApiTestResult = applyApiTestResult;
})();
