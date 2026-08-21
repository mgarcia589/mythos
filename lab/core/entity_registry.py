"""Entity registry — lookup entity metadata by code."""

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


@dataclass
class Entity:
    code: str
    name: str
    fc: str
    country: str
    deal: str
    entity_type: str = "Subsidiary"
    is_insurance: bool = False
    is_dormant: bool = False
    is_dre: bool = False
    fx_rate: float = 1.0
    ein_ref: str = ""


# Sample entity data for testing and demo purposes
SAMPLE_ENTITIES = [
    Entity("E001", "Alpha TopCo Ltd", "USD", "JE", "Portfolio-A"),
    Entity("E002", "Alpha MidCo Limited", "USD", "JE", "Portfolio-A"),
    Entity("E003", "Alpha Holdings Limited", "USD", "JE", "Portfolio-A"),
    Entity("E004", "Alpha Group Limited", "USD", "JE", "Portfolio-A"),
    Entity("E005", "Alpha Underwriting Bermuda Limited", "USD", "BD", "Portfolio-A"),
    Entity("E006", "Alpha Reinsurance Limited", "USD", "BD", "Portfolio-A", is_insurance=True),
    Entity("E007", "Beta Holdings Limited", "GBP", "UK", "Portfolio-A"),
    Entity("E008", "Beta Agents Limited", "USD", "UK", "Portfolio-A"),
    Entity("E009", "Alpha Germany GmbH", "EUR", "DE", "Portfolio-A"),
    Entity("E010", "Beta Dedicated Limited", "GBP", "UK", "Portfolio-A"),
    Entity("E011", "Gamma Digital Services Ltd", "USD", "UK", "Portfolio-A"),
    Entity("E012", "Delta Underwriting Limited", "GBP", "UK", "Portfolio-A"),
    Entity("E013", "Alpha Managing Agents Limited", "GBP", "UK", "Portfolio-A"),
    Entity("E014", "Alpha Services Limited", "GBP", "UK", "Portfolio-A"),
    Entity("E015", "Alpha Europe Limited", "GBP", "UK", "Portfolio-A"),
    Entity("E016", "Alpha Europe Limited (Zurich)", "USD", "SZ", "Portfolio-A", is_dre=True),
    Entity("E017", "Sigma Holdings Limited", "GBP", "UK", "Portfolio-A", is_dormant=True),
    Entity("E018", "Kappa Holdings Limited", "GBP", "UK", "Portfolio-A"),
    Entity("E019", "Alpha Holdings UK Limited", "GBP", "UK", "Portfolio-A"),
    Entity("E020", "Alpha Capital Four Limited", "USD", "UK", "Portfolio-A", is_insurance=True),
    Entity("E021", "Alpha Capital Seven Limited", "USD", "UK", "Portfolio-A", is_insurance=True),
    Entity("E022", "Alpha Capital Nine Limited", "USD", "UK", "Portfolio-A", is_insurance=True),
    Entity("E023", "Alpha Capital Ten Limited", "USD", "UK", "Portfolio-A", is_insurance=True),
    Entity("E024", "Alpha Capital Twelve Limited", "USD", "UK", "Portfolio-A", is_insurance=True),
    Entity("E025", "Alpha Capital Sixteen Limited", "GBP", "UK", "Portfolio-A", is_dormant=True),
    Entity("E026", "Alpha Corporate Capital Ltd", "USD", "UK", "Portfolio-A", is_insurance=True),
    Entity("E027", "Pebbles Bermuda Limited", "USD", "BD", "Portfolio-A"),
    Entity("E028", "Delta UK Holdings Limited", "GBP", "UK", "Portfolio-A", is_dormant=True),
    Entity("E029", "Delta UK Limited", "GBP", "UK", "Portfolio-A", is_dormant=True),
    Entity("E030", "Alpha Ireland Limited", "EUR", "IE", "Portfolio-A"),
    Entity("E031", "Alpha Asia PTE Limited", "SGD", "SG", "Portfolio-A"),
    Entity("E032", "Alpha Labuan PTE Limited", "USD", "MY", "Portfolio-A"),
    Entity("E033", "Alpha ILS Limited", "USD", "BD", "Portfolio-A"),
    Entity("E034", "Zeta Insurance Limited", "GBP", "UK", "Portfolio-A", is_insurance=True),
    Entity("E035", "Alpha Asia PTE Limited (Australia branch)", "AUD", "AU", "Portfolio-A", is_dre=True),
    Entity("E036", "Gamma Holdings Ltd", "USD", "JE", "Portfolio-A"),
]


class EntityRegistry:
    """Entity lookup service."""

    def __init__(self, entities: Optional[list[Entity]] = None):
        self._entities: dict[str, Entity] = {}
        if entities:
            for e in entities:
                self._entities[e.code] = e

    def match_by_ref_id(self, ref_id: str) -> Optional[Entity]:
        """Lookup entity by EIN reference (ein_ref field)."""
        if not ref_id:
            return None
        for e in self._entities.values():
            if e.ein_ref and e.ein_ref == ref_id:
                return e
        return None

    def match_by_name(self, name: str) -> Optional[Entity]:
        """Lookup entity by name (case-insensitive substring match)."""
        if not name:
            return None
        name_lower = name.lower().strip()
        for e in self._entities.values():
            if e.name.lower().strip() == name_lower:
                return e
        # Fallback: substring containment
        for e in self._entities.values():
            if e.name.lower().strip() in name_lower or name_lower in e.name.lower().strip():
                return e
        return None

    @classmethod
    def sample(cls) -> "EntityRegistry":
        """Create registry pre-loaded with sample entities for testing/demo."""
        return cls(SAMPLE_ENTITIES)

    def get(self, code: str) -> Optional[Entity]:
        return self._entities.get(code)

    def __getitem__(self, code: str) -> Entity:
        if code not in self._entities:
            raise KeyError(f"Entity {code} not found in registry")
        return self._entities[code]

    def __contains__(self, code: str) -> bool:
        return code in self._entities

    @property
    def all_codes(self) -> list[str]:
        return list(self._entities.keys())

    @property
    def insurance_codes(self) -> list[str]:
        return [c for c, e in self._entities.items() if e.is_insurance]

    @property
    def non_insurance_codes(self) -> list[str]:
        return [c for c, e in self._entities.items() if not e.is_insurance and not e.is_dre]

    @property
    def dre_codes(self) -> list[str]:
        return [c for c, e in self._entities.items() if e.is_dre]

    def by_deal(self, deal: str) -> list[Entity]:
        return [e for e in self._entities.values() if e.deal == deal]

    def by_country(self, country: str) -> list[Entity]:
        return [e for e in self._entities.values() if e.country == country]

    def by_currency(self, fc: str) -> list[Entity]:
        return [e for e in self._entities.values() if e.fc == fc]

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([vars(e) for e in self._entities.values()])

    def load_from_workbook(self, xlsx_reader, sheet_name: str = "Entity Listing"):
        """Load entities from workbook's Entity Listing sheet."""
        rows_data, _ = xlsx_reader.read_sheet(sheet_name)
        # Implementation depends on exact sheet structure
        # Will be refined once workbook is re-ingested
        pass
