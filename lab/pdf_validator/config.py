"""Configuration for PDF Validator module.

Resolution order:
1. Explicit kwargs passed to PDFValidatorConfig()
2. Environment variables (PDF_VALIDATOR_*)
3. Defaults
"""

import os
from dataclasses import dataclass, field
from pathlib import Path


def _project_root() -> Path:
    """Walk up from this file to find the Cerebro root."""
    p = Path(__file__).resolve()
    for parent in p.parents:
        if (parent / "CLAUDE.md").exists():
            return parent
    return Path.cwd()


@dataclass
class PDFValidatorConfig:
    """Configuration for PDF validation runs."""

    # Materiality threshold for flagging discrepancies (in dollars)
    tolerance: float = 10.0

    # Default output directory
    output_dir: Path = field(default_factory=lambda: _project_root() / "output" / "pdf-validation")

    # Default sources directory
    sources_dir: Path = field(default_factory=lambda: _project_root() / "sources")

    # Pools to skip during reconciliation (computed totals, rarely-used)
    skip_pools: frozenset[str] = frozenset({
        "TotalSection964AEPGrp",
        "Pre1987EPNotPrevTaxedGrp",
        "ReclassifiedSect965aPTEPGrp",
        "ReclassifiedSect965bPTEPGrp",
        "GeneralSection959c1PTEPGrp",
        "ReclassifiedSect951APTEPGrp",
        "ReclassifiedSect245AdPTEPGrp",
    })

    # Excel report branding
    client_name: str = ""
    engagement_name: str = ""

    # Logging
    log_level: str = "INFO"

    def __post_init__(self):
        self.tolerance = float(os.environ.get("PDF_VALIDATOR_TOLERANCE", str(self.tolerance)))
        self.log_level = os.environ.get("PDF_VALIDATOR_LOG_LEVEL", self.log_level)
        env_output = os.environ.get("PDF_VALIDATOR_OUTPUT_DIR")
        if env_output:
            self.output_dir = Path(env_output)
        self.output_dir.mkdir(parents=True, exist_ok=True)
