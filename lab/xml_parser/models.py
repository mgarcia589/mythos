"""Data models for parsed IRS e-file returns."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ReturnHeader:
    filer_ein: str = ""
    filer_name: str = ""
    return_type: str = ""
    tax_year: str = ""
    tax_period_begin: str = ""
    tax_period_end: str = ""
    software_id: str = ""
    software_version: str = ""
    subsidiary_count: int = 0
    return_timestamp: str = ""


@dataclass
class SubsidiaryEntity:
    name: str = ""
    ein: str = ""
    reference_id: str = ""
    country_code: str = ""
    functional_currency: str = ""
    incorporation_date: str = ""
    address_line1: str = ""
    city: str = ""
    province: str = ""
    postal_code: str = ""
    category_filers: list = field(default_factory=list)
    voting_stock_pct: str = ""
    dormant: bool = False


@dataclass
class FormData:
    form_name: str
    document_id: str = ""
    fields: dict = field(default_factory=dict)


@dataclass
class SubsidiaryReturn:
    entity: SubsidiaryEntity
    forms: dict = field(default_factory=dict)  # form_name → FormData
    tax_period_begin: str = ""
    tax_period_end: str = ""


@dataclass
class ParsedReturn:
    source_path: Path = field(default_factory=Path)
    header: ReturnHeader = field(default_factory=ReturnHeader)
    subsidiaries: list = field(default_factory=list)  # list[SubsidiaryReturn]

    @property
    def entity_count(self) -> int:
        return len(self.subsidiaries)

    def get_entity(self, name: str) -> Optional[SubsidiaryReturn]:
        for sub in self.subsidiaries:
            if name.lower() in sub.entity.name.lower():
                return sub
        return None

    def get_entity_by_ein(self, ein: str) -> Optional[SubsidiaryReturn]:
        for sub in self.subsidiaries:
            if sub.entity.ein == ein:
                return sub
        return None

    def get_entity_by_ref(self, ref_id: str) -> Optional[SubsidiaryReturn]:
        for sub in self.subsidiaries:
            if sub.entity.reference_id == ref_id:
                return sub
        return None
