#!/usr/bin/env python3
"""
local_ai/proxy.py
─────────────────
Anthropic API ↔ Ollama (OpenAI-compat) 格式轉換代理。
純 Python 標準庫，無需安裝任何套件。

claw 以 Anthropic 格式呼叫 → 本代理轉換 → Ollama 本地模型回應
→ 轉回 Anthropic 格式 → claw 收到回應

用法（通常由 run.sh 呼叫）：
    python3 local_ai/proxy.py --model qwen2.5-coder:14b --port 8082 --ollama-url http://localhost:11434
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from prompt_loader import load_prompt_profile
    from checkers.check_c_answer import check_c_answer
    from repair_loop import append_checker_warnings, build_repair_prompt
    from rag.search_docs import format_context, search as search_rag
except ImportError:  # pragma: no cover - package import path used by tests
    from local_ai.prompt_loader import load_prompt_profile
    from local_ai.checkers.check_c_answer import check_c_answer
    from local_ai.repair_loop import append_checker_warnings, build_repair_prompt
    from local_ai.rag.search_docs import format_context, search as search_rag


# ── 設定 ──────────────────────────────────────────────────────────────────────

DEFAULT_PORT = 8082
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5-coder:14b"
DEFAULT_SYSTEM_PROMPT = (
    "你是離線終端機助理。"
    "請全程只使用繁體中文回答，不要混用英文、日文、韓文、越南文或其他語言。"
    "不要自己切換語言，也不要詢問是否要改用別的語言。"
    "請直接在對話中輸出答案，不要主動建立、修改或輸出成檔案，除非使用者明確要求你這樣做。"
    "如果使用者要求寫程式，請直接給正確答案。"
    "如果使用者沒有明確指定程式語言，預設輸出 C 語言程式。"
    "如果使用者已經指定 Python、Java、C++ 或其他語言，就照使用者指定的語言回答。"
    "如果題目很簡單，例如要求輸出 1，請直接提供最短、正確的 C 程式。"
    "不要離題，不要自我對話，不要補無關說明。"
    "如果使用者沒有特別指定格式，請優先用清楚、直接、適合終端機閱讀的方式回覆。"
)

PROGRAMMING_KEYWORDS = (
    "write a program",
    "write a c program",
    "program",
    "code",
    "coding",
    "function",
    "array",
    "matrix",
    "sort",
    "struct",
    "read n",
    "generate",
    "c語言",
    "程式",
    "寫一個程式",
    "寫程式",
    "函式",
    "陣列",
    "排序",
    "讀檔",
    "輸出",
)

LANGUAGE_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("c", ("c語言", " c language", " in c", "write a c program", "language c")),
    ("c++", ("c++", "cpp", "c plus plus")),
    ("python", ("python", "py ")),
    ("java", ("java",)),
    ("javascript", ("javascript", "js ")),
    ("go", ("golang", "go language", " in go")),
    ("rust", ("rust",)),
)

MAX_C_REPAIR_ATTEMPTS = 2
C_FORBIDDEN_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bstd::", "包含 C++ 命名空間 std::"),
    (r"\bcout\s*<<", "使用了 C++ 的 cout"),
    (r"\bcin\s*>>", "使用了 C++ 的 cin"),
    (r"\bclass\b", "使用了 C++ 的 class"),
    (r"\btemplate\s*<", "使用了 C++ 的 template"),
    (r"\bnamespace\b", "使用了 C++ 的 namespace"),
    (r"\bauto\b", "使用了 C++ 的 auto"),
    (r"\bvector\s*<", "使用了 C++ 的 vector"),
    (r"\bstring\b", "使用了 C++ string 型別"),
    (r"\.\.\.", "出現了 ...，疑似 C++ fold expression 或其他不合法內容"),
)
FUNCTION_DEF_PATTERN = re.compile(
    r"^\s*(?:static\s+)?(?:unsigned\s+|signed\s+|long\s+|short\s+)*"
    r"(?:void|int|double|float|char|size_t|bool|struct\s+\w+)\s+"
    r"(?P<name>[A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{",
    re.MULTILINE,
)
FUNCTION_PROTO_PATTERN = re.compile(
    r"^\s*(?:static\s+)?(?:unsigned\s+|signed\s+|long\s+|short\s+)*"
    r"(?:void|int|double|float|char|size_t|bool|struct\s+\w+)\s+"
    r"(?P<name>[A-Za-z_]\w*)\s*\([^;{}]*\)\s*;",
    re.MULTILINE,
)
CALL_PATTERN = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
CONTROL_KEYWORDS = {
    "if", "for", "while", "switch", "return", "sizeof",
}
KNOWN_LIBRARY_CALLS = {
    "printf", "scanf", "fprintf", "fscanf", "snprintf", "puts", "gets",
    "malloc", "calloc", "realloc", "free", "exit", "pow", "sqrt", "fabs",
    "strlen", "strcpy", "strcmp", "fopen", "fclose", "fgets", "fputs",
}


def _looks_like_series_math_program(user_text: str) -> bool:
    lowered = user_text.lower()
    series_markers = (
        "1/1!",
        "2^2",
        "n^2",
        "factorial",
        "階乘",
        "級數",
        "series",
    )
    return any(marker in lowered for marker in series_markers)


def _check_series_math_c_code(user_text: str, text: str) -> tuple[bool, str]:
    if not _looks_like_series_math_program(user_text):
        return True, ""

    code = _extract_code_block(text, "c")
    normalized = re.sub(r"\s+", " ", code)

    has_factorial = (
        "factorial(" in code
        or re.search(r"\b(?:fact|fac)\b", code)
        or re.search(r"\bproduct\b", code)
    )
    if not has_factorial:
        return False, "這題是階乘級數，但程式中看不到 factorial 或等價的階乘計算"

    has_square_sum = (
        re.search(r"\+=\s*[A-Za-z_]\w*\s*\*\s*[A-Za-z_]\w*", code)
        or "pow(" in code
    )
    if not has_square_sum:
        return False, "這題需要累加平方和，但程式中看不到 1^2 + 2^2 + ... 的累加邏輯"

    has_alternating = bool(
        re.search(r"\(-?1\)\s*\^\s*", normalized)
        or re.search(r"%\s*2", normalized)
        or re.search(r"&\s*1", normalized)
        or re.search(r"if\s*\([^)]*%[^)]*2", normalized)
    )
    has_plus_equal = "+=" in code
    has_minus_equal = "-=" in code
    if not (has_alternating or (has_plus_equal and has_minus_equal)):
        return False, "這題是交錯級數，但程式中看不到正負號交替的邏輯"

    if not re.search(r"\bfor\s*\(", code):
        return False, "這題通常需要迴圈逐項累加，但程式中看不到 for 迴圈"

    return True, ""


def _looks_like_score_distribution_program(user_text: str) -> bool:
    lowered = user_text.lower()
    markers = (
        "score distribution",
        "class average",
        "scores between 0 and 100",
        "show the score distribution",
        "average",
        "scores:",
        "學生",
        "成績",
        "分布",
        "平均",
    )
    return any(marker in lowered for marker in markers)


def _check_score_distribution_c_code(user_text: str, text: str) -> tuple[bool, str]:
    if not _looks_like_score_distribution_program(user_text):
        return True, ""

    code = _extract_code_block(text, "c")
    lowered = code.lower()

    if "hello, world" in lowered:
        return False, "這題要求讀取成績並統計分布，不能輸出 Hello, World!"

    if "scanf" not in code:
        return False, "這題需要讀入 n 和成績，程式中看不到 scanf"

    if "printf" not in code:
        return False, "這題需要印出分布與平均，程式中看不到 printf"

    if not re.search(r"\bfor\s*\(", code):
        return False, "這題需要用迴圈讀入與統計，程式中看不到 for 迴圈"

    has_average = (
        "average" in lowered
        or re.search(r"\bsum\b", lowered)
        or re.search(r"/\s*n\b", lowered)
    )
    if not has_average:
        return False, "這題需要計算平均，程式中看不到 sum/average 或除以 n 的邏輯"

    has_distribution = (
        re.search(r"/\s*10", code)
        or re.search(r"\bcount\s*\[", lowered)
        or re.search(r"\bbucket", lowered)
        or re.search(r"\bhist", lowered)
        or "100" in code
    )
    if not has_distribution:
        return False, "這題需要依分數區間統計分布，程式中看不到分桶或區間計數邏輯"

    return True, ""


# ── Anthropic → OpenAI 格式轉換 ───────────────────────────────────────────────

def _flatten_message_content(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type", "")
            if btype == "text":
                parts.append(str(block.get("text", "")))
            elif btype == "tool_result":
                inner = block.get("content", [])
                if isinstance(inner, str):
                    parts.append(inner)
                elif isinstance(inner, list):
                    for inner_block in inner:
                        if isinstance(inner_block, dict) and inner_block.get("type") == "text":
                            parts.append(str(inner_block.get("text", "")))
        return "\n".join(parts)
    return ""


def _latest_user_text(body: dict) -> str:
    for msg in reversed(body.get("messages", [])):
        if msg.get("role") == "user":
            return _flatten_message_content(msg.get("content", ""))
    return ""


def _looks_like_programming_request(text: str) -> bool:
    lowered = f" {text.lower()} "
    if any(keyword in lowered for keyword in PROGRAMMING_KEYWORDS):
        return True
    return bool(re.search(r"\b(int|double|float|printf|scanf|main|struct|typedef)\b", lowered))


def _detect_explicit_language(text: str) -> str | None:
    lowered = f" {text.lower()} "
    for language, patterns in LANGUAGE_PATTERNS:
        if any(pattern in lowered for pattern in patterns):
            return language
    return None


def _programming_mode_instruction(user_text: str) -> str | None:
    if not _looks_like_programming_request(user_text):
        return None
    explicit_language = _detect_explicit_language(user_text)
    if explicit_language in (None, "c"):
        return (
            "這是一題程式設計題。"
            "請直接輸出一份完整、可編譯、可執行的 C 語言程式。"
            "除非使用者明確要求說明，否則只輸出一個 ```c 程式碼區塊，不要加前言、結語、道歉或多餘解釋。"
            "不要輸出偽代碼，不要輸出錯誤或未完成的程式。"
        )
    return (
        f"這是一題程式設計題。使用者已指定 {explicit_language}。"
        f"請直接輸出一份完整、可執行的 {explicit_language} 程式。"
        "除非使用者明確要求說明，否則只輸出一個程式碼區塊，不要加前言、結語或多餘解釋。"
    )


def _rag_context_instruction(user_text: str) -> str | None:
    enabled = os.environ.get("CLAW_RAG_ENABLED", "").strip().lower()
    if enabled not in ("1", "true", "yes", "on"):
        return None
    try:
        top_k = int(os.environ.get("CLAW_RAG_TOP_K", "5"))
    except ValueError:
        top_k = 5
    results = search_rag(user_text, top_k=top_k)
    context = format_context(results)
    if not context:
        return None
    return (
        "以下是離線本地 RAG 文件檢索結果。請優先根據這些片段回答；"
        "若片段不足，請明確說明限制，不要聲稱已上網查詢。\n\n"
        f"{context}"
    )


def _detect_programming_language(user_text: str) -> str | None:
    if not _looks_like_programming_request(user_text):
        return None
    explicit_language = _detect_explicit_language(user_text)
    if explicit_language is None:
        return "c"
    return explicit_language


def _extract_code_block(text: str, language: str | None = None) -> str:
    pattern = r"```(?P<lang>[^\n`]*)\n(?P<code>.*?)```"
    matches = list(re.finditer(pattern, text, re.DOTALL))
    if not matches:
        return text.strip()

    if language:
        for match in matches:
            fenced_lang = match.group("lang").strip().lower()
            if fenced_lang == language.lower():
                return match.group("code").strip()
    return matches[0].group("code").strip()


def _find_c_compiler() -> str | None:
    for candidate in ("cc", "gcc", "clang"):
        compiler = shutil.which(candidate)
        if compiler:
            return compiler
    return None


def _static_check_c_code(text: str) -> tuple[bool, str]:
    code = _extract_code_block(text, "c")
    for pattern, message in C_FORBIDDEN_PATTERNS:
        if re.search(pattern, code):
            return False, message

    if not re.search(r"\bmain\s*\(", code):
        return False, "缺少 main 函式"

    defined_functions = {match.group("name") for match in FUNCTION_DEF_PATTERN.finditer(code)}
    declared_functions = {match.group("name") for match in FUNCTION_PROTO_PATTERN.finditer(code)}

    calls = set()
    for match in CALL_PATTERN.finditer(code):
        name = match.group(1)
        if name in CONTROL_KEYWORDS:
            continue
        calls.add(name)

    unresolved_calls = sorted(
        name for name in calls
        if name not in defined_functions
        and name not in declared_functions
        and name not in KNOWN_LIBRARY_CALLS
    )
    if unresolved_calls:
        return False, f"可能有未宣告或未定義的函式：{', '.join(unresolved_calls[:6])}"

    return True, ""


def _compile_check_c_code(user_text: str, text: str) -> tuple[bool, str]:
    static_ok, static_error = _static_check_c_code(text)
    if not static_ok:
        return False, static_error

    code = _extract_code_block(text, "c")
    if _looks_like_programming_request(user_text) and "hello, world" in code.lower():
        return False, "這是作業題，不可以只回 Hello, World!"

    semantic_ok, semantic_error = _check_series_math_c_code(user_text, text)
    if not semantic_ok:
        return False, semantic_error

    score_ok, score_error = _check_score_distribution_c_code(user_text, text)
    if not score_ok:
        return False, score_error

    compiler = _find_c_compiler()
    if compiler is None:
        return True, "no local C compiler found; skipped syntax check"

    code = _extract_code_block(text, "c")
    with tempfile.NamedTemporaryFile("w", suffix=".c", delete=False, encoding="utf-8") as handle:
        handle.write(code)
        path = handle.name

    try:
        result = subprocess.run(
            [compiler, "-std=c11", "-fsyntax-only", path],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except Exception as exc:
        return False, f"compile check failed to run: {exc}"
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

    if result.returncode == 0:
        return True, ""
    return False, (result.stderr or result.stdout).strip()


def _ollama_api_chat_payload(oai_payload: dict) -> dict:
    payload = {
        "model": oai_payload["model"],
        "messages": oai_payload.get("messages", []),
        "stream": False,
        "options": {},
    }
    if "temperature" in oai_payload:
        payload["options"]["temperature"] = oai_payload["temperature"]
    if "max_tokens" in oai_payload:
        payload["options"]["num_predict"] = oai_payload["max_tokens"]
    if not payload["options"]:
        payload.pop("options")
    return payload


def _ollama_api_chat_to_openai_response(ollama_data: dict, model: str) -> dict:
    content_text = ollama_data.get("message", {}).get("content", "")
    done_reason = ollama_data.get("done_reason", "stop")
    prompt_eval_count = ollama_data.get("prompt_eval_count", 0)
    eval_count = ollama_data.get("eval_count", 0)
    return {
        "id": "chatcmpl_" + uuid.uuid4().hex[:24],
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": content_text},
            "finish_reason": done_reason,
        }],
        "usage": {
            "prompt_tokens": prompt_eval_count,
            "completion_tokens": eval_count,
            "total_tokens": prompt_eval_count + eval_count,
        },
    }


def _request_ollama_completion(oai_payload: dict, ollama_url: str) -> dict:
    non_streaming_payload = dict(oai_payload)
    non_streaming_payload["stream"] = False
    openai_req = Request(
        f"{ollama_url}/v1/chat/completions",
        data=json.dumps(non_streaming_payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer ollama",
        },
        method="POST",
    )
    try:
        with urlopen(openai_req, timeout=120) as resp:
            return json.loads(resp.read())
    except HTTPError as exc:
        if exc.code != 404:
            raise

    api_payload = _ollama_api_chat_payload(non_streaming_payload)
    api_req = Request(
        f"{ollama_url}/api/chat",
        data=json.dumps(api_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(api_req, timeout=120) as resp:
        ollama_data = json.loads(resp.read())
    return _ollama_api_chat_to_openai_response(ollama_data, oai_payload["model"])


def _open_ollama_stream(oai_payload: dict, ollama_url: str):
    """開啟一個對 Ollama /v1/chat/completions 的串流連線，回傳檔案物件。"""
    streaming_payload = dict(oai_payload)
    streaming_payload["stream"] = True
    req = Request(
        f"{ollama_url}/v1/chat/completions",
        data=json.dumps(streaming_payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer ollama",
            "Accept": "text/event-stream",
        },
        method="POST",
    )
    return urlopen(req, timeout=120)


def _repair_c_response(
    user_text: str,
    oai_payload: dict,
    initial_response: dict,
    ollama_url: str,
) -> dict:
    current_response = initial_response
    max_attempts = int(os.environ.get("CLAW_MAX_REPAIR_RETRIES", str(MAX_C_REPAIR_ATTEMPTS)))
    best_response = current_response
    best_check = {"ok": False, "score": -1.0, "issues": [], "suggestions": []}
    for _ in range(max_attempts + 1):
        content_text = current_response.get("choices", [{}])[0].get("message", {}).get("content", "")
        check = check_c_answer(content_text, user_text)
        if check.get("score", 0) >= best_check.get("score", 0):
            best_response = current_response
            best_check = check
        if check.get("ok"):
            return current_response
        if _ >= max_attempts:
            break

        repair_messages = list(oai_payload.get("messages", []))
        repair_messages.append({"role": "assistant", "content": content_text})
        repair_messages.append({
            "role": "user",
            "content": build_repair_prompt(user_text, content_text, check),
        })
        repair_payload = dict(oai_payload)
        repair_payload["messages"] = repair_messages
        repair_payload["stream"] = False
        repair_payload["temperature"] = 0.0
        current_response = _request_ollama_completion(repair_payload, ollama_url)

    content_text = best_response.get("choices", [{}])[0].get("message", {}).get("content", "")
    best_response = dict(best_response)
    best_response["choices"] = list(best_response.get("choices", []))
    if best_response["choices"]:
        choice = dict(best_response["choices"][0])
        message = dict(choice.get("message", {}))
        message["content"] = append_checker_warnings(content_text, best_check)
        choice["message"] = message
        best_response["choices"][0] = choice
    return best_response


def anthropic_to_openai(body: dict, model: str, default_system_prompt: str | None = None) -> dict:
    """將 Anthropic /v1/messages 請求轉換為 OpenAI /v1/chat/completions 格式。"""
    messages: list[dict] = []

    # system prompt
    system = body.get("system")
    system_parts: list[str] = []
    if system:
        if isinstance(system, list):
            text = " ".join(b.get("text", "") for b in system if isinstance(b, dict))
        else:
            text = str(system)
        if text.strip():
            system_parts.append(text.strip())
    if default_system_prompt and default_system_prompt.strip():
        system_parts.append(default_system_prompt.strip())
    programming_instruction = _programming_mode_instruction(_latest_user_text(body))
    if programming_instruction:
        system_parts.append(programming_instruction)
    rag_instruction = _rag_context_instruction(_latest_user_text(body))
    if rag_instruction:
        system_parts.append(rag_instruction)
    if system_parts:
        messages.append({"role": "system", "content": "\n\n".join(system_parts)})

    # 歷史訊息
    for msg in body.get("messages", []):
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if isinstance(content, str):
            messages.append({"role": role, "content": content})
        elif isinstance(content, list):
            # 把所有 text 塊合併；tool_result/tool_use 簡化為文字
            parts: list[str] = []
            for block in content:
                btype = block.get("type", "")
                if btype == "text":
                    parts.append(block.get("text", ""))
                elif btype == "tool_result":
                    inner = block.get("content", [])
                    if isinstance(inner, list):
                        for ib in inner:
                            if ib.get("type") == "text":
                                parts.append(f"[Tool result] {ib.get('text','')}")
                    elif isinstance(inner, str):
                        parts.append(f"[Tool result] {inner}")
                elif btype == "tool_use":
                    inp = json.dumps(block.get("input", {}))
                    parts.append(f"[Tool call: {block.get('name','')}({inp})]")
            messages.append({"role": role, "content": "\n".join(parts)})

    payload: dict = {
        "model": model,
        "messages": messages,
        "stream": body.get("stream", False),
    }
    if "max_tokens" in body:
        payload["max_tokens"] = body["max_tokens"]
    if "temperature" in body:
        payload["temperature"] = body["temperature"]
    else:
        payload["temperature"] = 0.1

    return payload


# ── OpenAI → Anthropic 格式轉換（非串流）────────────────────────────────────

def openai_to_anthropic(oai: dict, model: str) -> dict:
    """將 OpenAI chat.completion 回應轉換為 Anthropic Messages 格式。"""
    msg_id = "msg_" + uuid.uuid4().hex[:24]
    choice = oai.get("choices", [{}])[0]
    content_text = choice.get("message", {}).get("content", "")
    finish = choice.get("finish_reason", "stop")
    stop_reason = "end_turn" if finish in ("stop", None) else finish

    usage = oai.get("usage", {})
    return {
        "id": msg_id,
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": content_text}],
        "model": model,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        },
    }


# ── SSE 串流轉換 ──────────────────────────────────────────────────────────────

def stream_openai_to_anthropic(ollama_response, model: str):
    """
    把 Ollama 的 OpenAI-compat SSE 串流轉換為 Anthropic SSE 串流。
    每次 yield 一行已編碼的 bytes。
    """
    msg_id = "msg_" + uuid.uuid4().hex[:24]

    def sse_line(event: str, data: dict) -> bytes:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode()

    # message_start
    yield sse_line("message_start", {
        "type": "message_start",
        "message": {
            "id": msg_id, "type": "message", "role": "assistant",
            "content": [], "model": model,
            "stop_reason": None, "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 0},
        }
    })
    # content_block_start
    yield sse_line("content_block_start", {
        "type": "content_block_start",
        "index": 0,
        "content_block": {"type": "text", "text": ""},
    })
    yield b"event: ping\ndata: {\"type\":\"ping\"}\n\n"

    output_tokens = 0
    finish_reason = "end_turn"

    for raw_line in ollama_response:
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line or not line.startswith("data: "):
            continue
        payload_str = line[6:]
        if payload_str == "[DONE]":
            break
        try:
            chunk = json.loads(payload_str)
        except json.JSONDecodeError:
            continue

        choices = chunk.get("choices", [])
        if not choices:
            continue
        delta = choices[0].get("delta", {})
        text_delta = delta.get("content", "")
        fr = choices[0].get("finish_reason")
        if fr:
            finish_reason = "end_turn" if fr in ("stop", None) else fr

        if text_delta:
            output_tokens += 1
            yield sse_line("content_block_delta", {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": text_delta},
            })

    # content_block_stop
    yield sse_line("content_block_stop", {"type": "content_block_stop", "index": 0})
    # message_delta
    yield sse_line("message_delta", {
        "type": "message_delta",
        "delta": {"stop_reason": finish_reason, "stop_sequence": None},
        "usage": {"output_tokens": output_tokens},
    })
    # message_stop
    yield sse_line("message_stop", {"type": "message_stop"})


def _mid_stream_error_trailer(error_text: str = "上游連線中斷") -> bytes:
    """串流開始後如果上游中斷，用這段 SSE 事件把客戶端收尾到乾淨狀態。

    客戶端不需要這個 trailer 就能解析完畢，但少了它會出現 stop_reason 永遠為 None
    的鬼魂 message；補上 message_delta + message_stop 可讓客戶端穩定重設狀態。
    """
    delta = {
        "type": "message_delta",
        "delta": {"stop_reason": "error", "stop_sequence": None},
        "usage": {"output_tokens": 0},
    }
    error_block = {
        "type": "content_block_delta",
        "index": 0,
        "delta": {"type": "text_delta", "text": f"\n[proxy] {error_text}"},
    }
    pieces = [
        f"event: content_block_delta\ndata: {json.dumps(error_block, ensure_ascii=False)}\n\n",
        "event: content_block_stop\ndata: {\"type\":\"content_block_stop\",\"index\":0}\n\n",
        f"event: message_delta\ndata: {json.dumps(delta, ensure_ascii=False)}\n\n",
        "event: message_stop\ndata: {\"type\":\"message_stop\"}\n\n",
    ]
    return "".join(pieces).encode("utf-8")


def text_to_anthropic_sse(text: str, model: str):
    msg_id = "msg_" + uuid.uuid4().hex[:24]

    def sse_line(event: str, data: dict) -> bytes:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode()

    yield sse_line("message_start", {
        "type": "message_start",
        "message": {
            "id": msg_id,
            "type": "message",
            "role": "assistant",
            "content": [],
            "model": model,
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 0},
        },
    })
    yield sse_line("content_block_start", {
        "type": "content_block_start",
        "index": 0,
        "content_block": {"type": "text", "text": ""},
    })
    if text:
        yield sse_line("content_block_delta", {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": text},
        })
    yield sse_line("content_block_stop", {"type": "content_block_stop", "index": 0})
    yield sse_line("message_delta", {
        "type": "message_delta",
        "delta": {"stop_reason": "end_turn", "stop_sequence": None},
        "usage": {"output_tokens": max(1, len(text.split())) if text else 0},
    })
    yield sse_line("message_stop", {"type": "message_stop"})


# ── HTTP 請求處理器 ───────────────────────────────────────────────────────────

class ProxyHandler(BaseHTTPRequestHandler):
    """處理所有 HTTP 請求的代理。"""

    ollama_url: str = DEFAULT_OLLAMA_URL
    local_model: str = DEFAULT_MODEL
    ollama_model: str = DEFAULT_MODEL
    default_system_prompt: str = DEFAULT_SYSTEM_PROMPT

    def log_message(self, fmt: str, *args) -> None:  # 簡化日誌
        sys.stderr.write(f"[proxy] {fmt % args}\n")

    def _send_json_error(self, code: int, message: str) -> None:
        body = json.dumps(
            {"error": message}, ensure_ascii=False
        ).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        """健康檢查端點。"""
        if self.path in ("/health", "/"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "model": self.local_model}).encode())
        else:
            self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            self._send_json_error(400, "請求內容不是合法的 JSON")
            return

        if self.path in ("/v1/messages",):
            self._handle_messages(body)
        else:
            self._send_json_error(404, f"未知的端點：{self.path}")

    def _handle_messages(self, body: dict) -> None:
        streaming = body.get("stream", False)
        latest_user_text = _latest_user_text(body)
        oai_payload = anthropic_to_openai(body, self.ollama_model, self.default_system_prompt)
        requested_language = _detect_programming_language(latest_user_text)
        needs_c_repair = requested_language == "c"

        try:
            if streaming:
                self._stream_response(
                    body.get("model", self.local_model),
                    oai_payload,
                    needs_c_repair,
                    latest_user_text,
                )
            else:
                self._sync_response(
                    body.get("model", self.local_model),
                    oai_payload,
                    needs_c_repair,
                    latest_user_text,
                )
        except URLError as exc:
            sys.stderr.write(f"[proxy] Ollama 連線失敗：{exc}\n")
            self._send_json_error(502, "無法連線到 Ollama，請先執行 ollama serve")
        except HTTPError as exc:
            sys.stderr.write(f"[proxy] Ollama HTTP 錯誤：{exc}\n")
            self._send_json_error(
                502, f"Ollama 回應 HTTP {exc.code}：{exc.reason or '未知錯誤'}"
            )

    def _sync_response(
        self,
        model: str,
        oai_payload: dict,
        needs_c_repair: bool,
        user_text: str,
    ) -> None:
        oai_data = _request_ollama_completion(oai_payload, self.ollama_url)
        if needs_c_repair:
            oai_data = _repair_c_response(user_text, oai_payload, oai_data, self.ollama_url)
        result = openai_to_anthropic(oai_data, model)
        body_bytes = json.dumps(result).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def _send_sse_headers(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

    def _emit_prerendered_text_sse(self, content_text: str, model: str) -> None:
        """Headers 已送出後，把整段文字轉成 Anthropic SSE 並寫出。"""
        try:
            for chunk in text_to_anthropic_sse(content_text, model):
                self.wfile.write(chunk)
                self.wfile.flush()
        except BrokenPipeError:
            sys.stderr.write("[proxy] client disconnected during stream\n")

    def _stream_response(
        self,
        model: str,
        oai_payload: dict,
        needs_c_repair: bool,
        user_text: str,
    ) -> None:
        if needs_c_repair:
            # C 題會走本地檢查 + 重試路徑，需要完整文字才能檢驗。
            # 這條路徑的上游錯誤會直接 bubble 到 _handle_messages 的錯誤包裝器，
            # 因此 header 還沒送之前出錯，仍然可以送 JSON 錯誤。
            oai_data = _request_ollama_completion(oai_payload, self.ollama_url)
            oai_data = _repair_c_response(
                user_text, oai_payload, oai_data, self.ollama_url
            )
            content_text = (
                oai_data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            self._send_sse_headers()
            self._emit_prerendered_text_sse(content_text, model)
            return

        # 一般路徑：先嘗試打開上游串流，開啟失敗就 bubble 上去；
        # 只有真的拿到上游 stream 才送出 200 header，避免「送完 200 才發現
        # 上游掛掉，outer handler 只好再送一份 502」的協定衝突。
        try:
            upstream = _open_ollama_stream(oai_payload, self.ollama_url)
        except HTTPError as exc:
            if exc.code != 404:
                raise
            # 舊版 Ollama 沒有 /v1/chat/completions，退回非串流再模擬 SSE。
            oai_data = _request_ollama_completion(oai_payload, self.ollama_url)
            content_text = (
                oai_data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            self._send_sse_headers()
            self._emit_prerendered_text_sse(content_text, model)
            return

        # Upstream 就緒，承諾進入串流模式。
        self._send_sse_headers()
        try:
            with upstream:
                for chunk in stream_openai_to_anthropic(upstream, model):
                    self.wfile.write(chunk)
                    self.wfile.flush()
        except BrokenPipeError:
            sys.stderr.write("[proxy] client disconnected during stream\n")
        except (
            URLError,
            HTTPError,
            http.client.IncompleteRead,
            http.client.HTTPException,
            ConnectionError,
            OSError,
        ) as exc:
            # Header 已送，再送一份 502 只會打亂 SSE。用 trailer 告訴客戶端
            # 收工，並把錯誤寫到 stderr 給離線 log 追查。
            sys.stderr.write(f"[proxy] upstream interrupted mid-stream: {exc}\n")
            try:
                self.wfile.write(_mid_stream_error_trailer("上游連線中斷"))
                self.wfile.flush()
            except Exception:
                pass


# ── 主程式 ────────────────────────────────────────────────────────────────────

def wait_for_ollama(ollama_url: str, timeout: int = 30) -> bool:
    """等待 Ollama 服務啟動，回傳是否成功。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urlopen(f"{ollama_url}/api/tags", timeout=2):
                return True
        except Exception:
            time.sleep(1)
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Anthropic ↔ Ollama 代理")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama 模型名稱")
    parser.add_argument("--ollama-model", default=None, help="實際送給 Ollama 的模型名稱")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="代理監聽埠")
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL, help="Ollama 服務 URL")
    parser.add_argument(
        "--system-prompt",
        default=None,
        help="附加到每次請求的預設 system prompt",
    )
    parser.add_argument("--prompt-profile", default=None, help="local_ai/prompts 底下的 prompt profile")
    parser.add_argument("--prompt-dir", default=None, help="prompt profile 目錄")
    args = parser.parse_args()

    ProxyHandler.ollama_url = args.ollama_url
    ProxyHandler.local_model = args.model
    ProxyHandler.ollama_model = args.ollama_model or args.model
    ProxyHandler.default_system_prompt = load_prompt_profile(
        profile=args.prompt_profile,
        prompt_dir=args.prompt_dir,
        override_prompt=args.system_prompt,
    )

    sys.stderr.write(f"[proxy] 等待 Ollama 啟動（{args.ollama_url}）...\n")
    if not wait_for_ollama(args.ollama_url):
        sys.stderr.write("[proxy] 錯誤：無法連線到 Ollama，請先執行 ollama serve\n")
        sys.exit(1)

    server = HTTPServer(("127.0.0.1", args.port), ProxyHandler)
    sys.stderr.write(
        f"[proxy] 就緒 ─ 監聽 localhost:{args.port}  →  Ollama({args.model})\n"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        sys.stderr.write("\n[proxy] 關閉\n")


if __name__ == "__main__":
    main()
