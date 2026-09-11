"""Entity Registry — O(1) lookup store, auto-populated from parsed XML.

Replaces the old linear-scan registry with triple-indexed maps.
Can also be populated manually or from workbooks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

import pandas as pd

if TYPE_CHECKING:
    from lab.xml_parser.parser import EFileParser


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
    form_type: str = "5471"


class EntityRegistry:
    """Entity lookup service with O(1) indexed access.

    Three indexes maintained on every mutation:
      _by_ref:  reference_id / ein_ref → Entity
      _by_name: normalized name        → Entity
      _by_code: code                   → Entity
    """

    def __init__(self, entities: Optional[list[Entity]] = None):
        self._by_ref: dict[str, Entity] = {}
        self._by_name: dict[str, Entity] = {}
        self._by_code: dict[str, Entity] = {}
        if entities:
            for e in entities:
                self._register(e)

    @property
    def count(self) -> int:
        return len(self._by_code)

    def _register(self, entity: Entity) -> None:
        ref_key = entity.ein_ref or entity.code
        if ref_key:
            self._by_ref[ref_key] = entity
        if entity.name:
            self._by_name[entity.name.lower().strip()] = entity
        self._by_code[entity.code] = entity

    def register(self, entity: Entity) -> None:
        self._register(entity)

    def populate_from_parser(self, parser: EFileParser) -> int:
        """Auto-populate registry from parsed XML subsidiaries.

        Extracts identity from each SubsidiaryReturn and indexes it.
        Returns count of entities registered.
        """
        parsed = parser.parse()
        for sub in parsed.subsidiaries:
            ent = sub.entity
            ref_id = ent.reference_id
            if not ref_id:
                continue

            forms = list(sub.forms.keys())
            has_8858 = any("8858" in f for f in forms)
            has_5471 = any("5471" in f for f in forms)

            form_type = "5471"
            if has_8858 and not has_5471:
                form_type = "8858"
            elif has_8858 and has_5471:
                form_type = "5471"

            entity = Entity(
                code=ref_id,
                name=ent.name,
                fc=ent.functional_currency,
                country=ent.country_code,
                deal="",
                entity_type="FDE" if form_type == "8858" else "Subsidiary",
                is_dormant=ent.dormant,
                ein_ref=ref_id,
                form_type=form_type,
            )
            self._register(entity)
        return self.count

    def match_by_ref_id(self, ref_id: str) -> Optional[Entity]:
        if not ref_id:
            return None
        return self._by_ref.get(ref_id)

    def match_by_name(self, name: str) -> Optional[Entity]:
        if not name:
            return None
        key = name.lower().strip()
        hit = self._by_name.get(key)
        if hit:
            return hit
        for stored_name, entity in self._by_name.items():
            if stored_name in key or key in stored_name:
                return entity
        return None

    def get(self, code: str) -> Optional[Entity]:
        return self._by_code.get(code)

    def __getitem__(self, code: str) -> Entity:
        if code not in self._by_code:
            raise KeyError(f"Entity {code} not found in registry")
        return self._by_code[code]

    def __contains__(self, code: str) -> bool:
        return code in self._by_code

    def __len__(self) -> int:
        return len(self._by_code)

    @property
    def all_codes(self) -> list[str]:
        return list(self._by_code.keys())

    @property
    def insurance_codes(self) -> list[str]:
        return [c for c, e in self._by_code.items() if e.is_insurance]

    @property
    def non_insurance_codes(self) -> list[str]:
        return [c for c, e in self._by_code.items() if not e.is_insurance and not e.is_dre]

    @property
    def dre_codes(self) -> list[str]:
        return [c for c, e in self._by_code.items() if e.is_dre]

    def by_deal(self, deal: str) -> list[Entity]:
        return [e for e in self._by_code.values() if e.deal == deal]

    def by_country(self, country: str) -> list[Entity]:
        return [e for e in self._by_code.values() if e.country == country]

    def by_currency(self, fc: str) -> list[Entity]:
        return [e for e in self._by_code.values() if e.fc == fc]

    def by_form_type(self, form_type: str) -> list[Entity]:
        return [e for e in self._by_code.values() if e.form_type == form_type]

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([vars(e) for e in self._by_code.values()])

    def clear(self) -> None:
        self._by_ref.clear()
        self._by_name.clear()
        self._by_code.clear()

    @classmethod
    def sample(cls) -> "EntityRegistry":
        """Create registry pre-loaded with sample entities for testing/demo."""
        return cls(_SAMPLE_ENTITIES)


_SAMPLE_ENTITIES = [
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
