#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from .build_index import build_index, default_rag_dir, tokenize
except ImportError:  # pragma: no cover
    from build_index import build_index, default_rag_dir, tokenize


def _index_path(index_dir: Path | None = None) -> Path:
    return (index_dir or (default_rag_dir() / "index")) / "index.json"


def load_index(index_dir: Path | None = None, rebuild_if_missing: bool = True) -> dict[str, Any]:
    path = _index_path(index_dir)
    if not path.exists() and rebuild_if_missing:
        build_index()
    if not path.exists():
        return {"passages": [], "document_frequency": {}, "passage_count": 0}
    return json.loads(path.read_text(encoding="utf-8"))


def search(query: str, top_k: int = 5, index_dir: Path | None = None) -> list[dict[str, Any]]:
    idx = load_index(index_dir)
    passages = idx.get("passages", [])
    if not passages or not query.strip():
        return []
    q_counts = Counter(tokenize(query))
    if not q_counts:
        return []
    doc_count = max(1, int(idx.get("passage_count") or len(passages)))
    df = idx.get("document_frequency", {})
    results: list[dict[str, Any]] = []
    for passage in passages:
        tokens = passage.get("tokens", {})
        score = 0.0
        for token, q_weight in q_counts.items():
            tf = float(tokens.get(token, 0))
            if tf <= 0:
                continue
            idf = math.log((doc_count + 1) / (float(df.get(token, 0)) + 0.5)) + 1.0
            score += q_weight * idf * (tf / (tf + 1.2))
        filename = passage.get("source", "").lower()
        heading = passage.get("heading", "").lower()
        lowered_query = query.lower()
        if lowered_query and lowered_query in filename:
            score += 2.0
        for token in q_counts:
            if token in filename:
                score += 0.8
            if token in heading:
                score += 0.6
        if score > 0:
            results.append({
                "score": round(score, 4),
                "source": passage.get("source", ""),
                "heading": passage.get("heading", ""),
                "text": passage.get("text", ""),
            })
    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:top_k]


def format_context(results: list[dict[str, Any]], max_chars: int = 6000) -> str:
    if not results:
        return ""
    sources: list[str] = []
    parts = ["參考本地文件："]
    for result in results:
        source = f"local_ai/rag/docs/{result['source']}"
        if source not in sources:
            sources.append(source)
            parts.append(f"- {source}")
    parts.append("\n以下是可用的本地文件片段，請只在相關時引用：")
    used = len("\n".join(parts))
    for result in results:
        heading = f" {result['heading']}" if result.get("heading") else ""
        block = f"\n[source: local_ai/rag/docs/{result['source']}{heading}]\n{result['text'].strip()}\n"
        if used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)
    return "\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Search local offline RAG docs")
    parser.add_argument("query")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    results = search(args.query, args.top_k)
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(format_context(results))


if __name__ == "__main__":
    main()
