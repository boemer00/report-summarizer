"""Pytest scaffolds for thematic classifier."""

from typing import Dict

import pytest


def test_classify_chunks_signature_exists():
    """Ensure ThematicClassifier exposes the expected public method."""
    from src.processing.thematic_classifier import ThematicClassifier

    clf = ThematicClassifier()
    assert hasattr(clf, "classify_chunks")


def test_thematic_pillar_enum_values():
    """Ensure ThematicPillar contains the three expected values."""
    from src.processing.thematic_classifier import ThematicPillar

    assert {p.value for p in ThematicPillar} == {
        "ai",
        "customer_journey",
        "digital_performance",
    }
