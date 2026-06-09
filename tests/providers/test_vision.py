from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from friday.storage import UserSettings, merge_settings, save_settings, load_settings
from friday.vision import describe_image, vision_config_hint, vision_ready, masked_vision_key
from friday.safety import RiskLevel, classify_tool


def test_vision_ready_requires_enabled_and_key():
    assert not vision_ready(UserSettings())
    assert not vision_ready(UserSettings(vision_enabled=True, vision_api_key=""))
    assert not vision_ready(
        UserSettings(
            vision_enabled=True,
            vision_api_key="ark-test-key-12345678",
            vision_model="",
        )
    )
    assert vision_ready(
        UserSettings(
            vision_enabled=True,
            vision_api_key="ark-test-key-12345678",
            vision_model="ep-20260609014629-l67jd",
        )
    )


def test_vision_config_hint_rejects_sk_key_on_ark():
    settings = UserSettings(
        vision_enabled=True,
        vision_provider="ark",
        vision_api_key="sk-wrong-key-12345678",
        vision_model="ep-20260609014629-l67jd",
    )
    assert not vision_ready(settings)
    assert "ark-" in vision_config_hint(settings)


def test_describe_image_not_configured():
    msg = describe_image(UserSettings(), "/tmp/x.png")
    assert "未配置" in msg


def test_describe_image_missing_file(tmp_path: Path):
    settings = UserSettings(
        vision_enabled=True,
        vision_api_key="ark-test-key-12345678",
        vision_model="ep-20260609014629-l67jd",
    )
    msg = describe_image(settings, str(tmp_path / "missing.png"))
    assert "找不到图片" in msg


def test_describe_image_success(tmp_path: Path):
    img = tmp_path / "test.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)

    settings = UserSettings(
        vision_enabled=True,
        vision_api_key="ark-test-key-12345678",
        vision_model="ep-test",
    )

    mock_choice = MagicMock()
    mock_choice.message.content = "这是一张测试图片"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch("openai.OpenAI", return_value=mock_client):
        result = describe_image(settings, str(img))

    assert result == "这是一张测试图片"
    mock_client.chat.completions.create.assert_called_once()


def test_describe_image_classified_read():
    assert classify_tool("describe_image") == RiskLevel.READ
    assert classify_tool("vision_status") == RiskLevel.READ


def test_test_vision_requires_endpoint():
    from friday.vision import test_vision_connection

    ok, msg = test_vision_connection(
        UserSettings(
            vision_enabled=True,
            vision_api_key="ark-test-key-12345678",
            vision_model="",
        )
    )
    assert not ok
    assert "ep-" in msg or "端点" in msg


def test_test_vision_image_call(tmp_appdata):
    from friday.vision import test_vision_connection

    settings = UserSettings(
        vision_enabled=True,
        vision_api_key="ark-test-key-12345678",
        vision_model="ep-test-vision",
    )
    mock_choice = MagicMock()
    mock_choice.message.content = "ok"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch("openai.OpenAI", return_value=mock_client):
        ok, msg = test_vision_connection(settings)

    assert ok
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    content = call_kwargs["messages"][0]["content"]
    assert any(item.get("type") == "image_url" for item in content)


def test_describe_image_compresses_large_png(tmp_path: Path):
    from friday.vision import _COMPRESS_IF_OVER, optimize_image_bytes

    try:
        from PIL import Image
        import random
    except ImportError:
        pytest.skip("Pillow not installed")

    img_path = tmp_path / "big.png"
    img = Image.new("RGB", (2400, 1600))
    pixels = img.load()
    rng = random.Random(0)
    for y in range(0, 1600, 4):
        for x in range(0, 2400, 4):
            pixels[x, y] = (rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255))
    img.save(img_path, format="PNG")
    raw = img_path.read_bytes()
    assert len(raw) > _COMPRESS_IF_OVER

    data, mime = optimize_image_bytes(raw)
    assert mime == "image/jpeg"
    assert len(data) < len(raw)


def test_compose_chat_message_with_prefetch():
    from friday.vision import compose_chat_message

    msg = compose_chat_message("这是什么", "/x/a.png", "界面显示下载确认框")
    assert "截图视觉分析" in msg
    assert "勿再调用 describe_image" in msg
    assert "这是什么" in msg


def test_compose_chat_message_multiple_images():
    from friday.vision import compose_chat_message

    paths = ["/x/a.png", "/x/b.png"]
    msg = compose_chat_message("对比这两张图", image_paths=paths)
    assert "2 张截图" in msg
    assert "/x/a.png" in msg
    assert "/x/b.png" in msg
    assert "对比这两张图" in msg

    summary = "【图1】按钮\n【图2】菜单"
    msg2 = compose_chat_message("有何不同", vision_summary=summary, image_paths=paths)
    assert "截图视觉分析" in msg2
    assert summary in msg2
    assert "有何不同" in msg2


def test_vision_api_key_encryption_roundtrip(tmp_appdata):
    original = UserSettings(vision_api_key="ark-secret-vision-key-99")
    save_settings(original)
    loaded = load_settings()
    assert loaded.vision_api_key == "ark-secret-vision-key-99"
    assert masked_vision_key(loaded).startswith("ark-")


def test_merge_settings_preserves_empty_vision_key():
    current = UserSettings(vision_api_key="ark-keep-me")
    merged = merge_settings(current, {"vision_api_key": "", "vision_enabled": True})
    assert merged.vision_api_key == "ark-keep-me"
    assert merged.vision_enabled is True
