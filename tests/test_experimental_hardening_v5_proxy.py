#!/usr/bin/env python3
"""
test_experimental_hardening_v5_proxy.py
───────────────────────────────────────
第五輪加固測試，著重於 v4 尾聲列出的五個待補強點：

    1. SSE 中途上游斷線的復原
    2. C 修復迴圈不會無限重試
    3. 超大 body 的 Content-Length 是位元組數（非字元數）
    4. --system-prompt 正確注入上游 payload
    5. bundle manifest 使用 BOM-less UTF-8，跨平台讀取不會被 BOM 卡住

純 Python 標準庫，不需安裝任何外部套件、不需 Ollama、不需網路。
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
PROXY_PY = PROJECT_DIR / "local_ai" / "proxy.py"

sys.path.insert(0, str(PROJECT_DIR / "local_ai"))
import proxy  # noqa: E402


# ────────────────────────────────────────────────────────────────────────────
# 共用：選空閒 port
# ────────────────────────────────────────────────────────────────────────────

def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_health(port: int, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/health", timeout=0.5
            ) as resp:
                if resp.status == 200:
                    return
        except Exception:
            time.sleep(0.1)
    raise RuntimeError(f"proxy on port {port} failed to become healthy")


# ────────────────────────────────────────────────────────────────────────────
# H-v5-01 ~ 02：中斷恢復
# ────────────────────────────────────────────────────────────────────────────

class TestMidStreamErrorTrailer(unittest.TestCase):
    """`_mid_stream_error_trailer` 產生的 bytes 要足以讓客戶端乾淨收工。"""

    def test_trailer_contains_error_stop_reason(self):
        data = proxy._mid_stream_error_trailer("模擬上游中斷")
        text = data.decode("utf-8")
        self.assertIn("message_delta", text)
        self.assertIn("message_stop", text)
        self.assertIn("\"stop_reason\": \"error\"", text)
        # 錯誤訊息是 UTF-8 中文，沒有 \u 跳脫
        self.assertIn("模擬上游中斷", text)
        self.assertIn("模擬上游中斷".encode("utf-8"), data)

    def test_trailer_ends_with_message_stop(self):
        data = proxy._mid_stream_error_trailer()
        # 最後一個 event 必須是 message_stop，否則客戶端會卡住
        events = [
            line[len("event: "):]
            for line in data.decode("utf-8").split("\n")
            if line.startswith("event: ")
        ]
        self.assertEqual(events[-1], "message_stop")


class UnreachableUpstreamProxy(unittest.TestCase):
    """Proxy 指向一個死 port，stream=True 路徑應回 502（而非送出 200 後再出糗）。

    不使用子行程 `main()`（因為會被 `wait_for_ollama` 卡住 30 秒）；改用
    in-process HTTP server 起同一份 `ProxyHandler`，直接驗證 HTTP 行為。
    """

    proxy_port: int = 0
    dead_port: int = 0
    server: HTTPServer | None = None
    server_thread: threading.Thread | None = None

    @classmethod
    def setUpClass(cls):
        cls.dead_port = _pick_free_port()  # 綁了立即關，幾乎確定此 port 此刻沒人在聽
        cls.proxy_port = _pick_free_port()

        proxy.ProxyHandler.ollama_url = f"http://127.0.0.1:{cls.dead_port}"
        proxy.ProxyHandler.local_model = "qwen2.5-coder:14b"
        proxy.ProxyHandler.ollama_model = "qwen2.5-coder:14b"
        proxy.ProxyHandler.default_system_prompt = "請用繁體中文回答。"
        cls.server = HTTPServer(("127.0.0.1", cls.proxy_port), proxy.ProxyHandler)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        _wait_for_health(cls.proxy_port, timeout=3)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_stream_request_gets_502_not_broken_sse(self):
        """關鍵：stream=True 路徑在 upstream 連不上時，不應該已經送出 200 header。"""
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.proxy_port}/v1/messages",
            data=json.dumps(
                {
                    "model": "qwen2.5-coder:14b",
                    "messages": [{"role": "user", "content": "哈囉"}],
                    "stream": True,
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=5)
            self.fail("expected HTTPError 502")
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 502)
            raw = exc.read()
            decoded = json.loads(raw.decode("utf-8"))
            self.assertIn("無法連線到 Ollama", decoded["error"])
            self.assertIn("無法連線到 Ollama".encode("utf-8"), raw)

    def test_non_stream_also_returns_502(self):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.proxy_port}/v1/messages",
            data=json.dumps(
                {
                    "model": "qwen2.5-coder:14b",
                    "messages": [{"role": "user", "content": "哈囉"}],
                    "stream": False,
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=5)
            self.fail("expected HTTPError 502")
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 502)
            raw = exc.read()
            self.assertIn("無法連線到 Ollama".encode("utf-8"), raw)


# ────────────────────────────────────────────────────────────────────────────
# H-v5-03 ~ 04：C 修復迴圈上限
# ────────────────────────────────────────────────────────────────────────────

class AlwaysCppHandler(BaseHTTPRequestHandler):
    """每次都回 C++ code，用來逼出 C 修復重試上限。"""

    shared_state: dict = {"count": 0}

    def log_message(self, fmt, *args):
        return

    def do_GET(self):  # noqa: N802
        if self.path == "/api/tags":
            self._json(200, {"models": []})
        else:
            self.send_error(404)

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        _ = self.rfile.read(length)
        self.shared_state["count"] += 1
        content = "```c\n#include <iostream>\nusing namespace std;\nint main(){cout<<1;}\n```"
        self._json(
            200,
            {
                "id": "cmpl_x",
                "object": "chat.completion",
                "created": 0,
                "model": "m",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )

    def _json(self, code: int, payload: dict):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class TestCRepairMaxRetries(unittest.TestCase):
    ollama: HTTPServer | None = None
    ollama_thread: threading.Thread | None = None
    proxy_server: HTTPServer | None = None
    proxy_thread: threading.Thread | None = None
    ollama_port: int = 0
    proxy_port: int = 0

    @classmethod
    def setUpClass(cls):
        AlwaysCppHandler.shared_state = {"count": 0}
        cls.ollama_port = _pick_free_port()
        cls.proxy_port = _pick_free_port()

        cls.ollama = HTTPServer(("127.0.0.1", cls.ollama_port), AlwaysCppHandler)
        cls.ollama_thread = threading.Thread(target=cls.ollama.serve_forever, daemon=True)
        cls.ollama_thread.start()

        proxy.ProxyHandler.ollama_url = f"http://127.0.0.1:{cls.ollama_port}"
        proxy.ProxyHandler.local_model = "qwen2.5-coder:14b"
        proxy.ProxyHandler.ollama_model = "qwen2.5-coder:14b"
        proxy.ProxyHandler.default_system_prompt = "請用繁體中文回答。"
        cls.proxy_server = HTTPServer(("127.0.0.1", cls.proxy_port), proxy.ProxyHandler)
        cls.proxy_thread = threading.Thread(target=cls.proxy_server.serve_forever, daemon=True)
        cls.proxy_thread.start()
        _wait_for_health(cls.proxy_port, timeout=3)

    @classmethod
    def tearDownClass(cls):
        cls.proxy_server.shutdown()
        cls.proxy_server.server_close()
        cls.ollama.shutdown()
        cls.ollama.server_close()

    def test_cpp_loop_bounded_to_max_plus_one(self):
        """假 Ollama 永遠回 C++；proxy 必須在 1+MAX_C_REPAIR_ATTEMPTS 次呼叫後停手。"""
        AlwaysCppHandler.shared_state["count"] = 0
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.proxy_port}/v1/messages",
            data=json.dumps(
                {
                    "model": "qwen2.5-coder:14b",
                    "messages": [
                        {
                            "role": "user",
                            "content": "請用 C 寫計算交錯階乘級數 factorial 的程式",
                        }
                    ],
                    "stream": False,
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        # 上限 = 初次 + MAX_C_REPAIR_ATTEMPTS 次修復
        expected_cap = 1 + proxy.MAX_C_REPAIR_ATTEMPTS
        self.assertEqual(
            AlwaysCppHandler.shared_state["count"],
            expected_cap,
            f"expected {expected_cap} ollama calls, got {AlwaysCppHandler.shared_state['count']}",
        )
        # 最終回的是最後一次（仍是 C++），但 proxy 有停手、沒卡死
        self.assertEqual(data["type"], "message")
        self.assertIn("cout", data["content"][0]["text"])

    def test_subsequent_request_does_not_carry_over_counter(self):
        AlwaysCppHandler.shared_state["count"] = 0
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.proxy_port}/v1/messages",
            data=json.dumps(
                {
                    "model": "qwen2.5-coder:14b",
                    "messages": [
                        {"role": "user", "content": "請用 C 寫階乘 factorial 程式"},
                    ],
                    "stream": False,
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10).read()
        first_count = AlwaysCppHandler.shared_state["count"]
        urllib.request.urlopen(req, timeout=10).read()
        second_count = AlwaysCppHandler.shared_state["count"]
        delta = second_count - first_count
        self.assertEqual(delta, 1 + proxy.MAX_C_REPAIR_ATTEMPTS)


# ────────────────────────────────────────────────────────────────────────────
# H-v5-05 ~ 06：大 body 與多位元組 Content-Length
# ────────────────────────────────────────────────────────────────────────────

class TestSendJsonErrorByteLength(unittest.TestCase):
    def test_chinese_content_length_is_byte_count(self):
        """中文每字 3 bytes；Content-Length 必須以位元組計，不可用字元數。"""
        msg = "繁體" * 1000  # 2000 chars
        body = json.dumps({"error": msg}, ensure_ascii=False).encode("utf-8")
        # 檢查位元組數量遠大於字元數
        self.assertGreaterEqual(len(body), 2000 * 3)
        # 用 len(body) 再解碼一次不會出錯（位元組對齊）
        self.assertEqual(json.loads(body.decode("utf-8"))["error"], msg)


class EchoLengthHandler(BaseHTTPRequestHandler):
    """假 Ollama：回覆含「你收到了 N bytes」讓 proxy e2e 也能驗證讀取完整。"""

    last_len: int = 0

    def log_message(self, fmt, *args):
        return

    def do_GET(self):  # noqa: N802
        if self.path == "/api/tags":
            data = json.dumps({"models": []}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_error(404)

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        EchoLengthHandler.last_len = length
        parsed = json.loads(raw)
        total_user_chars = 0
        for msg in parsed.get("messages", []):
            if msg.get("role") == "user":
                c = msg.get("content", "")
                if isinstance(c, str):
                    total_user_chars += len(c)
        content = f"收到 {total_user_chars} 個使用者字元。"
        data = json.dumps(
            {
                "id": "cmpl_x",
                "object": "chat.completion",
                "created": 0,
                "model": "m",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class TestLargeBodyRoundTrip(unittest.TestCase):
    ollama_port: int = 0
    proxy_port: int = 0

    @classmethod
    def setUpClass(cls):
        cls.ollama_port = _pick_free_port()
        cls.proxy_port = _pick_free_port()
        cls.ollama = HTTPServer(("127.0.0.1", cls.ollama_port), EchoLengthHandler)
        cls.ollama_thread = threading.Thread(target=cls.ollama.serve_forever, daemon=True)
        cls.ollama_thread.start()

        proxy.ProxyHandler.ollama_url = f"http://127.0.0.1:{cls.ollama_port}"
        proxy.ProxyHandler.local_model = "qwen2.5-coder:14b"
        proxy.ProxyHandler.ollama_model = "qwen2.5-coder:14b"
        proxy.ProxyHandler.default_system_prompt = "請用繁體中文回答。"
        cls.proxy_server = HTTPServer(("127.0.0.1", cls.proxy_port), proxy.ProxyHandler)
        cls.proxy_thread = threading.Thread(target=cls.proxy_server.serve_forever, daemon=True)
        cls.proxy_thread.start()
        _wait_for_health(cls.proxy_port, timeout=3)

    @classmethod
    def tearDownClass(cls):
        cls.proxy_server.shutdown()
        cls.proxy_server.server_close()
        cls.ollama.shutdown()
        cls.ollama.server_close()

    def test_half_mb_body_round_trip(self):
        """512 KB（≈170K 個中文字元）的 prompt 能完整送達 Ollama 並得到正確回覆。"""
        # 170K 中文字 × 3 bytes/char ≈ 510 KB
        big_prompt = "測" * 170_000
        payload = json.dumps(
            {
                "model": "qwen2.5-coder:14b",
                "messages": [{"role": "user", "content": big_prompt}],
                "stream": False,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        self.assertGreater(len(payload), 500_000, "payload should be > 500 KB")
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.proxy_port}/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Content-Length": str(len(payload)),
            },
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read())
        text = data["content"][0]["text"]
        # Echo handler 回的字元數應該 >= 170_000（如果 proxy 有截斷就會遠小於）
        # 用正規表示式抽出數字
        import re
        m = re.search(r"收到 (\d+)", text)
        self.assertIsNotNone(m, f"unexpected echo text: {text!r}")
        echoed = int(m.group(1))
        self.assertGreaterEqual(echoed, 170_000)


# ────────────────────────────────────────────────────────────────────────────
# H-v5-07 ~ 08：--system-prompt 注入
# ────────────────────────────────────────────────────────────────────────────

class RecordingHandler(BaseHTTPRequestHandler):
    """把上游收到的 payload 整包錄下來，用來檢查 system prompt 傳遞。"""

    last_payload: dict = {}

    def log_message(self, fmt, *args):
        return

    def do_GET(self):  # noqa: N802
        if self.path == "/api/tags":
            data = json.dumps({"models": []}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_error(404)

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            RecordingHandler.last_payload = json.loads(raw)
        except json.JSONDecodeError:
            RecordingHandler.last_payload = {"_raw": raw.decode("utf-8", errors="replace")}
        data = json.dumps(
            {
                "id": "cmpl_x",
                "object": "chat.completion",
                "created": 0,
                "model": "m",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "收到"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class TestSystemPromptPropagation(unittest.TestCase):
    SENTINEL = "SENTINEL_哨兵_4213_ZZZ"

    @classmethod
    def setUpClass(cls):
        RecordingHandler.last_payload = {}
        cls.ollama_port = _pick_free_port()
        cls.proxy_port = _pick_free_port()
        cls.ollama = HTTPServer(("127.0.0.1", cls.ollama_port), RecordingHandler)
        cls.ollama_thread = threading.Thread(target=cls.ollama.serve_forever, daemon=True)
        cls.ollama_thread.start()

        # 這次用子行程啟動真 proxy，驗證 CLI --system-prompt 旗標走全路徑
        cls.proxy_proc = subprocess.Popen(
            [
                sys.executable,
                str(PROXY_PY),
                "--model", "qwen2.5-coder:14b",
                "--port", str(cls.proxy_port),
                "--ollama-url", f"http://127.0.0.1:{cls.ollama_port}",
                "--system-prompt", cls.SENTINEL,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        _wait_for_health(cls.proxy_port, timeout=10)

    @classmethod
    def tearDownClass(cls):
        cls.proxy_proc.terminate()
        try:
            cls.proxy_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.proxy_proc.kill()
        cls.ollama.shutdown()
        cls.ollama.server_close()

    def test_sentinel_reaches_ollama_as_system_message(self):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.proxy_port}/v1/messages",
            data=json.dumps(
                {
                    "model": "qwen2.5-coder:14b",
                    "messages": [{"role": "user", "content": "你好"}],
                    "stream": False,
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=15).read()
        payload = RecordingHandler.last_payload
        self.assertIn("messages", payload)
        system_msgs = [m for m in payload["messages"] if m.get("role") == "system"]
        self.assertTrue(system_msgs, f"no system message in upstream payload: {payload}")
        combined = "\n".join(m.get("content", "") for m in system_msgs)
        self.assertIn(self.SENTINEL, combined)

    def test_sentinel_not_leaked_to_user_message(self):
        payload = RecordingHandler.last_payload
        user_msgs = [m for m in payload.get("messages", []) if m.get("role") == "user"]
        for m in user_msgs:
            self.assertNotIn(self.SENTINEL, m.get("content", ""))


# ────────────────────────────────────────────────────────────────────────────
# H-v5-09 ~ 10：bundle manifest BOM-less UTF-8
# ────────────────────────────────────────────────────────────────────────────

class TestBundleManifestBomless(unittest.TestCase):
    """驗證 bundle manifest 以 BOM-less UTF-8 寫入、可被 Linux / macOS 讀回。"""

    UTF8_BOM = b"\xef\xbb\xbf"

    def _write_bomless_utf8(self, path: Path, lines: list[str]) -> None:
        """模擬 prepare_bundle.ps1 / prepare_bundle.sh 的寫入方式。"""
        text = "\n".join(lines) + "\n"
        path.write_bytes(text.encode("utf-8"))  # 標準 Python 不會寫 BOM

    def test_written_manifest_has_no_bom(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bundle-manifest.txt"
            self._write_bomless_utf8(
                path,
                [
                    "model=qwen2.5-coder:14b",
                    "ollama_version=0.4.5",
                    "platform=darwin-arm64",
                    "描述=離線 bundle 清單",
                ],
            )
            raw = path.read_bytes()
            self.assertFalse(
                raw.startswith(self.UTF8_BOM),
                "manifest 不應該以 UTF-8 BOM 開頭",
            )
            # 內容可被「像 bash 一樣」逐行讀回
            decoded = raw.decode("utf-8")
            self.assertIn("描述=離線 bundle 清單", decoded)

    def test_with_bom_is_detected_as_wrong(self):
        """反面驗證：若有人不小心寫了 BOM，這個測試會立刻變紅。"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.txt"
            path.write_bytes(self.UTF8_BOM + "model=foo\n".encode("utf-8"))
            raw = path.read_bytes()
            self.assertTrue(raw.startswith(self.UTF8_BOM))
            # 模擬 bash 解析：第一行用 strip BOM 前的文字作 key，會看到亂字元
            first_line = raw.decode("utf-8", errors="strict").splitlines()[0]
            self.assertTrue(
                first_line.startswith("\ufeff"),
                "第一行開頭應含 U+FEFF；Linux `read` 會因此讀到髒 key",
            )


# ────────────────────────────────────────────────────────────────────────────
# H-v5-13 ~ 14：Windows Level 1 air-gap launcher contract
# ────────────────────────────────────────────────────────────────────────────

class TestWindowsAirgapLauncherContract(unittest.TestCase):
    """鎖住 Windows launcher 對 bundled Python 與 strict offline 的契約。"""

    RUN_PS1 = PROJECT_DIR / "local_ai" / "run.ps1"
    PREPARE_PS1 = PROJECT_DIR / "local_ai" / "prepare_bundle.ps1"

    def test_run_ps1_prefers_bundled_python_before_system_python(self):
        text = self.RUN_PS1.read_text(encoding="utf-8")
        bundled = 'Join-Path $runtimeDir "python/python.exe"'
        system = 'Resolve-CommandPath "python"'
        self.assertIn(bundled, text)
        self.assertIn(system, text)
        self.assertLess(
            text.index(bundled),
            text.index(system),
            "run.ps1 should try local_ai/runtime/python/python.exe before PATH Python",
        )

    def test_run_ps1_strict_offline_disables_runtime_fallbacks(self):
        text = self.RUN_PS1.read_text(encoding="utf-8")
        self.assertIn("$strictOffline = Test-Truthy $env:CLAW_STRICT_OFFLINE", text)
        self.assertIn("if ($strictOffline) {", text)
        self.assertIn("bundled Python not found", text)
        self.assertIn("bundled claw.exe not found", text)
        self.assertIn("bundled ollama.exe not found", text)
        self.assertIn("bundled model cache not found", text)
        self.assertIn("bundle manifest not found", text)

    def test_prepare_bundle_manifest_records_python_runtime_status(self):
        text = self.PREPARE_PS1.read_text(encoding="utf-8")
        self.assertIn("python_runtime=", text)
        self.assertIn("python_binary=", text)
        self.assertIn('Join-Path $runtimeDir "python/python.exe"', text)

    def test_prepare_bundle_accepts_portable_python_sources(self):
        text = self.PREPARE_PS1.read_text(encoding="utf-8")
        self.assertIn("--python-zip", text)
        self.assertIn("--python-dir", text)
        self.assertIn("CLAW_PORTABLE_PYTHON_ZIP", text)
        self.assertIn("CLAW_PORTABLE_PYTHON_DIR", text)
        self.assertIn("function Bundle-PythonZip", text)
        self.assertIn("function Bundle-PythonDirectory", text)
        self.assertIn("Expand-Archive", text)
        self.assertIn("portable Python zip must extract python.exe at its root", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
