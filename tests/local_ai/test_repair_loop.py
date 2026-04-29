from __future__ import annotations

from local_ai.repair_loop import run_repair_loop


def test_repair_loop_stops_after_max_retries() -> None:
    calls = {"count": 0}

    def generate(_: str) -> str:
        calls["count"] += 1
        return "bad answer"

    def check(answer: str, user_text: str) -> dict[str, object]:
        return {"ok": False, "score": 0.1, "issues": ["still bad"], "suggestions": []}

    result = run_repair_loop("question", generate, check, max_retries=2)
    assert not result["ok"]
    assert result["attempts"] == 2
    assert calls["count"] == 3
