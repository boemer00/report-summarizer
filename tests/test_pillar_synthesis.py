"""Unit tests for PillarSynopsisGenerator (selection and synthesis)."""

from typing import List

import types

from src.summarization.pillar_synthesis import PillarSynopsisGenerator
from src.core.models import DocumentChunk


def make_chunk(idx: int, doc_id: str, text: str, emb_size: int = 8) -> DocumentChunk:
    # Simple deterministic embedding for tests
    embedding = [float((idx + j) % 5) for j in range(emb_size)]
    return DocumentChunk(
        id=f"c{idx}",
        document_id=doc_id,
        content=text,
        embedding=embedding,
        metadata={},
    )


def test_select_representative_chunks_prefers_diversity():
    gen = PillarSynopsisGenerator(api_key="dummy")
    # Many chunks from same doc and a few from another doc; should spread selection
    chunks: List[DocumentChunk] = []
    for i in range(10):
        chunks.append(make_chunk(i, "d1", "A" * 300 + f" {i}"))
    for i in range(10, 14):
        chunks.append(make_chunk(i, "d2", "B" * 300 + f" {i}"))

    selected = gen.select_representative_chunks(chunks, k=6)
    assert 1 <= len(selected) <= 6
    # Ensure we didn't only pick from a single doc
    docs = {c.document_id for c in selected}
    assert len(docs) >= 2


def test_generate_synopsis_uses_stubbed_llm_and_adds_sources():
    gen = PillarSynopsisGenerator(api_key="dummy")

    # Stub LLM invoke
    class Stub:
        def __init__(self, content: str):
            self.content = content

    def fake_ensure_llm():
        class FakeLLM:
            def invoke(self, prompt: str):
                return Stub("Paragraph one.\n\nParagraph two.")

        gen.llm = FakeLLM()

    gen._ensure_llm = fake_ensure_llm  # type: ignore

    chunks = [
        make_chunk(1, "d1", "Insight about AI and trust." + " X" * 200),
        make_chunk(2, "d2", "Another insight about performance." + " Y" * 200),
        make_chunk(3, "d3", "Customer journey friction points." + " Z" * 200),
    ]

    doc_info = {
        "d1": {"title": "Doc One", "url": "https://one"},
        "d2": {"title": "Doc Two", "url": "https://two"},
        "d3": {"title": "Doc Three", "url": "https://three"},
    }

    out = gen.generate_synopsis(
        pillar_name="AI",
        chunks=chunks,
        doc_info_by_id=doc_info,
        max_source_citations=2,
        paragraphs=2,
    )

    assert "Paragraph one." in out
    assert "Sources:" in out
    assert "Doc One" in out or "https://one" in out
