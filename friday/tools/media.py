from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from collections import defaultdict
from pathlib import Path

from friday.tools._decorators import register_tool


def _resolve(path: str) -> Path:
    return Path(path).expanduser().resolve()


# ── PDF ──

@register_tool(
    name="read_pdf",
    description="读取 PDF 文件的文本内容",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "PDF 文件路径"},
            "max_chars": {"type": "integer", "description": "最多读取字符数"},
        },
        "required": ["path"],
    },
)
def read_pdf(path: str, max_chars: int = 8000) -> str:
    """读取 PDF 文本内容"""
    target = _resolve(path)
    if not target.exists():
        return f"文件不存在: {target}"
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return "需要安装 pymupdf: pip install pymupdf"

    doc = fitz.open(target)
    parts: list[str] = []
    total = 0
    for page in doc:
        text = page.get_text()
        if text:
            total += len(text)
            parts.append(text)
            if total >= max_chars:
                break
    doc.close()
    result = "\n".join(parts)
    if total > max_chars:
        result = result[:max_chars] + f"\n... (截断，共 {total} 字符)"
    return result or "(PDF 无可提取文本)"


# ── Excel ──

@register_tool(
    name="read_excel",
    description="读取 Excel 文件内容，返回 CSV 格式",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Excel 文件路径"},
            "sheet_name": {"type": "string", "description": "工作表名称（可选）"},
            "max_rows": {"type": "integer", "description": "最多读取行数"},
        },
        "required": ["path"],
    },
)
def read_excel(path: str, sheet_name: str | None = None, max_rows: int = 100) -> str:
    """读取 Excel 表格内容，返回 CSV 格式文本"""
    target = _resolve(path)
    if not target.exists():
        return f"文件不存在: {target}"
    try:
        import openpyxl
    except ImportError:
        return "需要安装 openpyxl: pip install openpyxl"

    wb = openpyxl.load_workbook(target, read_only=True, data_only=True)
    sheet = wb[sheet_name] if sheet_name else wb.active
    output = io.StringIO()
    writer = csv.writer(output)
    rows_written = 0
    for row in sheet.iter_rows(values_only=True):
        writer.writerow([str(cell) if cell is not None else "" for cell in row])
        rows_written += 1
        if rows_written >= max_rows:
            output.write("... (截断)")
            break
    wb.close()
    text = output.getvalue().strip()
    return f"工作表: {sheet.title}\n{text}" if text else "(空表格)"


# ── 批量重命名 ──

def _compute_new_name(f: Path, index: int, mode: str, value: str) -> str | None:
    """计算重命名后的文件名，不支持的模式返回 None。"""
    stem = f.stem
    suffix = f.suffix
    if mode == "prefix":
        return f"{value}{stem}{suffix}"
    if mode == "suffix":
        return f"{stem}{value}{suffix}"
    if mode == "replace":
        parts = value.split("|", 1)
        old = parts[0]
        new = parts[1] if len(parts) > 1 else ""
        return f.name.replace(old, new)
    if mode == "number":
        prefix = value or "file_"
        return f"{prefix}{index:03d}{suffix}"
    return None


@register_tool(
    name="batch_rename",
    description="批量重命名文件。mode: prefix=添加前缀 / suffix=添加后缀 / replace=替换字符串 / number=按编号",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "目标目录"},
            "pattern": {"type": "string", "description": "匹配模式，如 *.txt"},
            "mode": {"type": "string", "enum": ["prefix", "suffix", "replace", "number"]},
            "value": {"type": "string", "description": "重命名参数（前缀/后缀/替换串/编号前缀）"},
            "dry_run": {"type": "boolean", "description": "是否仅预览，不实际执行"},
        },
        "required": ["path", "mode", "value"],
    },
)
def batch_rename(
    path: str,
    pattern: str = "*",
    mode: str = "prefix",
    value: str = "",
    dry_run: bool = False,
) -> str:
    """批量重命名文件。
    mode=prefix: 添加前缀
    mode=suffix: 添加后缀
    mode=replace: 替换文件名中的字符串 (value 格式: old|new)
    mode=number: 按编号重命名 (value 格式: prefix_)
    """
    target = _resolve(path)
    if not target.is_dir():
        return f"不是有效目录: {target}"

    files = sorted([f for f in target.iterdir() if f.is_file() and f.match(pattern)])
    if not files:
        return f"未找到匹配文件 (pattern={pattern})"

    # ── 预览模式：只收集计划不执行 ──
    plans: list[str] = []
    for i, f in enumerate(files, 1):
        new_name = _compute_new_name(f, i, mode, value)
        if new_name is None:
            return f"不支持的 rename mode: {mode}"
        plans.append(f"{f.name} -> {new_name}")

    if dry_run:
        return f"预览 {len(files)} 个重命名:\n" + "\n".join(plans)

    # ── 执行重命名 ──
    renamed = 0
    for i, f in enumerate(files, 1):
        new_name = _compute_new_name(f, i, mode, value)
        if new_name is None:
            continue
        new_path = target / new_name
        if new_path.exists() and new_path != f:
            new_name = f"{f.stem}_renamed{i}{f.suffix}"
            new_path = target / new_name
        f.rename(new_path)
        renamed += 1

    return f"已重命名 {renamed} 个文件"


# ── 查找重复文件 ──

def _file_hash(filepath: Path, chunk_size: int = 8192) -> str:
    hasher = hashlib.md5()
    with filepath.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


@register_tool(
    name="find_duplicates",
    description="在目录中按 MD5 查找重复文件",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "扫描目录"},
            "max_files": {"type": "integer", "description": "最多扫描文件数"},
        },
        "required": ["path"],
    },
)
def find_duplicates(path: str, max_files: int = 500) -> str:
    """查找目录中的重复文件（按 MD5 比较）"""
    target = _resolve(path)
    if not target.is_dir():
        return f"不是有效目录: {target}"

    # 先按文件大小粗筛
    size_map: dict[int, list[Path]] = defaultdict(list)
    count = 0
    for item in target.rglob("*"):
        if not item.is_file():
            continue
        try:
            size_map[item.stat().st_size].append(item)
        except OSError:
            continue
        count += 1
        if count >= max_files:
            break

    # 只检查同大小的文件组
    lines: list[str] = []
    scanned = 0
    dupes = 0
    for files in size_map.values():
        if len(files) < 2:
            continue
        hash_map: dict[str, list[Path]] = defaultdict(list)
        for f in files:
            try:
                h = _file_hash(f)
                hash_map[h].append(f)
            except OSError:
                continue
            scanned += 1
        for h, group in hash_map.items():
            if len(group) < 2:
                continue
            sizes = sum(g.stat().st_size for g in group)
            lines.append(f"MD5 {h[:8]} | {len(group)} 个文件 | {sizes} bytes")
            for g in group:
                lines.append(f"    {g}")
            dupes += len(group) - 1

    if not lines:
        return f"扫描 {scanned} 个文件，未发现重复"
    header = f"扫描 {scanned} 个文件，发现 {dupes} 个重复\n"
    return header + "\n".join(lines)


# ── 压缩 / 解压 ──

@register_tool(
    name="zip_files",
    description="将多个文件或文件夹压缩为 zip 包",
    parameters={
        "type": "object",
        "properties": {
            "sources": {
                "type": "array",
                "items": {"type": "string"},
                "description": "要压缩的文件或文件夹路径列表",
            },
            "output": {"type": "string", "description": "输出 zip 文件路径"},
            "root_dir": {"type": "string", "description": "压缩包内路径的基准目录"},
        },
        "required": ["sources", "output"],
    },
)
def zip_files(
    sources: list[str],
    output: str,
    root_dir: str | None = None,
) -> str:
    """将多个文件/文件夹压缩为 zip"""
    output_path = _resolve(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    base = _resolve(root_dir) if root_dir else None
    count = 0
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for src_raw in sources:
            src = _resolve(src_raw)
            if not src.exists():
                continue
            if src.is_dir():
                for f in src.rglob("*"):
                    if not f.is_file():
                        continue
                    arcname = str(f.relative_to(base)) if base else str(f.relative_to(src.parent))
                    zf.write(f, arcname)
                    count += 1
            else:
                arcname = str(src.relative_to(base)) if base else src.name
                zf.write(src, arcname)
                count += 1

    size_mb = output_path.stat().st_size / (1024 * 1024)
    return f"已压缩 {count} 个文件 -> {output_path} ({size_mb:.1f} MB)"


@register_tool(
    name="unzip_file",
    description="解压 zip 文件",
    parameters={
        "type": "object",
        "properties": {
            "source": {"type": "string", "description": "zip 文件路径"},
            "output_dir": {"type": "string", "description": "解压目标目录"},
        },
        "required": ["source", "output_dir"],
    },
)
def unzip_file(source: str, output_dir: str) -> str:
    """解压 zip 文件"""
    src = _resolve(source)
    out = _resolve(output_dir)
    if not src.exists():
        return f"文件不存在: {src}"
    out.mkdir(parents=True, exist_ok=True)

    count = 0
    with zipfile.ZipFile(src, "r") as zf:
        zf.extractall(out)
        count = len(zf.namelist())

    return f"已解压 {count} 个文件 -> {out}"


# ── 新增工具：截图 / 剪贴板 ──

@register_tool(
    name="screenshot",
    description="截取当前屏幕并保存为 PNG 文件",
    parameters={
        "type": "object",
        "properties": {
            "output_path": {"type": "string", "description": "截图保存路径（.png）"},
        },
        "required": ["output_path"],
    },
)
def screenshot(output_path: str) -> str:
    target = _resolve(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        img.save(str(target), "PNG")
        return f"截图已保存: {target} ({img.width}x{img.height})"
    except ImportError:
        return "需要安装 Pillow: pip install pillow"
    except Exception as e:
        return f"截图失败: {e}"


@register_tool(
    name="clipboard_read",
    description="读取剪贴板中的文本内容",
    parameters={"type": "object", "properties": {}},
)
def clipboard_read() -> str:
    try:
        import pyperclip
        text = pyperclip.paste()
        if not text:
            return "(剪贴板为空)"
        if len(text) > 3000:
            text = text[:3000] + "\n... (已截断)"
        return text
    except ImportError:
        return "需要安装 pyperclip: pip install pyperclip"


@register_tool(
    name="clipboard_write",
    description="将文本写入剪贴板",
    parameters={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "要写入剪贴板的文本"},
        },
        "required": ["text"],
    },
)
def clipboard_write(text: str) -> str:
    try:
        import pyperclip
        pyperclip.copy(text)
        return f"已写入剪贴板 ({len(text)} 字符)"
    except ImportError:
        return "需要安装 pyperclip: pip install pyperclip"
