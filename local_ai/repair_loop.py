#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from typing import Any, Callable


Checker = Callable[[str, str], dict[str, Any]]
Generator = Callable[[str], str]


def build_repair_prompt(
    user_text: str,
    previous_answer: str,
    checker_result: dict[str, Any],
) -> str:
    return (
        "請修正上一個回答，只修正 checker JSON 列出的問題。\n"
        "請保持離線模式，不要建議需要網路的指令，除非使用者明確要求其他語言，請使用繁體中文。\n\n"
        f"原始問題：\n{user_text}\n\n"
        f"上一個回答：\n{previous_answer}\n\n"
        "checker JSON：\n"
        f"{json.dumps(checker_result, ensure_ascii=False, indent=2)}\n"
    )


def run_repair_loop(
    user_text: str,
    generate_answer: Generator,
    check_answer: Checker,
    max_retries: int | None = None,
) -> dict[str, Any]:
    retries = int(os.environ.get("CLAW_MAX_REPAIR_RETRIES", "2")) if max_retries is None else max_retries
    prompt = user_text
    answer = generate_answer(prompt)
    best_answer = answer
    best_result = check_answer(answer, user_text)
    attempts = 0
    while attempts < retries and not best_result.get("ok", False):
        attempts += 1
        prompt = build_repair_prompt(user_text, answer, best_result)
        answer = generate_answer(prompt)
        result = check_answer(answer, user_text)
        if result.get("score", 0) >= best_result.get("score", 0):
            best_answer = answer
            best_result = result
        if result.get("ok", False):
            best_answer = answer
            best_result = result
            break
    return {
        "ok": bool(best_result.get("ok", False)),
        "answer": best_answer,
        "checker": best_result,
        "attempts": attempts,
        "max_retries": retries,
    }


def append_checker_warnings(answer: str, checker_result: dict[str, Any]) -> str:
    if checker_result.get("ok", False):
        return answer
    issues = checker_result.get("issues", [])
    if not issues:
        return answer
    warning_lines = ["", "", "本地檢查警告："]
    warning_lines.extend(f"- {issue}" for issue in issues)
    return answer.rstrip() + "\n".join(warning_lines)
