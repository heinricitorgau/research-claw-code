#!/usr/bin/env python3
"""Offline C exam evaluation runner.

The runner intentionally stays dependency-free: Python standard library,
local_ai/run.sh for model calls, and an installed C compiler are enough.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
AI_TIMEOUT_SECONDS = 300


def default_eval_dir() -> Path:
    """Get default eval cases directory."""
    return Path(__file__).resolve().parent / "eval_cases" / "c_exam"


def case_points(case: dict[str, Any]) -> float:
    """Read a case point value defensively from JSON."""
    try:
        return float(case.get("points", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def display_points(points: float) -> int | float:
    """Keep integer point totals tidy in console and JSON summaries."""
    return int(points) if points.is_integer() else points


def local_ai_run_script() -> Path:
    """Return the repo-local local_ai/run.sh regardless of caller cwd."""
    local_ai_dir = Path(__file__).resolve().parent
    return local_ai_dir / "run.sh"


def load_eval_cases(eval_dir: Path | None = None) -> list[dict[str, Any]]:
    """Load all JSON eval case files."""
    directory = eval_dir or default_eval_dir()
    cases = []
    for json_file in sorted(directory.glob("*.json")):
        try:
            case = json.loads(json_file.read_text(encoding="utf-8"))
            case["_filename"] = json_file.name
            cases.append(case)
        except json.JSONDecodeError as e:
            print(f"Warning: error loading {json_file.name}: {e}", file=sys.stderr)
    return cases


def normalize_model_output(text: str) -> str:
    """Remove terminal noise and normalize model output before extraction."""
    normalized = ANSI_RE.sub("", text)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")

    noisy_patterns = (
        r"^\s*[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏].*Thinking.*$",
        r"^\s*.*Thinking[.…。]*\s*$",
        r"^\s*✔ .*Done\s*$",
        r"^\s*╭─\s*c\s*$",
        r"^\s*╰.*$",
    )
    for pattern in noisy_patterns:
        normalized = re.sub(pattern, "", normalized, flags=re.IGNORECASE | re.MULTILINE)

    return normalized.strip()


def mask_c_comments_and_strings(code: str) -> str:
    """Mask strings/comments so brace validation is not confused by printf text."""
    out: list[str] = []
    i = 0
    state = "code"
    while i < len(code):
        ch = code[i]
        nxt = code[i + 1] if i + 1 < len(code) else ""

        if state == "code":
            if ch == "/" and nxt == "/":
                out.extend("  ")
                i += 2
                state = "line_comment"
                continue
            if ch == "/" and nxt == "*":
                out.extend("  ")
                i += 2
                state = "block_comment"
                continue
            if ch == '"':
                out.append(" ")
                i += 1
                state = "string"
                continue
            if ch == "'":
                out.append(" ")
                i += 1
                state = "char"
                continue
            out.append(ch)
        elif state == "line_comment":
            out.append("\n" if ch == "\n" else " ")
            if ch == "\n":
                state = "code"
        elif state == "block_comment":
            out.append("\n" if ch == "\n" else " ")
            if ch == "*" and nxt == "/":
                out.append(" ")
                i += 1
                state = "code"
        elif state == "string":
            out.append("\n" if ch == "\n" else " ")
            if ch == "\\" and nxt:
                out.append(" ")
                i += 1
            elif ch == '"':
                state = "code"
        elif state == "char":
            out.append("\n" if ch == "\n" else " ")
            if ch == "\\" and nxt:
                out.append(" ")
                i += 1
            elif ch == "'":
                state = "code"
        i += 1
    return "".join(out)


def has_balanced_braces(code: str) -> bool:
    """Return True when braces are balanced and never close before opening."""
    masked = mask_c_comments_and_strings(code)
    depth = 0
    for ch in masked:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def validate_c_code(code: str) -> bool:
    """Validate extracted text as a minimal complete C program."""
    return bool(
        code
        and "#include" in code
        and re.search(r"\bint\s+main\s*\(", code)
        and has_balanced_braces(code)
    )


def extract_until_main_closing_brace(text: str, start: int, main_match: re.Match[str]) -> str:
    """Capture a C translation unit from first include through main's closing brace."""
    masked = mask_c_comments_and_strings(text)
    open_at = masked.find("{", main_match.end())
    if open_at < 0:
        return ""

    depth = 0
    for idx in range(open_at, len(masked)):
        ch = masked[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1].strip()
            if depth < 0:
                return ""
    return ""


def heuristic_extract_c_code(text: str) -> str:
    """Find a region containing #include and int main, ending at main's close brace."""
    include_at = text.find("#include")
    main_match = re.search(r"\bint\s+main\s*\(", text)
    if include_at < 0 or not main_match:
        return ""

    start = include_at if include_at < main_match.start() else max(include_at, 0)
    code = extract_until_main_closing_brace(text, start, main_match)
    return code if validate_c_code(code) else ""


def debug_extraction_failure(raw_output: str) -> None:
    print("[debug] raw model output:", file=sys.stderr)
    print(raw_output[:500], file=sys.stderr)
    print("[debug] extraction failed", file=sys.stderr)


def extract_c_code(text: str, *, debug: bool = True) -> str:
    """Extract and validate C code from markdown, CLI output, or plain text."""
    normalized = normalize_model_output(text)

    matches = re.findall(r"```c(.*?)```", normalized, re.DOTALL | re.IGNORECASE)
    for match in matches:
        code = match.strip()
        if validate_c_code(code):
            return code

    matches = re.findall(r"```(.*?)```", normalized, re.DOTALL)
    for match in matches:
        code = match.strip()
        if validate_c_code(code):
            return code

    code = heuristic_extract_c_code(normalized)
    if code:
        return code

    if debug:
        debug_extraction_failure(text)
    return ""


def find_c_compiler() -> str | None:
    """Find available C compiler: cc, gcc, or clang."""
    for compiler in ("cc", "gcc", "clang"):
        path = shutil.which(compiler)
        if path:
            return path
    return None


def compile_c_code(code: str, work_dir: Path, case_id: str) -> tuple[bool, str, Path | None]:
    """Compile C code and return (success, message, executable_path)."""
    compiler = find_c_compiler()
    if not compiler:
        return False, "No C compiler found (cc/gcc/clang)", None

    safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", case_id or "answer")
    source_path = work_dir / f"{safe_id}.c"
    exe_path = work_dir / safe_id
    source_path.write_text(code, encoding="utf-8")

    try:
        result = subprocess.run(
            [compiler, "-std=c99", "-Wall", "-Wextra", "-o", str(exe_path), str(source_path), "-lm"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True, "Compiled successfully", exe_path
        error_msg = (result.stderr or result.stdout).strip()
        return False, f"Compilation failed: {error_msg[:500]}", None
    except subprocess.TimeoutExpired:
        return False, "Compilation timeout (10s)", None
    except Exception as e:
        return False, f"Compilation error: {str(e)[:200]}", None


def run_c_program(exe_path: Path, sample_input: str, timeout: int = 5) -> tuple[bool, str]:
    """Run compiled C program with input and return (success, output)."""
    try:
        result = subprocess.run(
            [str(exe_path)],
            input=sample_input if sample_input.endswith("\n") else sample_input + "\n",
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, f"Timeout after {timeout}s"
    except Exception as e:
        return False, f"Execution error: {str(e)[:100]}"


def check_output_keywords(output: str, case: dict[str, Any]) -> tuple[bool, list[str]]:
    """Check if output contains expected keywords."""
    checker = case.get("checker_rules", {})
    behavior = case.get("expected_behavior", {})
    keywords = []
    keywords.extend(checker.get("output_keywords", []))
    keywords.extend(behavior.get("output_contains", []))

    missing = []
    for keyword in keywords:
        if str(keyword).lower() not in output.lower():
            missing.append(str(keyword))

    return len(missing) == 0, missing


def check_structure(code: str, case: dict[str, Any]) -> tuple[bool, list[str]]:
    """Smoke-check that the answer looks like a complete C solution."""
    checker = case.get("checker_rules", {})
    required = checker.get("required_code_keywords")
    if required is None:
        required = checker.get("keywords", ["#include", "main", "scanf", "printf"])

    missing = []
    lower_code = code.lower()
    for keyword in required:
        if str(keyword).lower() not in lower_code:
            missing.append(str(keyword))

    return len(missing) == 0, missing


def check_expected_behavior(output: str, case: dict[str, Any]) -> tuple[bool, str]:
    """Check lightweight numeric/output behavior."""
    behavior = case.get("expected_behavior", {})

    min_val = behavior.get("min_value")
    max_val = behavior.get("max_value")
    if min_val is not None or max_val is not None:
        numbers = re.findall(r"-?\d+\.?\d*", output)
        if numbers:
            try:
                val = float(numbers[-1])  # Use last number found
                if min_val is not None and val < min_val:
                    return False, f"Value {val} < minimum {min_val}"
                if max_val is not None and val > max_val:
                    return False, f"Value {val} > maximum {max_val}"
            except ValueError:
                pass
    
    return True, "Expected behavior smoke check passed"


def run_smoke_tests(code: str, case: dict[str, Any]) -> dict[str, Any]:
    """Run smoke tests on code: compile, run, check output."""
    checker_rules = case.get("checker_rules", {})
    timeout = checker_rules.get("timeout_seconds", 5)
    sample_input = case.get("sample_input", "")
    
    results = {
        "case_id": case.get("id", "unknown"),
        "compile_pass": False,
        "run_pass": False,
        "keyword_pass": False,
        "structure_pass": False,
        "score": 0.0,
        "messages": [],
    }
    
    structure_pass, missing_structure = check_structure(code, case)
    results["structure_pass"] = structure_pass
    if missing_structure:
        results["messages"].append(f"Missing code structure keywords: {missing_structure}")
    else:
        results["messages"].append("Code structure keywords found")

    if checker_rules.get("compile_required", True):
        with tempfile.TemporaryDirectory(prefix="c_exam_eval_") as tmp:
            success, msg, exe_path = compile_c_code(code, Path(tmp), case.get("id", ""))
            results["compile_pass"] = success
            results["messages"].append(f"Compile: {msg}")
            if not success:
                results["score"] = 0.0
                return results

            if checker_rules.get("runtime_required", True) and exe_path is not None:
                success, output = run_c_program(exe_path, sample_input, timeout)
                results["run_pass"] = success
                results["output"] = output[:1000]
                results["messages"].append(f"Runtime: {'OK' if success else output[:200]}")

                if success:
                    kw_pass, missing = check_output_keywords(output, case)
                    results["keyword_pass"] = kw_pass
                    if missing:
                        results["messages"].append(f"Missing output keywords: {missing}")
                    else:
                        results["messages"].append("Output keywords found")

                    behavior_pass, behavior_msg = check_expected_behavior(output, case)
                    results["behavior_pass"] = behavior_pass
                    results["messages"].append(f"Behavior: {behavior_msg}")
    else:
        results["compile_pass"] = True

    max_points = case_points(case)
    if results["compile_pass"] and results["run_pass"]:
        if results["keyword_pass"] and results["structure_pass"]:
            score_pct = 1.0
        elif results["keyword_pass"] or results["structure_pass"]:
            score_pct = 0.7
        else:
            score_pct = 0.5
    else:
        score_pct = 0.0 if not results["compile_pass"] else 0.25

    results["score"] = round(max_points * score_pct, 1)

    return results


def build_model_prompt(case: dict[str, Any]) -> str:
    features = "\n".join(f"- {feature}" for feature in case.get("required_features", []))
    sample_input = case.get("sample_input", "")
    expected = json.dumps(case.get("expected_behavior", {}), ensure_ascii=False)
    return (
        "Write a complete, single-file C99 program for this exam problem.\n"
        "Return ONLY one fenced C code block in this exact format:\n"
        "```c\n"
        "<full compilable C program>\n"
        "```\n"
        "Do not include explanations before or after the block.\n\n"
        f"Problem:\n{case.get('prompt', '')}\n\n"
        f"Required features:\n{features}\n\n"
        f"Sample stdin:\n{sample_input}\n\n"
        f"Expected behavior smoke hints:\n{expected}\n"
    )


def build_repair_prompt(previous_output: str) -> str:
    return (
        "Your previous answer did not contain a valid ```c code block.\n"
        "Please rewrite ONLY the C program in a single ```c block.\n"
        "Do not include explanation.\n\n"
        "Previous answer:\n"
        f"{previous_output[:4000]}\n"
    )


def call_local_ai(run_script: Path, prompt: str, timeout: int = AI_TIMEOUT_SECONDS) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault("CLAW_PROMPT_PROFILE", "c_programming")
    return subprocess.run(
        ["bash", str(run_script), "--output-format", "text", "prompt", prompt],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def generate_ai_response(case: dict[str, Any]) -> str:
    """Generate C code from AI for the given case (requires local_ai/run.sh)."""
    prompt = case.get("prompt", "")
    if not prompt:
        return ""
    
    try:
        run_script = local_ai_run_script()
        
        if not run_script.exists():
            print(f"Warning: local_ai/run.sh not found at {run_script}", file=sys.stderr)
            return ""
        
        full_prompt = build_model_prompt(case)

        result = call_local_ai(run_script, full_prompt)
        combined = "\n".join(part for part in (result.stdout, result.stderr) if part)
        if result.returncode == 0 and extract_c_code(combined, debug=False):
            return combined

        extracted = extract_c_code(combined)
        if extracted:
            print(
                f"Warning: local AI returned non-zero for {case.get('id')}, but C code was found; continuing.",
                file=sys.stderr,
            )
            return extracted

        repair_result = call_local_ai(run_script, build_repair_prompt(combined))
        repaired = "\n".join(part for part in (repair_result.stdout, repair_result.stderr) if part)
        if extract_c_code(repaired, debug=False):
            return repaired

        details = combined.strip()
        print(f"Warning: AI generation failed for {case.get('id')}: {details[:300]}", file=sys.stderr)
        return ""
    except subprocess.TimeoutExpired:
        print(f"Warning: AI generation timeout for {case.get('id')}", file=sys.stderr)
        return ""
    except Exception as e:
        print(f"Warning: error generating code: {e}", file=sys.stderr)
        return ""


def run_evaluation(
    eval_dir: Path | None = None,
    use_ai: bool = False,
    case_filter: str | None = None,
    output_file: Path | None = None,
    answers_dir: Path | None = None,
) -> dict[str, Any]:
    """Run full evaluation suite."""
    eval_dir = eval_dir or default_eval_dir()
    cases = load_eval_cases(eval_dir)
    
    if case_filter:
        needle = case_filter.lower()
        cases = [
            c for c in cases
            if needle in c.get("id", "").lower()
            or needle in c.get("topic", "").lower()
            or needle in str(c.get("year", "")).lower()
            or needle in c.get("_filename", "").lower()
        ]
    
    if not cases:
        print("No eval cases found", file=sys.stderr)
        return {"error": "No cases found"}
    
    total_points = sum(case_points(case) for case in cases)

    report = {
        "timestamp": int(time.time()),
        "total_cases": len(cases),
        "cases_tested": 0,
        "total_points": display_points(total_points),
        "total_earned": 0,
        "results": [],
    }
    
    for case in cases:
        case_id = case.get("id", "unknown")
        print(f"Evaluating {case_id}...", end=" ", flush=True)
        
        points = case_points(case)

        if use_ai:
            code = generate_ai_response(case)
        elif answers_dir:
            answer_path = answers_dir / f"{case_id}.c"
            code = answer_path.read_text(encoding="utf-8") if answer_path.exists() else ""
        else:
            code = case.get("reference_answer", "")

        def no_code_result(message: str) -> dict[str, Any]:
            return {
                "case_id": case_id,
                "compile_pass": False,
                "run_pass": False,
                "keyword_pass": False,
                "structure_pass": False,
                "score": 0.0,
                "messages": [message],
                "case_info": {
                    "year": case.get("year"),
                    "exam": case.get("exam"),
                    "topic": case.get("topic"),
                    "points": display_points(points),
                },
            }

        if not code:
            print("no answer")
            results = no_code_result("No answer code supplied. Use --use-ai or --answers-dir.")
            report["results"].append(results)
            report["cases_tested"] += 1
            continue
        
        code = extract_c_code(code)
        if not code:
            print("no code")
            results = no_code_result("No valid C code could be extracted from the model output.")
            report["results"].append(results)
            report["cases_tested"] += 1
            continue

        results = run_smoke_tests(code, case)
        
        # Print result summary
        status = "✅" if results["compile_pass"] else "❌"
        print(f"{status} score={results['score']}/{display_points(points)}")
        
        results["case_info"] = {
            "year": case.get("year"),
            "exam": case.get("exam"),
            "topic": case.get("topic"),
            "points": display_points(points),
        }
        
        report["results"].append(results)
        report["cases_tested"] += 1
        report["total_earned"] += results["score"]
    
    # Calculate summary
    if total_points > 0:
        report["pass_rate"] = round(100 * report["total_earned"] / total_points, 1)
    else:
        report["pass_rate"] = 0.0
    
    # Save report
    if output_file is None:
        output_file = Path(eval_dir).parent / "eval_report.json"
    
    output_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n📊 Report saved to {output_file}")
    print(f"Summary: {display_points(float(report['total_earned']))}/{report['total_points']} points ({report['pass_rate']}%)")
    
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="C Exam Offline Evaluation Runner")
    parser.add_argument(
        "--eval-dir",
        type=Path,
        default=None,
        help="Path to eval cases directory (default: local_ai/eval_cases/c_exam)",
    )
    parser.add_argument(
        "--use-ai",
        action="store_true",
        help="Generate code using local AI (requires local_ai/run.sh)",
    )
    parser.add_argument(
        "--filter",
        default=None,
        help="Filter cases by ID substring (e.g., '2021', 'series')",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output report file (default: eval_report.json)",
    )
    parser.add_argument(
        "--answers-dir",
        type=Path,
        default=None,
        help="Optional directory containing <case_id>.c answers for offline smoke tests",
    )
    args = parser.parse_args()
    
    run_evaluation(
        eval_dir=args.eval_dir,
        use_ai=args.use_ai,
        case_filter=args.filter,
        output_file=args.output,
        answers_dir=args.answers_dir,
    )


if __name__ == "__main__":
    main()
