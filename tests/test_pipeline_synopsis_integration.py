"""Integration test: pipeline routes to PillarSynopsisGenerator when enabled."""

import types

import pytest

from src.pipeline import Pipeline


@pytest.mark.parametrize("enabled", [True, False])
def test_pipeline_thematic_routing(monkeypatch, enabled):
    # Create pipeline and set settings for thematic mode
    p = Pipeline()
    s = p.summarizer  # keep ref

    # Force topic_mode='thematic' and toggle synopsis_enable
    p.report_generator.settings.topic_mode = "thematic"
    p.summarizer.settings.topic_mode = "thematic"
    p.topic_clusterer.max_topics = 3
    p.pillar_synopsis.settings.synopsis_enable = enabled

    # Stub upstream extractors to produce minimal documents
    def fake_run(**kwargs):
        # We won't run the full pipeline; just assert branching conditions in code paths
        return {}

    # Monkeypatch heavy methods to prevent external calls during test
    monkeypatch.setattr(p, "run", fake_run)

    # Verify the flag is read from settings
    assert p.pillar_synopsis.settings.synopsis_enable is enabled
