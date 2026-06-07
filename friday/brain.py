from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

from openai import OpenAI

from friday.logging_config import get_logger
from friday.paths import format_folders_for_prompt, known_folders
from friday.storage import UserSettings, resolved_workspace
from friday.tools.registry import get_tool_definitions, get_tool_definitions_for_messages

_log = get_logger("brain")

_SYSTEM_PROMPT_BASE = """你是「星期五」，住在这台 Windows 电脑里的 AI 管家。
职责：帮用户打理电脑——整理文件、查看系统状态、生成文档、执行日常电脑事务。

能力概览：
- 文件：列出/搜索/读取/写入/移动/复制/删除/整理/重命名/查重/压缩/解压/查看详情
- 文档：创建 Word/PPT、读取 PDF/Excel
- 系统：CPU/内存/磁盘/进程/网络信息、截图、剪贴板读写
- 图片：DeepSeek 无法直接看图；用户粘贴截图或在对话框发图时，路径会在消息里给出，请用 describe_image 分析
- 联网：浏览网页查找下载链接、验证官方来源（TLS/域名）、从网址下载文件到本地
- 应用：打开网页、启动程序、执行 PowerShell、运行 Python（工作区 .python-env）
- 扩展：从 GitHub 安装/卸载插件包（技能+规则），用户也可在「设置 → 扩展」管理
  · 安装插件前先 list_friday_plugins 看是否已装；不知仓库地址时用 list_plugin_catalog
  · 用户只说插件名（如 storage-analyzer）可直接用该 ID 安装，或查推荐列表
  · 不要用猜错的 owner/repo 连续重试；GitHub Agent Skill 用 skill:owner/repo/目录 格式

规则：
1. 自称「星期五」，语气亲切、简洁，像可靠的电脑管家。
2. 优先使用工具完成任务，不要只给空泛建议。
3. 用户说「下载文件夹」「桌面」「文档」「图片」等时，使用下方「本机常用文件夹路径」中的绝对路径；未指定时优先使用「默认操作文件夹」。
4. 文件操作前先了解目录结构（list_directory / search_files）。
5. 删除文件/目录前务必告知用户后果，获得确认后再执行。
6. 帮用户下载软件时（务必高效、少步骤）：
   - 禁止用 run_powershell / Invoke-WebRequest 下载；系统会直接拒绝此类命令。
   - 优先使用 download_software(软件名, 保存路径) 一键完成（内部浏览官网+验证+下载，只需用户确认一次）。
   - 备选：browse_webpage → verify_download_source → download_file，总共不超过 3 步。
   - 用户指定 E 盘等路径时，destination 直接用该绝对路径。
   - 填写 expected_software（netease_music、chrome、微信等）提高识别率。
   - 下载完成后用户要求打开时，用 open_app 启动安装包，不要开浏览器或 PowerShell。
7. 复杂数据处理、统计分析、批量转换、绘图等任务优先用 run_python 或 run_python_script（工作区 .python-env，含 pandas/numpy 等）。
   - 执行前可用 python_env_info 查看环境；Windows 用 python 路径，不要用 python3 命令。
   - 长脚本先 write_text_file 保存再 run_python_script；小片段可直接 run_python。
8. 回答使用简体中文，说明已完成的动作和结果，避免暴露工具函数名等技术细节。
9. 危险操作（删除系统文件、格式化磁盘）不要执行。
10. 若用户问与电脑无关的闲聊（写诗、百科等），简短回应后引导回电脑事务，例如整理文件、查系统、做文档。
"""

# 兼容旧引用
SYSTEM_PROMPT = _SYSTEM_PROMPT_BASE


def build_system_prompt(settings: UserSettings, *, yolo_unlocked: bool = False) -> str:
    from friday.interaction_modes import mode_prompt_block
    from friday.rules import active_rules_prompt
    from friday.vision import vision_ready

    folders = known_folders(resolved_workspace(settings))
    folder_block = format_folders_for_prompt(folders)
    rules_block = active_rules_prompt()
    mode_block = mode_prompt_block(
        getattr(settings, "interaction_mode", "agent"),
        yolo_unlocked=yolo_unlocked,
    )
    vision_block = ""
    if vision_ready(settings):
        vision_block = (
            "\n【视觉辅助已启用】用户发图或消息中含截图路径时，必须先调用 describe_image 分析，"
            "再根据返回的文字描述回答；不要声称无法看图。\n"
        )
    return f"{_SYSTEM_PROMPT_BASE}{vision_block}\n本机常用文件夹路径：\n{folder_block}\n{mode_block}\n{rules_block}\n"

# ── 模型上下文窗口（保守取值，留 15% 给响应） ──
_MODEL_MAX_TOKENS: dict[str, int] = {
    "deepseek-v4-flash": 130_000,
    "deepseek-v4-pro": 130_000,
    "deepseek-chat": 64_000,
    "deepseek-reasoner": 64_000,
}

_DEFAULT_MAX_CONTEXT = 100_000  # 未知模型保守估计
_SAFETY_RATIO = 0.85  # 请求 token 不超过上下文的 85%，留空间给响应
_MIN_KEEP_RECENT = 6  # 截断时至少保留最近 N 条消息（system + user + assistant + tool 对）


def resolve_max_context(settings: UserSettings, *, client: OpenAI | None = None) -> int:
    """解析模型上下文上限：硬编码表为 fallback，优先尝试 API。"""
    fallback = _MODEL_MAX_TOKENS.get(settings.model, _DEFAULT_MAX_CONTEXT)
    if client is None:
        return fallback
    try:
        info = client.models.retrieve(settings.model)
        for attr in ("max_context_tokens", "context_length", "max_tokens"):
            value = getattr(info, attr, None)
            if isinstance(value, int) and value > 0:
                return value
        if isinstance(info, dict):
            for key in ("max_context_tokens", "context_length", "max_tokens"):
                value = info.get(key)
                if isinstance(value, int) and value > 0:
                    return value
    except Exception:  # noqa: BLE001
        pass
    return fallback


@dataclass
class ChatCompletionResult:
    content: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class DeepSeekBrain:
    def __init__(self, settings: UserSettings) -> None:
        self.settings = settings
        self.client = OpenAI(api_key=settings.api_key, base_url=settings.base_url)
        self._encoder: Any = None
        self._encoder_initialized = False
        self._max_context = resolve_max_context(settings)
        # ── #13 token 用量统计 ──
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0

    @property
    def encoder(self):
        """tiktoken 编码器，仅在首次 token 计数时加载。"""
        if not self._encoder_initialized:
            self._encoder = self._init_encoder()
            self._encoder_initialized = True
        return self._encoder

    def _init_encoder(self):
        """延迟导入 tiktoken，避免未安装时启动崩溃。"""
        try:
            import tiktoken
            return tiktoken.get_encoding("cl100k_base")
        except ImportError:
            _log.warning("tiktoken 未安装，token 计数将使用字符估算")
            return None
        except Exception:
            _log.warning("tiktoken 初始化失败，使用 o200k_base")
            import tiktoken
            return tiktoken.get_encoding("o200k_base")

    def count_tokens(self, messages: list[dict[str, Any]]) -> int:
        """估算消息列表的 token 数。未安装 tiktoken 时用字符数/4 估算。"""
        enc = self.encoder
        if enc is None:
            return sum(len(str(m)) // 4 for m in messages)

        total = 0
        for msg in messages:
            total += 4  # 每条消息的框架开销
            for key, value in msg.items():
                if isinstance(value, str):
                    total += len(enc.encode(value))
                elif isinstance(value, list):
                    total += self._count_tool_calls(value)
        # 工具定义的开销（粗略估算，一次即可）
        return total + 200

    def _count_tool_calls(self, tool_calls: list[dict[str, Any]]) -> int:
        enc = self.encoder
        if enc is None:
            return sum(len(str(tc)) // 4 for tc in tool_calls)
        total = 0
        for tc in tool_calls:
            total += len(enc.encode(str(tc)))
        return total

    def trim_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """当上下文即将超限时，截断早期消息。

        策略：保留 system prompt + 最近的对话轮次，丢弃中间的工具调用细节。
        """
        if len(messages) <= _MIN_KEEP_RECENT:
            return messages

        token_count = self.count_tokens(messages)
        budget = int(self._max_context * _SAFETY_RATIO)

        if token_count <= budget:
            return messages

        _log.info(
            "上下文截断触发 | tokens=%d budget=%d messages=%d",
            token_count, budget, len(messages),
        )

        # 保留 system prompt (索引 0) + 最近的消息
        trimmed = [messages[0]]  # system prompt
        # 从尾部向前保留，直到接近预算
        kept = []
        for msg in reversed(messages[1:]):
            kept.insert(0, msg)
            if self.count_tokens(trimmed + kept) >= budget:
                break

        result = trimmed + kept
        _log.info("上下文截断完成 | kept=%d/%d tokens≈%d", len(result), len(messages), self.count_tokens(result))
        return result

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: bool = True,
        *,
        tool_definitions: list[dict[str, Any]] | None = None,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "model": self.settings.model,
            "messages": messages,
            "temperature": 0.2,
        }
        if tools:
            kwargs["tools"] = tool_definitions or get_tool_definitions_for_messages(
                messages,
                settings=self.settings,
            )
            kwargs["tool_choice"] = "auto"
        return self.client.chat.completions.create(**kwargs)

    def iter_chat(
        self,
        messages: list[dict[str, Any]],
        tools: bool = True,
        *,
        tool_definitions: list[dict[str, Any]] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> Iterator[tuple[str, Any]]:
        kwargs: dict[str, Any] = {
            "model": self.settings.model,
            "messages": messages,
            "temperature": 0.2,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tool_definitions or get_tool_definitions_for_messages(
                messages,
                settings=self.settings,
            )
            kwargs["tool_choice"] = "auto"

        stream = self.client.chat.completions.create(**kwargs)
        content_parts: list[str] = []
        tool_calls_acc: dict[int, dict[str, Any]] = {}

        for chunk in stream:
            if should_cancel and should_cancel():
                close = getattr(stream, "close", None)
                if callable(close):
                    close()
                break
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            if delta.content:
                content_parts.append(delta.content)
                yield "delta", delta.content

            if delta.tool_calls:
                for call in delta.tool_calls:
                    idx = call.index
                    if idx not in tool_calls_acc:
                        tool_calls_acc[idx] = {
                            "id": "",
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        }
                    acc = tool_calls_acc[idx]
                    if call.id:
                        acc["id"] = call.id
                    if call.function:
                        if call.function.name:
                            acc["function"]["name"] += call.function.name
                        if call.function.arguments:
                            acc["function"]["arguments"] += call.function.arguments

        tool_calls = [tool_calls_acc[idx] for idx in sorted(tool_calls_acc)]
        result = ChatCompletionResult(
            content="".join(content_parts),
            tool_calls=tool_calls,
        )

        # ── #13 统计 token 用量 ──
        self.total_prompt_tokens += self.count_tokens(messages)
        enc = self.encoder
        if enc is not None:
            self.total_completion_tokens += len(enc.encode(result.content))
        else:
            self.total_completion_tokens += len(result.content) // 4

        yield "finish", result

    def usage_summary(self) -> str:
        """返回本次会话的 token 用量摘要。"""
        return (
            f"📊 Token 用量：输入 {self.total_prompt_tokens:,} | "
            f"输出 {self.total_completion_tokens:,} | "
            f"合计 {self.total_prompt_tokens + self.total_completion_tokens:,}"
        )

    def test_connection(self) -> tuple[bool, str]:
        try:
            response = self.client.chat.completions.create(
                model=self.settings.model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=8,
            )
            text = response.choices[0].message.content or "ok"
            return True, f"连接成功，模型响应: {text.strip()}"
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)
