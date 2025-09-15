from typing import List, Dict, Optional, Tuple

import numpy as np
from langchain_openai import ChatOpenAI

from src.core import config
from src.core.models import DocumentChunk


class PillarSynopsisGenerator:
    """Generate a concise 1–2 paragraph synopsis per thematic pillar.

    This generator selects a diverse, representative subset of chunks and then
    synthesizes a deeper, cross-document narrative suitable for executive
    consumption.
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        """Initialize generator and load settings."""
        self.settings = config.settings or config.init_settings()
        self.api_key = api_key or self.settings.openai_api_key
        self.llm: Optional[ChatOpenAI] = None

    def _ensure_llm(self) -> None:
        if self.llm is None:
            self.llm = ChatOpenAI(
                api_key=self.api_key,
                model=self.settings.openai_model_summarization,
                temperature=0.2,
                max_tokens=1200,
            )

    @staticmethod
    def _cosine(a: np.ndarray, b: np.ndarray) -> float:
        if a.size == 0 or b.size == 0:
            return 0.0
        na = np.linalg.norm(a)
        nb = np.linalg.norm(b)
        if na == 0.0 or nb == 0.0:
            return 0.0
        return float(np.dot(a, b) / (na * nb))

    def _normalize_text(self, text: str) -> str:
        return " ".join((text or "").lower().split())

    def _filter_candidates(self, chunks: List[DocumentChunk], min_chars: int = 180) -> List[DocumentChunk]:
        seen: set = set()
        filtered: List[DocumentChunk] = []
        for c in chunks:
            if not c or not c.content:
                continue
            if len(c.content.strip()) < min_chars:
                continue
            if not c.embedding:
                continue
            key = self._normalize_text(c.content)[:400]
            if key in seen:
                continue
            seen.add(key)
            filtered.append(c)
        return filtered

    def select_representative_chunks(self, chunks: List[DocumentChunk], k: int = 12) -> List[DocumentChunk]:
        """Select a diversity-aware subset of chunks as synopsis inputs.

        Uses MMR against a pillar centroid with per-document caps and quality filters.
        """
        if not chunks:
            return []

        candidates = self._filter_candidates(chunks, min_chars=180)
        if not candidates:
            return []

        # Build embedding matrix
        embeddings: List[np.ndarray] = [np.array(c.embedding, dtype=np.float32) for c in candidates]
        # Compute centroid
        matrix = np.vstack(embeddings)
        centroid = np.mean(matrix, axis=0)

        lambda_mmr: float = float(self.settings.synopsis_mmr_lambda)
        # Respect explicit k argument; fall back to settings if not provided
        target_k: int = int(k) if k is not None else int(self.settings.synopsis_selection_k)
        target_k = max(1, min(target_k, len(candidates)))

        # Per-document cap to ensure spread
        per_doc_cap: int = 3
        doc_counts: Dict[str, int] = {}

        selected: List[int] = []
        remaining: List[int] = list(range(len(candidates)))

        def relevance(idx: int) -> float:
            return self._cosine(embeddings[idx], centroid)

        def novelty(idx: int) -> float:
            if not selected:
                return 0.0
            sims = [self._cosine(embeddings[idx], embeddings[j]) for j in selected]
            return max(sims) if sims else 0.0

        # First pass with per-doc cap enforced
        while len(selected) < target_k and remaining:
            scored: List[Tuple[int, float]] = []
            for idx in remaining:
                doc_id = candidates[idx].document_id
                if doc_counts.get(doc_id, 0) >= per_doc_cap:
                    continue
                score = lambda_mmr * relevance(idx) - (1.0 - lambda_mmr) * novelty(idx)
                scored.append((idx, score))
            if not scored:
                break
            scored.sort(key=lambda t: t[1], reverse=True)
            best_idx = scored[0][0]
            selected.append(best_idx)
            remaining.remove(best_idx)
            doc = candidates[best_idx].document_id
            doc_counts[doc] = doc_counts.get(doc, 0) + 1

        # Second pass without per-doc cap (fill if needed)
        while len(selected) < target_k and remaining:
            scored = [(idx, lambda_mmr * relevance(idx) - (1.0 - lambda_mmr) * novelty(idx)) for idx in remaining]
            scored.sort(key=lambda t: t[1], reverse=True)
            best_idx = scored[0][0]
            selected.append(best_idx)
            remaining.remove(best_idx)

        return [candidates[i] for i in selected]

    def generate_synopsis(
        self,
        pillar_name: str,
        chunks: List[DocumentChunk],
        doc_info_by_id: Dict[str, Dict[str, str]],
        *,
        max_source_citations: int = 3,
        paragraphs: int = 2,
    ) -> str:
        """Create a 1–2 paragraph synthesis for the given pillar.

        Aggregates agreements/disagreements and implications, then appends a Sources line.
        """
        self._ensure_llm()

        selected = self.select_representative_chunks(
            chunks,
            k=int(self.settings.synopsis_selection_k),
        )

        if not selected:
            return f"No sufficient content to summarize for {pillar_name}."

        # Prepare text samples
        samples = []
        cited_doc_ids: List[str] = []
        for c in selected:
            # Keep a modest preview length
            samples.append(c.content.strip()[:600])
            cited_doc_ids.append(c.document_id)

        # Build stable citation order by first appearance in the original chunks input
        first_index: Dict[str, int] = {}
        for i, ch in enumerate(chunks):
            if ch.document_id not in first_index:
                first_index[ch.document_id] = i

        unique_selected_docs = []
        seen_docs: set = set()
        for d in cited_doc_ids:
            if d not in seen_docs:
                unique_selected_docs.append(d)
                seen_docs.add(d)

        ordered_docs = sorted(unique_selected_docs, key=lambda d: first_index.get(d, 10**9))

        citations: List[str] = []
        for doc_id in ordered_docs[: int(max_source_citations)]:
            info = doc_info_by_id.get(doc_id, {})
            title = (info.get("title") or "Source").strip()
            url = (info.get("url") or "").strip()
            citations.append(f"{title} ({url})" if url else title)

        instructions = (
            "You are an expert analyst writing for the following ICP (audience):\n"
            f"{self.settings.audience_profile}\n\n"
            "Synthesize across sources for the pillar below.\n"
            "Write exactly 1–2 dense paragraphs (no bullets).\n"
            "Be concrete: highlight agreements and disagreements across sources,\n"
            "explain implications, and avoid generic claims.\n"
            "Do not include extra headings or lists."
        )

        prompt = (
            f"Pillar: {pillar_name}\n\n"
            f"Text samples (representative excerpts):\n\n"
            + "\n\n".join(samples)
            + "\n\n"
            + f"Output: {paragraphs} paragraph(s) of analysis only."
        )

        try:
            response = self.llm.invoke(
                instructions + "\n\n" + prompt
            )
            content = getattr(response, "content", str(response)).strip()
        except Exception as exc:
            content = f"Error generating synopsis for {pillar_name}: {exc}"

        sources_line = "Sources: " + "; ".join(citations) if citations else ""
        if sources_line:
            return content + "\n\n" + sources_line
        return content
