"""DeepSeek API 连接诊断工具 — 逐层排查 DNS / TCP / SSL / API 认证 / 模型可用性"""
from __future__ import annotations

import json
import socket
import ssl
import sys
import urllib.request
from pathlib import Path

SETTINGS_PATH = Path(__file__).resolve().parents[1] / "friday" / "storage.py"


def _load_settings():
    """从 APPDATA 加载用户设置。"""
    try:
        appdata = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "AppData" / "Roaming" / "Friday"
    except Exception:
        appdata = Path.home() / "AppData" / "Roaming" / "Friday"
    settings_file = appdata / "settings.json"
    if not settings_file.is_file():
        print("[❌] 未找到配置文件: %s" % settings_file)
        return None
    raw = json.loads(settings_file.read_text(encoding="utf-8"))
    api_key = raw.get("api_key", "")
    base_url = raw.get("base_url", "https://api.deepseek.com")
    model = raw.get("model", "deepseek-chat")

    # 尝试解密 Fernet key
    if api_key and api_key.startswith("fernet:"):
        key_file = appdata / ".fernet_key"
        if key_file.is_file():
            try:
                from cryptography.fernet import Fernet
                f = Fernet(key_file.read_bytes())
                api_key = f.decrypt(api_key[len("fernet:"):].encode()).decode()
            except Exception:
                pass

    return {"api_key": api_key, "base_url": base_url, "model": model}


def _redact(s: str, show: int = 4) -> str:
    if not s or len(s) <= show * 2:
        return "***"
    return s[:show] + "..." + s[-show:]


def diagnose():
    cfg = _load_settings()
    if not cfg:
        return 1

    api_key = cfg["api_key"]
    base_url = cfg["base_url"].rstrip("/")
    model = cfg["model"]

    print("=" * 60)
    print("DeepSeek API 连接诊断")
    print("=" * 60)
    print(f"  Base URL : {base_url}")
    print(f"  Model    : {model}")
    print(f"  API Key  : {_redact(api_key) if api_key else '(空)'}")
    print()

    # 1. DNS 解析
    from urllib.parse import urlparse
    parsed = urlparse(base_url)
    host = parsed.hostname or ""
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    print(f"[1/5] DNS 解析 {host} ...")
    try:
        addrs = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
        ips = sorted(set(a[4][0] for a in addrs))
        print(f"  ✅ 解析成功: {', '.join(ips[:4])}")
    except socket.gaierror as e:
        print(f"  ❌ DNS 解析失败: {e}")
        print(f"  💡 建议: 检查网络连接 / DNS 设置，或尝试更换 Base URL")
        return 1

    # 2. TCP 连接
    print(f"[2/5] TCP 连接 {host}:{port} ...")
    try:
        sock = socket.create_connection((host, port), timeout=10)
        sock.close()
        print(f"  ✅ TCP 连接成功")
    except (socket.timeout, TimeoutError) as e:
        print(f"  ❌ TCP 连接超时: {e}")
        print(f"  💡 建议: 网络延迟过高或被防火墙拦截，检查代理/VPN")
        return 1
    except OSError as e:
        print(f"  ❌ TCP 连接失败: {e}")
        print(f"  💡 建议: {host} 不可达，检查网络/防火墙/代理设置")
        return 1

    # 3. SSL/TLS 握手
    print(f"[3/5] SSL/TLS 握手 ...")
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
        from datetime import datetime
        not_after = cert.get("notAfter", "")
        cn = ""
        for field in cert.get("subject", []):
            if field[0][0] == "commonName":
                cn = field[0][1]
        print(f"  ✅ SSL 握手成功 (证书: {cn}, 到期: {not_after})")
    except ssl.SSLError as e:
        print(f"  ❌ SSL 握手失败: {e}")
        print(f"  💡 建议: 证书验证失败，检查系统时间或代理设置")
        return 1
    except Exception as e:
        print(f"  ⚠️ SSL 测试异常: {e}")

    # 4. API 认证测试
    print(f"[4/5] API 认证测试 ...")
    if not api_key:
        print(f"  ❌ API Key 为空")
        print(f"  💡 建议: 在设置中填写正确的 DeepSeek API Key")
        return 1
    try:
        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 8,
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())
            content = body["choices"][0]["message"]["content"]
            print(f"  ✅ API 响应成功: {content.strip()}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        print(f"  ❌ HTTP {e.code}: {body}")
        if e.code == 401:
            print(f"  💡 建议: API Key 无效或已过期，请重新生成")
        elif e.code == 404:
            print(f"  💡 建议: 模型 '{model}' 不存在，请更换为 deepseek-chat 或 deepseek-reasoner")
        elif e.code == 403:
            print(f"  💡 建议: 账户余额不足或权限不足")
        else:
            print(f"  💡 建议: 检查 API Key 和 Base URL 是否正确")
        return 1
    except urllib.error.URLError as e:
        print(f"  ❌ 请求失败: {e.reason}")
        return 1
    except Exception as e:
        print(f"  ❌ 未知错误: {e}")
        return 1

    # 5. 模型列表检查
    print(f"[5/5] 模型可用性检查 ...")
    try:
        req = urllib.request.Request(
            f"{base_url}/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            models_list = [m.get("id", "") for m in data.get("data", [])]
            if model in models_list:
                print(f"  ✅ 模型 '{model}' 在可用列表中")
            else:
                print(f"  ⚠️ 模型 '{model}' 不在 /models 返回的列表中")
                print(f"  可用模型: {', '.join(models_list[:10])}")
                print(f"  💡 建议: 将模型改为 deepseek-chat（通用对话）或 deepseek-reasoner（深度推理）")
    except Exception as e:
        print(f"  ⚠️ 无法获取模型列表: {e}")

    print()
    print("=" * 60)
    print("✅ 所有检查通过，API 连接正常！")
    return 0


if __name__ == "__main__":
    sys.exit(diagnose())
