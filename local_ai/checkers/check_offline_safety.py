#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from typing import Any


INTERNET_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bpip\s+install\b", "包含 pip install，離線環境可能無法執行"),
    (r"\bnpm\s+install\b", "包含 npm install，離線環境可能無法執行"),
    (r"\bcargo\s+install\b", "包含 cargo install，離線環境可能無法執行"),
    (r"\bollama\s+pull\b", "包含 ollama pull，離線環境不能下載模型"),
    (r"\bapt(?:-get)?\s+install\b", "包含 apt install，離線環境可能無法執行"),
    (r"\bbrew\s+install\b", "包含 brew install，離線環境可能無法執行"),
    (r"\bInvoke-WebRequest\b|\biwr\b", "包含下載指令，離線環境可能無法執行"),
    (r"\bcurl\s+https?://|\bwget\s+https?://", "包含外部網址下載指令"),
)

DESTRUCTIVE_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\brm\s+-rf\s+/(?:\s|$)", "包含危險的 rm -rf /"),
    (r"\brm\s+-rf\s+\*", "包含危險的 rm -rf *"),
    (r"\bdel\s+/s\s+/q\b", "包含大量刪除檔案的 Windows 指令"),
    (r"\bformat\s+[A-Za-z]:", "包含格式化磁碟指令"),
    (r"\bdd\s+if=.*\bof=/dev/", "包含可能覆寫磁碟的 dd 指令"),
)


def _result(ok: bool, score: float, issues: list[str], suggestions: list[str]) -> dict[str, Any]:
    return {
        "ok": ok,
        "score": round(max(0.0, min(1.0, score)), 2),
        "issues": issues,
        "suggestions": suggestions,
    }


def check_offline_safety(text: str, user_text: str = "") -> dict[str, Any]:
    issues: list[str] = []
    suggestions: list[str] = []
    for pattern, message in INTERNET_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            issues.append(message)
    explicit_destructive = any(
        marker in user_text.lower()
        for marker in ("刪除", "清掉", "delete", "remove", "format", "wipe")
    )
    if not explicit_destructive:
        for pattern, message in DESTRUCTIVE_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                issues.append(message)

    if issues:
        suggestions.append("改用本機已存在的檔案、文件、工具或已打包資源")
        suggestions.append("移除需要網路或高風險破壞性操作的指令")
    return _result(not issues, 1.0 - 0.18 * len(issues), issues, suggestions)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Check offline safety of an answer")
    parser.add_argument("path", nargs="?", help="Answer file; stdin is used when omitted")
    parser.add_argument("--user-text", default="")
    args = parser.parse_args()
    if args.path:
        with open(args.path, "r", encoding="utf-8") as handle:
            text = handle.read()
    else:
        import sys

        text = sys.stdin.read()
    print(json.dumps(check_offline_safety(text, args.user_text), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
