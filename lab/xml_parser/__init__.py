"""Project Mythos — IRS e-File Compliance Analysis Tool.

Automated rollover review, XML comparison, and quality validation
for US International Tax Compliance (Forms 5471, 8858, 8865, 8992, 1118).

Parse IRS e-file returns (1120/1065) into structured DataFrames,
compare across years/versions, reconcile against workbooks, and
generate professional reports.
"""

__version__ = "0.6.0"
__project__ = "Project Mythos"

from lab.xml_parser.parser import EFileParser
from lab.xml_parser.comparator import XMLComparator
from lab.xml_parser.workbook_reader import WorkbookReader
from lab.xml_parser.reconciler import Reconciler
from lab.xml_parser.review_engine import ReviewEngine
