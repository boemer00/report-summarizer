"""Pytest scaffolds for thematic report rendering."""

import pytest


def test_render_thematic_report_signature_exists():
    from src.summarization.report_generator import ReportGenerator

    rg = ReportGenerator()
    assert hasattr(rg, "render_thematic_report")
