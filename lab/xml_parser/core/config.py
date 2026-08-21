"""Centralized configuration for Mythos.

Resolution order:
1. Explicit kwargs passed to MythosConfig()
2. Environment variables (MYTHOS_*)
3. mythos.toml in working directory
4. Defaults
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


def _project_root() -> Path:
    """Walk up from this file to find the Cerebro root."""
    p = Path(__file__).resolve()
    for parent in p.parents:
        if (parent / "CLAUDE.md").exists():
            return parent
    return Path.cwd()


@dataclass
class MythosConfig:
    sources_dir: Path = field(default_factory=lambda: _project_root() / "sources")
    output_dir: Path = field(default_factory=lambda: _project_root() / "lab" / "xml_parser" / "output")
    log_level: str = "INFO"
    excel_branding: bool = True
    balance_sheet_tolerance: float = 1.0
    rollover_materiality: float = 10_000.0
    etr_low: float = 0.0
    etr_high: float = 0.50
    firm_name: str = ""
    confidentiality_label: str = "Confidential"

    def __post_init__(self):
        self.sources_dir = Path(os.environ.get("MYTHOS_SOURCES_DIR", str(self.sources_dir)))
        self.output_dir = Path(os.environ.get("MYTHOS_OUTPUT_DIR", str(self.output_dir)))
        self.log_level = os.environ.get("MYTHOS_LOG_LEVEL", self.log_level)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def client_dir(self, client_slug: str) -> Path:
        """Return sources/{client_slug}/ path."""
        return self.sources_dir / client_slug

    def latest_xml(self, client_slug: str, pattern: str = "*.xml") -> Optional[Path]:
        """Find most recent XML file in a client's source directory."""
        client = self.client_dir(client_slug)
        if not client.exists():
            return None
        files = sorted(client.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        return files[0] if files else None


_default_config: Optional[MythosConfig] = None


def get_config() -> MythosConfig:
    """Get or create the singleton config instance."""
    global _default_config
    if _default_config is None:
        _default_config = MythosConfig()
    return _default_config


def reset_config(**overrides) -> MythosConfig:
    """Reset config with optional overrides. Useful for testing."""
    global _default_config
    _default_config = MythosConfig(**overrides)
    return _default_config
