"""Check modules — each category of automated compliance checks."""

from lab.xml_parser.engine.checks.flow import run_flow_checks
from lab.xml_parser.engine.checks.completeness import run_completeness_checks
from lab.xml_parser.engine.checks.reasonableness import run_reasonableness_checks
from lab.xml_parser.engine.checks.rollover import run_rollover_checks
from lab.xml_parser.engine.checks.cross_schedule import run_cross_schedule_checks
from lab.xml_parser.engine.checks.cross_form import run_cross_form_checks
from lab.xml_parser.engine.checks.form_8990 import run_form_8990_checks

ALL_CHECKS = [
    ("flow", run_flow_checks),
    ("completeness", run_completeness_checks),
    ("reasonableness", run_reasonableness_checks),
    ("rollover", run_rollover_checks),
    ("cross_schedule", run_cross_schedule_checks),
    ("cross_form", run_cross_form_checks),
    ("section_163j", run_form_8990_checks),
]

__all__ = [
    "run_flow_checks",
    "run_completeness_checks",
    "run_reasonableness_checks",
    "run_rollover_checks",
    "run_cross_schedule_checks",
    "run_cross_form_checks",
    "run_form_8990_checks",
    "ALL_CHECKS",
]
