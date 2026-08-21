"""Shared utilities for check modules."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Callable

import pandas as pd

from lab.xml_parser.core.models import Finding

if TYPE_CHECKING:
    from lab.xml_parser.parser import EFileParser


class CheckContext:
    """Lightweight context passed to each check module.

    Provides access to the parser, DataFrame, and entity name resolver,
    plus accumulates findings via add().
    """

    def __init__(
        self,
        parser: EFileParser,
        df: pd.DataFrame,
        get_entity_name: Callable[[pd.DataFrame, str], str],
        prior_parser: EFileParser | None = None,
    ):
        self.parser = parser
        self.df = df
        self._get_entity_name = get_entity_name
        self.prior_parser = prior_parser
        self._findings: list[Finding] = []

    def entity_name(self, code: str) -> str:
        return self._get_entity_name(self.df, code)

    def add(
        self,
        *,
        check_id: str,
        severity: str,
        category: str,
        entity_code: str,
        entity_name: str,
        description: str,
        expected: str = "",
        actual: str = "",
        delta: float | None = None,
        context: str = "",
    ) -> None:
        self._findings.append(Finding(
            check_id=check_id,
            severity=severity,
            category=category,
            entity_code=entity_code,
            entity_name=entity_name,
            description=description,
            expected=expected,
            actual=actual,
            delta=delta,
            context=context,
        ))

    @property
    def findings(self) -> list[Finding]:
        return self._findings


def safe_float(row: pd.Series, col: str) -> float | None:
    """Extract a numeric value from a DataFrame row, returning None on failure."""
    try:
        val = row[col] if col in row.index else None
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return None
        return float(val)
    except (ValueError, TypeError, KeyError):
        return None
