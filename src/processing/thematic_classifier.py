from __future__ import annotations

"""Thematic classifier scaffolding for routing chunks into fixed pillars.

This module introduces a deterministic classification mode that assigns
document chunks into three predefined pillars: AI, Customer Journey, and
Digital Performance. It is designed to replace or complement automatic
clustering for use cases that require fixed topical sections.

Implementation will leverage embedding similarity against short anchor
definitions tuned for the ICP, with optional keyword boosting and a
configurable similarity threshold.
"""

from enum import Enum
from typing import Dict, List, Tuple

import numpy as np

import src.core.config as config
from src.processing.vector_store import VectorStore
from src.core.models import DocumentChunk


class ThematicPillar(str, Enum):
    """Fixed pillars for thematic routing."""

    AI = "ai"
    CUSTOMER_JOURNEY = "customer_journey"
    DIGITAL_PERFORMANCE = "digital_performance"


class ThematicClassifier:
    """Classify chunks into fixed pillars based on embeddings.

    Public interface only; implementation will be added in the Implement step.
    """

    def __init__(self) -> None:
        """Initialize classifier and prepare anchor embeddings.

        Will load configuration from environment (thresholds, audience_profile)
        and compute or lazily compute anchor embeddings for the three pillars.
        """
        self.settings = config.settings or config.init_settings()
        self.threshold: float = float(self.settings.thematic_threshold)
        # ICP-aware anchor definitions
        self.anchors: Dict[ThematicPillar, str] = {
            ThematicPillar.AI: (
                "Artificial intelligence in considered-purchase journeys for B2B/B2C premium brands:"
                " impact on trust, evaluation, ROI, reliability, agentic/assistive experiences,"
                " data/ethics, and org adoption."
            ),
            ThematicPillar.CUSTOMER_JOURNEY: (
                "End-to-end buyer journey from problem to provider decision in high-stakes contexts;"
                " confidence-building touchpoints, reassurance, proof signals, empathy, risks across"
                " marketing-sales-postpurchase handoffs."
            ),
            ThematicPillar.DIGITAL_PERFORMANCE: (
                "Digital experience as proof of reliability: speed, stability, personalization, UX clarity,"
                " content quality, measurement/attribution, conversion, and trust signals."
            ),
        }
        # Defer embedding of anchors; EmbeddingGenerator is independent; we compute on demand
        self._anchor_embeddings: Dict[ThematicPillar, np.ndarray] = {}

    def _ensure_anchor_embeddings(self) -> None:
        """Compute anchor embeddings once using the pipeline's embedding model."""
        from src.processing.embeddings import EmbeddingGenerator

        if self._anchor_embeddings:
            return
        generator = EmbeddingGenerator()
        for pillar, text in self.anchors.items():
            emb = generator.generate_embedding(text)
            self._anchor_embeddings[pillar] = np.array(emb, dtype=np.float32) if emb else np.zeros(1536, dtype=np.float32)

    def _cosine(self, a: np.ndarray, b: np.ndarray) -> float:
        if a.size == 0 or b.size == 0:
            return 0.0
        na = np.linalg.norm(a)
        nb = np.linalg.norm(b)
        if na == 0.0 or nb == 0.0:
            return 0.0
        return float(np.dot(a, b) / (na * nb))

    def _keyword_boost(self, text: str, pillar: ThematicPillar, base: float) -> float:
        """Apply a small boost based on indicative keywords to avoid false negatives."""
        if not text:
            return base
        t = text.lower()
        boost = 0.0
        if pillar == ThematicPillar.AI:
            if any(k in t for k in [" ai ", " artificial intelligence", "gen ai", "gpt", "llm", "agentic"]):
                boost += 0.05
        elif pillar == ThematicPillar.DIGITAL_PERFORMANCE:
            if any(k in t for k in ["core web vitals", "lcp", "ttfb", "page speed", "conversion rate", "performance"]):
                boost += 0.03
        elif pillar == ThematicPillar.CUSTOMER_JOURNEY:
            if any(k in t for k in ["journey", "evaluation", "touchpoint", "case study", "demo", "sales follow-up"]):
                boost += 0.03
        return base + boost

    def classify_chunks(self, vector_store: VectorStore) -> Dict[ThematicPillar, List[DocumentChunk]]:
        """Assign chunks to pillars.

        Args:
            vector_store: The vector store containing all chunks and embeddings.

        Returns:
            Mapping from pillar to a list of associated chunks.
        """
        self._ensure_anchor_embeddings()

        assignments: Dict[ThematicPillar, List[DocumentChunk]] = {
            ThematicPillar.AI: [],
            ThematicPillar.CUSTOMER_JOURNEY: [],
            ThematicPillar.DIGITAL_PERFORMANCE: [],
        }

        for chunk in vector_store.get_all_chunks():
            if not chunk.embedding:
                continue
            e = np.array(chunk.embedding, dtype=np.float32)
            scores: List[Tuple[ThematicPillar, float]] = []
            for pillar, anchor_emb in self._anchor_embeddings.items():
                score = self._cosine(e, anchor_emb)
                # apply lightweight keyword boost using content
                score = self._keyword_boost(chunk.content, pillar, score)
                scores.append((pillar, score))

            # Choose the best pillar if over threshold
            pillar, best = max(scores, key=lambda s: s[1])
            if best >= self.threshold:
                assignments[pillar].append(chunk)

        # If nothing was assigned (too strict), lower threshold once and retry quickly
        if not any(assignments.values()):
            fallback_threshold = max(0.1, self.threshold * 0.75)
            for chunk in vector_store.get_all_chunks():
                if not chunk.embedding:
                    continue
                e = np.array(chunk.embedding, dtype=np.float32)
                best_pillar, best_score = None, -1.0
                for pillar, anchor_emb in self._anchor_embeddings.items():
                    score = self._cosine(e, anchor_emb)
                    score = self._keyword_boost(chunk.content, pillar, score)
                    if score > best_score:
                        best_score = score
                        best_pillar = pillar
                if best_pillar and best_score >= fallback_threshold:
                    assignments[best_pillar].append(chunk)

        return assignments
