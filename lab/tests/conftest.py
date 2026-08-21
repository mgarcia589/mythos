"""Shared pytest fixtures for Mythos test suite."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lab.xml_parser.parser import EFileParser
from lab.xml_parser.review_engine import ReviewEngine, ReviewReport

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_cy_path():
    return FIXTURES / "sample_cy.xml"


@pytest.fixture
def sample_py_path():
    return FIXTURES / "sample_py.xml"


@pytest.fixture
def parser_cy(sample_cy_path):
    return EFileParser(sample_cy_path)


@pytest.fixture
def parser_py(sample_py_path):
    return EFileParser(sample_py_path)


@pytest.fixture
def review_report(sample_cy_path, sample_py_path) -> ReviewReport:
    """Full review with both CY and PY — the main baseline fixture."""
    engine = ReviewEngine()
    return engine.review(sample_cy_path, sample_py_path)


@pytest.fixture
def review_report_cy_only(sample_cy_path) -> ReviewReport:
    """Review with only CY (no rollover checks)."""
    engine = ReviewEngine()
    return engine.review(sample_cy_path)
