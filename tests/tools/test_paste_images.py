from __future__ import annotations

import base64

import pytest

from friday.paste_images import save_pasted_image
from friday.storage import UserSettings


def test_save_pasted_image_png(tmp_appdata, workspace, monkeypatch: pytest.MonkeyPatch):
    settings = UserSettings(workspace=str(workspace))
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    path, filename = save_pasted_image(
        settings,
        image_base64=base64.b64encode(png_bytes).decode("ascii"),
        mime_type="image/png",
    )
    assert filename.startswith("paste-")
    assert filename.endswith(".png")
    assert path.replace("\\", "/").startswith(str(workspace).replace("\\", "/"))
    assert (workspace / "粘贴的截图" / filename).is_file()


def test_save_pasted_image_rejects_large(tmp_appdata, workspace):
    settings = UserSettings(workspace=str(workspace))
    huge = base64.b64encode(b"x" * (10 * 1024 * 1024 + 1)).decode("ascii")
    with pytest.raises(ValueError, match="过大"):
        save_pasted_image(settings, image_base64=huge, mime_type="image/png")
