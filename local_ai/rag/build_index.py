#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ALLOWED_SUFFIXES = {".md", ".txt", ".c", ".h", ".py", ".json", ".csv"}
TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")


def default_rag_dir() -> Path:
    return Path(__file__).resolve().parent


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def _split_markdown(text: str) -> list[tuple[str, str]]:
    chunks: list[tuple[str, str]] = []
    current_heading = ""
    current: list[str] = []
    for line in text.splitlines():
        if line.lstrip().startswith("#") and current:
            chunks.append((current_heading, "\n".join(current).strip()))
            current = []
        if line.lstrip().startswith("#"):
            current_heading = line.strip()
        current.append(line)
    if current:
        chunks.append((current_heading, "\n".join(current).strip()))
    return chunks


def _split_plain(text: str, max_lines: int = 40) -> list[tuple[str, str]]:
    lines = text.splitlines()
    chunks: list[tuple[str, str]] = []
    for start in range(0, len(lines), max_lines):
        part = "\n".join(lines[start : start + max_lines]).strip()
        if part:
            chunks.append(("", part))
    return chunks


def build_index(docs_dir: Path | None = None, index_dir: Path | None = None) -> dict[str, Any]:
    rag_dir = default_rag_dir()
    docs = docs_dir or (rag_dir / "docs")
    index = index_dir or (rag_dir / "index")
    docs.mkdir(parents=True, exist_ok=True)
    index.mkdir(parents=True, exist_ok=True)

    passages: list[dict[str, Any]] = []
    document_frequency: Counter[str] = Counter()
    for path in sorted(docs.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in ALLOWED_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="replace")
        chunks = _split_markdown(text) if path.suffix.lower() == ".md" else _split_plain(text)
        for chunk_index, (heading, content) in enumerate(chunks):
            if not content:
                continue
            rel = path.relative_to(docs).as_posix()
            tokens = tokenize(" ".join([path.name, heading, content]))
            counts = Counter(tokens)
            record = {
                "id": len(passages),
                "source": rel,
                "heading": heading,
                "chunk": chunk_index,
                "text": content[:2500],
                "tokens": dict(counts),
                "length": max(1, sum(counts.values())),
            }
            passages.append(record)
            document_frequency.update(set(counts))

    payload = {
        "version": 1,
        "docs_dir": str(docs),
        "passage_count": len(passages),
        "document_frequency": dict(document_frequency),
        "passages": passages,
    }
    (index / "index.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build local offline RAG keyword index")
    parser.add_argument("--docs-dir", default=None)
    parser.add_argument("--index-dir", default=None)
    args = parser.parse_args()
    payload = build_index(
        Path(args.docs_dir).expanduser() if args.docs_dir else None,
        Path(args.index_dir).expanduser() if args.index_dir else None,
    )
    print(json.dumps({"ok": True, "passage_count": payload["passage_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
