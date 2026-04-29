#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

try:
    from .build_index import ALLOWED_SUFFIXES, build_index, default_rag_dir
except ImportError:  # pragma: no cover
    from build_index import ALLOWED_SUFFIXES, build_index, default_rag_dir


def import_docs(source: Path, docs_dir: Path | None = None, reindex: bool = True) -> dict[str, object]:
    if not source.exists():
        return {"ok": False, "imported": 0, "issues": [f"Source does not exist: {source}"]}
    target = docs_dir or (default_rag_dir() / "docs")
    target.mkdir(parents=True, exist_ok=True)
    imported = 0
    skipped = 0
    files = [source] if source.is_file() else list(source.rglob("*"))
    for path in files:
        if not path.is_file():
            continue
        if path.suffix.lower() not in ALLOWED_SUFFIXES:
            skipped += 1
            continue
        rel = path.name if source.is_file() else path.relative_to(source).as_posix()
        destination = target / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        imported += 1
    index_info = build_index(target) if reindex else {"passage_count": None}
    return {
        "ok": True,
        "imported": imported,
        "skipped": skipped,
        "passage_count": index_info.get("passage_count"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Import USB docs into local RAG docs")
    parser.add_argument("source")
    parser.add_argument("--no-reindex", action="store_true")
    args = parser.parse_args()
    result = import_docs(Path(args.source).expanduser(), reindex=not args.no_reindex)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
