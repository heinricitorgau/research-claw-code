#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path


DEFAULT_PROFILE = "default_zh_tw"


def _base_dir() -> Path:
    return Path(__file__).resolve().parent


def resolve_prompt_dir(prompt_dir: str | None = None) -> Path:
    raw = prompt_dir or os.environ.get("CLAW_PROMPT_DIR")
    if raw:
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = (_base_dir().parent / path).resolve()
        return path
    return _base_dir() / "prompts"


def load_prompt_profile(
    profile: str | None = None,
    prompt_dir: str | None = None,
    override_prompt: str | None = None,
) -> str:
    if override_prompt and override_prompt.strip():
        return override_prompt.strip()

    selected = (profile or os.environ.get("CLAW_PROMPT_PROFILE") or DEFAULT_PROFILE).strip()
    if not selected:
        selected = DEFAULT_PROFILE
    if selected.endswith(".md"):
        filename = selected
    else:
        filename = f"{selected}.md"

    directory = resolve_prompt_dir(prompt_dir)
    path = directory / filename
    if not path.exists():
        fallback = directory / f"{DEFAULT_PROFILE}.md"
        if fallback.exists():
            return fallback.read_text(encoding="utf-8").strip()
        return (
            "你是離線終端機助理。除非使用者明確要求其他語言，永遠使用繁體中文回答。"
            "不要聲稱你能上網，也不要建議需要網路的指令。"
        )
    return path.read_text(encoding="utf-8").strip()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Load a local claw prompt profile")
    parser.add_argument("--profile", default=None)
    parser.add_argument("--prompt-dir", default=None)
    args = parser.parse_args()
    print(load_prompt_profile(args.profile, args.prompt_dir))


if __name__ == "__main__":
    main()
