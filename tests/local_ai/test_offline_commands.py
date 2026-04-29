from __future__ import annotations

from pathlib import Path


def test_runtime_commands_do_not_attempt_internet_access() -> None:
    run_sh = Path("local_ai/run.sh").read_text(encoding="utf-8")
    run_ps1 = Path("local_ai/run.ps1").read_text(encoding="utf-8")
    combined = run_sh + "\n" + run_ps1
    forbidden = ("pip install", "npm install", "cargo install", "ollama pull")
    assert not any(item in combined for item in forbidden)
