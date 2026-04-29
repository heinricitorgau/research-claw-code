#!/usr/bin/env python3
from __future__ import annotations

import json
from typing import Any

try:
    from .check_offline_safety import check_offline_safety
except ImportError:  # pragma: no cover
    from check_offline_safety import check_offline_safety


def check_markdown_answer(text: str, user_text: str = "") -> dict[str, Any]:
    issues: list[str] = []
    suggestions: list[str] = []
    if "```" in text and text.count("```") % 2 != 0:
        issues.append("Markdown code block is not closed")
        suggestions.append("Close every fenced code block")
    if not text.strip():
        issues.append("Answer is empty")
        suggestions.append("Provide a concise answer")

    safety = check_offline_safety(text, user_text)
    issues.extend(safety["issues"])
    suggestions.extend(safety["suggestions"])
    ok = not issues
    score = min(0.95, safety["score"]) - 0.2 * (len(issues) - len(safety["issues"]))
    return {
        "ok": ok,
        "score": round(max(0.0, score), 2),
        "issues": issues,
        "suggestions": suggestions,
    }


def main() -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Check a Markdown answer")
    parser.add_argument("path", nargs="?")
    args = parser.parse_args()
    text = open(args.path, encoding="utf-8").read() if args.path else sys.stdin.read()
    print(json.dumps(check_markdown_answer(text), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
