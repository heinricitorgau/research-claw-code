#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from typing import Any

try:
    from .check_offline_safety import check_offline_safety
except ImportError:  # pragma: no cover
    from check_offline_safety import check_offline_safety


C_FORBIDDEN_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bstd::", "Contains C++ namespace std::"),
    (r"\bcout\s*<<|\bcin\s*>>", "Contains C++ iostream syntax"),
    (r"\bclass\b|\btemplate\s*<|\bnamespace\b", "Contains obvious C++ syntax"),
    (r"\bvector\s*<|\bstring\b", "Contains C++ STL types"),
    (r"\bdef\s+\w+\s*\(", "Contains Python function syntax"),
    (r"\bconsole\.log\s*\(", "Contains JavaScript syntax"),
)


def extract_code_block(text: str, language: str | None = "c") -> str:
    matches = list(re.finditer(r"```(?P<lang>[^\n`]*)\n(?P<code>.*?)```", text, re.DOTALL))
    if not matches:
        return text.strip()
    if language:
        for match in matches:
            lang = match.group("lang").strip().lower()
            if lang in (language.lower(), "c99", "c11"):
                return match.group("code").strip()
    return matches[0].group("code").strip()


def _balanced_braces(code: str) -> bool:
    depth = 0
    in_string: str | None = None
    escape = False
    for ch in code:
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == in_string:
                in_string = None
            continue
        if ch in ("'", '"'):
            in_string = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0 and in_string is None


def _find_c_compiler() -> str | None:
    for candidate in ("gcc", "clang", "cc"):
        found = shutil.which(candidate)
        if found:
            return found
    return None


def _compile_check(code: str) -> str | None:
    compiler = _find_c_compiler()
    if not compiler:
        return None
    with tempfile.NamedTemporaryFile("w", suffix=".c", delete=False, encoding="utf-8") as handle:
        handle.write(code)
        path = handle.name
    try:
        result = subprocess.run(
            [compiler, "-std=c11", "-Wall", "-Wextra", "-fsyntax-only", path],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except Exception as exc:
        return f"Compiler check failed to run: {exc}"
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    if result.returncode == 0:
        return ""
    return (result.stderr or result.stdout).strip() or "C code does not compile"


def _has_test_case(text: str) -> bool:
    lowered = text.lower()
    markers = (
        "測試輸入",
        "測試輸出",
        "sample input",
        "sample output",
        "input:",
        "output:",
        "輸入：",
        "輸出：",
    )
    return any(marker in lowered for marker in markers)


def check_c_answer(text: str, user_text: str = "") -> dict[str, Any]:
    code = extract_code_block(text, "c")
    issues: list[str] = []
    suggestions: list[str] = []

    for pattern, message in C_FORBIDDEN_PATTERNS:
        if re.search(pattern, code):
            issues.append(message)

    if not re.search(r"\bint\s+main\s*\(", code):
        issues.append("Missing int main")
        suggestions.append("Add a complete main function")

    uses_printf_scanf = bool(re.search(r"\b(?:printf|scanf|puts|getchar|putchar)\s*\(", code))
    if uses_printf_scanf and "#include <stdio.h>" not in code:
        issues.append("Missing #include <stdio.h>")
        suggestions.append("Include #include <stdio.h> for standard input/output")

    if not _balanced_braces(code):
        issues.append("Unbalanced braces or quotes")
        suggestions.append("Check that every {, }, quote, and code block is closed")

    if not _has_test_case(text):
        issues.append("Missing test input/output")
        suggestions.append("Add at least one sample run")

    compiler_error = _compile_check(code)
    if compiler_error:
        issues.append("C code does not compile")
        suggestions.append(compiler_error[:500])

    safety = check_offline_safety(text, user_text)
    issues.extend(safety["issues"])
    suggestions.extend(safety["suggestions"])

    # Deduplicate while preserving order.
    issues = list(dict.fromkeys(issues))
    suggestions = list(dict.fromkeys(suggestions))
    score = 1.0 - 0.15 * len(issues)
    if compiler_error:
        score -= 0.2
    return {
        "ok": not issues,
        "score": round(max(0.0, min(1.0, score)), 2),
        "issues": issues,
        "suggestions": suggestions,
    }


def main() -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Check a C programming answer")
    parser.add_argument("path", nargs="?")
    parser.add_argument("--user-text", default="")
    args = parser.parse_args()
    text = open(args.path, encoding="utf-8").read() if args.path else sys.stdin.read()
    print(json.dumps(check_c_answer(text, args.user_text), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
