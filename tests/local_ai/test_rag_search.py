from __future__ import annotations

from pathlib import Path

from local_ai.rag.build_index import build_index
from local_ai.rag.search_docs import search


def test_rag_search_finds_relevant_markdown_section(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    index = tmp_path / "index"
    docs.mkdir()
    (docs / "c_pointer_notes.md").write_text(
        "# Pointer\nC pointer stores an address and uses * to dereference.\n\n"
        "# Array\nArray elements are contiguous.",
        encoding="utf-8",
    )
    build_index(docs, index)
    results = search("pointer dereference address", index_dir=index)
    assert results
    assert results[0]["source"] == "c_pointer_notes.md"
    assert "dereference" in results[0]["text"]
