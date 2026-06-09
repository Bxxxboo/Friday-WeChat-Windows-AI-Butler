from __future__ import annotations

import os
import platform
import socket
import subprocess
import uuid
import webbrowser
from datetime import datetime

import psutil

from friday.tools._decorators import register_tool


@register_tool(
    name="get_system_status",
    description="查看电脑系统状态（CPU、内存、系统版本）",
    parameters={"type": "object", "properties": {}},
)
def get_system_status() -> str:
    vm = psutil.virtual_memory()
    boot = datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"系统: {platform.system()} {platform.release()} ({platform.machine()})",
        f"主机名: {platform.node()}",
        f"CPU: {psutil.cpu_count(logical=False)} 核 / {psutil.cpu_count()} 线程, 使用率 {psutil.cpu_percent(interval=None)}%",
        f"内存: 总计 {vm.total // (1024**2)} MB, 已用 {vm.percent}%, 可用 {vm.available // (1024**2)} MB",
        f"开机时间: {boot}",
    ]
    return "\n".join(lines)


@register_tool(
    name="get_disk_usage",
    description="查看磁盘使用情况",
    parameters={"type": "object", "properties": {}},
)
def get_disk_usage() -> str:
    lines = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except PermissionError:
            continue
        total_gb = usage.total / (1024**3)
        free_gb = usage.free / (1024**3)
        lines.append(
            f"{part.device} ({part.mountpoint}) {usage.percent}% 已用, 剩余 {free_gb:.1f} GB / {total_gb:.1f} GB"
        )
    return "\n".join(lines) or "无法读取磁盘信息"


@register_tool(
    name="get_top_processes",
    description="查看占用内存最高的进程",
    parameters={
        "type": "object",
        "properties": {"limit": {"type": "integer"}},
    },
)
def get_top_processes(limit: int = 10) -> str:
    processes = []
    for proc in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            mem = proc.info["memory_info"].rss
            processes.append((mem, proc.info["pid"], proc.info["name"]))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    processes.sort(reverse=True)
    lines = []
    for mem, pid, name in processes[:limit]:
        lines.append(f"PID {pid:>6} | {mem // (1024**2):>5} MB | {name}")
    return "\n".join(lines)


# ── 新增工具 ──

@register_tool(
    name="open_url",
    description="在默认浏览器中打开网址",
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "要打开的网址（需包含 http:// 或 https://）"},
        },
        "required": ["url"],
    },
)
def open_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        return "网址必须以 http:// 或 https:// 开头"
    webbrowser.open(url)
    return f"已在浏览器中打开: {url}"


@register_tool(
    name="open_app",
    description="启动应用程序（按名称或路径）",
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "应用程序名称（如 notepad、calc、explorer）或完整路径"},
        },
        "required": ["name"],
    },
)
def open_app(name: str) -> str:
    system = platform.system()
    try:
        if system == "Windows":
            subprocess.Popen(["cmd", "/c", "start", "", name], shell=True)
        elif system == "Darwin":
            subprocess.Popen(["open", "-a", name])
        else:
            subprocess.Popen([name])
        return f"已启动: {name}"
    except Exception as e:
        return f"启动失败: {e}"


@register_tool(
    name="get_network_info",
    description="查看网络信息（主机名、IP 地址、MAC 地址）",
    parameters={"type": "object", "properties": {}},
)
def get_network_info() -> str:
    hostname = socket.gethostname()
    try:
        ip = socket.gethostbyname(hostname)
    except socket.gaierror:
        ip = "无法获取"

    mac = "无法获取"
    try:
        node = uuid.getnode()
        mac = ":".join(f"{(node >> (i * 8)) & 0xff:02x}" for i in reversed(range(6)))
    except Exception:
        pass

    lines = [
        f"主机名: {hostname}",
        f"本地 IP: {ip}",
        f"MAC 地址: {mac}",
    ]

    # 网卡列表（可选依赖 netifaces）
    try:
        import netifaces
        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface)
            inet = addrs.get(netifaces.AF_INET, [])
            for addr in inet:
                addr_str = addr.get("addr", "")
                if addr_str and addr_str != "127.0.0.1":
                    lines.append(f"网卡 {iface}: {addr_str}")
    except ImportError:
        pass

    return "\n".join(lines)


@register_tool(
    name="list_open_windows",
    description="列出当前可见窗口（标题与进程），了解用户正在使用哪些程序",
    parameters={
        "type": "object",
        "properties": {
            "max_results": {"type": "integer", "description": "最多返回数量，默认 25"},
        },
    },
)
def list_open_windows(max_results: int = 25) -> str:
    if platform.system() != "Windows":
        return "仅支持 Windows"
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    entries: list[tuple[str, str, int]] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _callback(hwnd: int, _lparam: int) -> bool:
        if user32.GetParent(hwnd):
            return True
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd) + 1
        if length <= 1:
            return True
        buf = ctypes.create_unicode_buffer(length)
        user32.GetWindowTextW(hwnd, buf, length)
        title = buf.value.strip()
        if not title:
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        proc_name = "?"
        try:
            proc_name = psutil.Process(int(pid.value)).name()
        except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
            pass
        entries.append((title, proc_name, int(pid.value)))
        return True

    user32.EnumWindows(_callback, 0)
    if not entries:
        return "未找到可见窗口"
    entries.sort(key=lambda item: item[0].casefold())
    limit = max(1, int(max_results))
    lines = []
    for title, proc_name, pid in entries[:limit]:
        lines.append(f"{title} | {proc_name} (PID {pid})")
    if len(entries) > limit:
        lines.append(f"... 另有 {len(entries) - limit} 个窗口未列出")
    return "\n".join(lines)
