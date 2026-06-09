"""model_providers 预设与推断测试。"""

from friday.custom_endpoints import switch_category_provider
from friday.model_providers import (
    default_image_gen_base_url,
    infer_llm_provider,
    infer_vision_provider,
    normalize_image_gen_model,
    normalize_vision_model,
    providers_catalog,
)
from friday.storage import UserSettings


def test_providers_catalog_has_three_kinds():
    cat = providers_catalog()
    assert "llm" in cat and len(cat["llm"]) >= 5
    assert "vision" in cat and len(cat["vision"]) >= 4
    assert "image_gen" in cat and len(cat["image_gen"]) >= 4


def test_infer_llm_provider_from_base_url():
    s = UserSettings(base_url="https://api.deepseek.com", llm_provider="")
    assert infer_llm_provider(s) == "deepseek"
    s = UserSettings(base_url="https://api.openai.com/v1", llm_provider="")
    assert infer_llm_provider(s) == "openai"
    s = UserSettings(base_url="https://api.example.com/v1", llm_provider="")
    assert infer_llm_provider(s) == "deepseek"


def test_infer_llm_provider_mimo_host():
    s = UserSettings(base_url="https://api.xiaomimimo.com/v1", llm_provider="")
    assert infer_llm_provider(s) == "mimo"


def test_infer_llm_provider_respects_stored():
    s = UserSettings(base_url="https://api.openai.com/v1", llm_provider="deepseek")
    assert infer_llm_provider(s) == "deepseek"


def test_infer_vision_provider_from_base_url():
    s = UserSettings(vision_base_url="https://ark.cn-beijing.volces.com/api/v3", vision_provider="")
    assert infer_vision_provider(s) == "ark"
    s = UserSettings(vision_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1", vision_provider="")
    assert infer_vision_provider(s) == "qwen_vl"


def test_infer_vision_provider_mimo_host():
    s = UserSettings(vision_base_url="https://api.xiaomimimo.com/v1", vision_provider="")
    assert infer_vision_provider(s) == "mimo"


def test_normalize_vision_model_rejects_mismatch():
    assert normalize_vision_model("ark", "mimo-v2.5") == ""
    assert normalize_vision_model("mimo", "mimo-v2.5") == "mimo-v2.5"
    assert normalize_vision_model("mimo", "mimo-v2.5-pro") == "mimo-v2.5"
    assert normalize_vision_model("ark", "ep-20260101") == "ep-20260101"


def test_switch_vision_provider_resets_invalid_model():
    settings = UserSettings(
        vision_provider="ark",
        vision_base_url="https://ark.cn-beijing.volces.com/api/v3",
        vision_model="mimo-v2.5",
    )
    switched = switch_category_provider(settings, "vision", "mimo")
    assert switched.vision_provider == "mimo"
    assert switched.vision_model == "mimo-v2.5"
    assert switched.vision_base_url == "https://api.xiaomimimo.com/v1"


def test_default_image_gen_base_url_by_provider():
    assert "zhima" in default_image_gen_base_url("openai_compat")
    assert "volces" in default_image_gen_base_url("ark")
    assert "openai.com" in default_image_gen_base_url("openai")


def test_normalize_image_gen_model_rejects_mismatch():
    assert normalize_image_gen_model("ark", "ep-20260609014727-895pn") == "ep-20260609014727-895pn"
    assert normalize_image_gen_model("openai_compat", "ep-20260609014727-895pn") == ""
    assert normalize_image_gen_model("openai", "dall-e-3") == "dall-e-3"
    assert normalize_image_gen_model("openai", "ep-20260101") == "dall-e-3"
    assert normalize_image_gen_model("mimo", "mimo-v2.5") == ""


def test_switch_image_gen_provider_resets_ark_endpoint():
    settings = UserSettings(
        image_gen_provider="ark",
        image_gen_api_key="ark-key-12345678",
        image_gen_base_url="https://ark.cn-beijing.volces.com/api/v3",
        image_gen_model="ep-20260609014727-895pn",
    )
    switched = switch_category_provider(settings, "image_gen", "openai_compat")
    assert switched.image_gen_provider == "openai_compat"
    assert switched.image_gen_model == ""
    assert switched.image_gen_api_key == ""
    assert "zhima" in switched.image_gen_base_url
