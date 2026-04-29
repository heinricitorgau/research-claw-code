from __future__ import annotations

from local_ai.prompt_loader import load_prompt_profile


def test_traditional_chinese_prompt_loads_correctly() -> None:
    prompt = load_prompt_profile("default_zh_tw")
    assert "繁體中文" in prompt
    assert "不要聲稱你能上網" in prompt
