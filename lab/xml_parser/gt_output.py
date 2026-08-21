"""Great Tables output — backward-compat shim.

All functionality now lives in lab.xml_parser.export.html_exporter.
This module delegates for existing callers.
"""

from lab.xml_parser.export.html_exporter import (
    summary_table as gt_summary_table,
    detail_table as gt_detail_table,
    export_html as gt_full_review,
)

__all__ = ["gt_summary_table", "gt_detail_table", "gt_full_review"]
