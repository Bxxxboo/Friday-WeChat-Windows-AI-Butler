"""已知异常 → 用户可见文案与修复指引（P3-1）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ErrorHint:
    code: str
    detail: str
    hint: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "detail": self.detail, "hint": self.hint}


def classify_error(raw: Any = "", *, context: str = "") -> ErrorHint:
    """将异常或日志片段映射为面向用户的 detail + hint。"""
    text = str(raw or "").strip()
    lower = text.lower()
    ctx = (context or "").strip().lower()

    if ctx in {"backend_starting", "health_starting"}:
        return ErrorHint(
            "backend_starting",
            "后端仍在启动，请稍候",
            "就绪后再测试 API 连接",
        )

    if ctx in {"health_timeout", "startup_timeout"} or "启动超时" in text:
        return ErrorHint(
            "health_timeout",
            "后端仍在启动，请稍候",
            "若长时间无响应，请重启应用；仍失败请打开 AppData 下的 friday.log",
        )

    if ctx in {"auth_401", "unauthorized"} or "unauthorized" in lower or text == "401":
        return ErrorHint(
            "auth_401",
            "本地认证已过期",
            "已尝试自动恢复；若仍失败，请完全退出星期五后重新打开",
        )

    if "python.runtime" in lower or "pythonnet" in lower:
        return ErrorHint(
            "runtime_lib",
            "运行库异常，请安装 VC++ 运行库或重新安装星期五",
            "可安装 Microsoft Visual C++ 2015–2022 运行库；若安装路径含中文，请改到英文目录后重装",
        )

    if "multipart" in lower or "python-multipart" in lower:
        return ErrorHint(
            "missing_multipart",
            "安装包组件缺失，请下载最新版覆盖安装",
            "从 Gitee Releases 下载最新 Friday-Windows.zip 覆盖安装",
        )

    if (
        "jsondecodeerror" in lower
        or ("settings" in lower and "json" in lower)
        or "配置文件损坏" in text
        or ctx == "settings_json"
    ):
        return ErrorHint(
            "settings_corrupt",
            "配置文件损坏，已尝试从 .bak 恢复",
            "打开 %APPDATA%\\Friday，检查 settings.json 与 settings.json.bak",
        )

    if ctx == "api_key_missing" or text == "请先填写 API Key":
        return ErrorHint(
            "api_key_missing",
            "请先在设置中填写大模型 API Key",
            "打开 设置 → 大模型，选择服务商并保存 Key",
        )

    if any(k in lower for k in ("invalid api key", "incorrect api key", "authentication", "unauthorized")):
        return ErrorHint(
            "api_auth",
            "API Key 无效或已失效",
            "请在 设置 → 大模型 检查当前服务商与 Key 是否匹配（MiMo / DeepSeek 等需分别配置）",
        )

    if any(k in lower for k in ("401", "403")) and ("api" in lower or "key" in lower or ctx == "api_test"):
        return ErrorHint(
            "api_auth",
            "API Key 无效或已失效",
            "请在 设置 → 大模型 检查当前服务商与 Key 是否匹配（MiMo / DeepSeek 等需分别配置）",
        )

    if "推理接入点" in text or ("ep-" in lower and "不存在" in text):
        return ErrorHint(
            "image_gen_endpoint",
            text.split("\n")[0][:240],
            "请在火山方舟控制台确认 ep ID 是否正确、是否已开通图像生成能力",
        )

    if "http 404" in lower or ("404" in text and "接口" in text):
        return ErrorHint(
            "api_not_found",
            "接口地址或模型不存在",
            "请检查 Base URL 是否为服务商文档中的 /api/v3；火山方舟需填写 ep- 推理接入点而非裸模型名",
        )

    if "尺寸过小" in text or "3686400" in text.replace(",", ""):
        return ErrorHint(
            "image_gen_size",
            text.split("\n")[0][:240],
            "该模型最低约 1920×1920（368 万像素）；对话生图会自动提升尺寸，测试也会自动重试",
        )

    if "http 400" in lower or ("请求被拒绝" in text) or ("参数无效" in text):
        return ErrorHint(
            "api_bad_request",
            text.split("\n")[0][:240] or "生图请求被拒绝",
            "请核对模型名、Key 与服务商是否一致；中转站需使用其文档中的生图 model ID",
        )

    if any(k in lower for k in ("connection", "timeout", "timed out", "network", "connect", "refused", "unreachable")):
        if "proxy" in lower or "407" in lower:
            return ErrorHint(
                "api_proxy",
                "无法通过代理连接 API",
                "在 设置 → API 连接 → 网络代理 填写公司代理地址（如 http://127.0.0.1:7890），或取消系统代理后重试",
            )
        if any(k in lower for k in ("ssl", "certificate", "cert verify", "tls")):
            return ErrorHint(
                "api_ssl",
                "SSL 证书验证失败",
                "检查系统时间是否正确；企业网络需导入代理根证书，或配置正确的 HTTPS 代理",
            )
        if "getaddrinfo" in lower or "name or service not known" in lower or "nodename nor servname" in lower:
            return ErrorHint(
                "api_dns",
                "无法解析 API 服务器地址",
                "检查 DNS 与网络；若 Base URL 填错请改回官方地址；公司网络可能需要代理",
            )
        if ctx == "api_test" or "deepseek" in lower or "openai" in lower or "api" in lower or "ark" in lower:
            return ErrorHint(
                "api_network",
                "无法连接 API 服务器",
                "请检查网络与防火墙；公司/校园网请在设置中配置 HTTP 代理，并点击「网络诊断」查看详情",
            )

    if text:
        return ErrorHint(
            "unknown",
            text[:240],
            "可打开 设置 → 数据与日志 → 打开日志文件夹 查看详情",
        )

    return ErrorHint(
        "unknown",
        "操作失败",
        "可打开 设置 → 数据与日志 → 打开日志文件夹 查看详情",
    )


def format_user_message(hint: ErrorHint, *, include_detail: bool = True) -> str:
    """合并 detail 与 hint 为单行/多行展示文案。"""
    if include_detail and hint.hint:
        return f"{hint.detail}\n{hint.hint}"
    return hint.detail or hint.hint
