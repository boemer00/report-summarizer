"""Pytest scaffolds for pillar summarization."""

import pytest


def test_summarize_pillar_signature_exists():
    from src.summarization.summarizer import Summarizer

    s = Summarizer(api_key="dummy")
    assert hasattr(s, "summarize_pillar")
