"""发版 extensions 对账逻辑（P0-3）。"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT_ROOT = ROOT / "extensions"
PPT_MARKER = EXT_ROOT / "ppt-master" / "scripts" / "svg_to_pptx.py"

REQUIRED_MANIFESTS = (
    "vision-bridge/friday-plugin.json",
    "storage-analyzer/friday-plugin.json",
    "ppt-master/friday-plugin.json",
    "file-safety/friday-plugin.json",
    "karpathy-guidelines/friday-plugin.json",
)


def _list_extension_manifests(base: Path) -> set[str]:
    found: set[str] = set()
    if not base.is_dir():
        return found
    for manifest in base.glob("*/friday-plugin.json"):
        rel = manifest.relative_to(base).as_posix()
        found.add(f"{manifest.parent.name}/friday-plugin.json")
    return found


def test_source_extensions_have_core_manifests():
    manifests = _list_extension_manifests(EXT_ROOT)
    for rel in REQUIRED_MANIFESTS:
        assert rel in manifests, f"missing extensions/{rel}"


def test_ppt_master_sync_marker_documented_for_release():
    """make-release 发版前会 sync；仓库 dev 环境可能尚未拉 skill，仅断言 sync 脚本存在。"""
    sync_script = ROOT / "scripts" / "sync_ppt_master_skill.ps1"
    assert sync_script.is_file()
    if PPT_MARKER.is_file():
        assert (EXT_ROOT / "ppt-master" / "SKILL.md").is_file()


def test_verify_release_extensions_script_exists():
    assert (ROOT / "scripts" / "verify-release-extensions.ps1").is_file()
