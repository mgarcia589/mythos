"""IRS e-File XML Parser — Core parsing engine using lxml."""

from pathlib import Path
from typing import Optional

import pandas as pd
from lxml import etree

from lab.xml_parser.models import (
    FormData,
    ParsedReturn,
    ReturnHeader,
    SubsidiaryEntity,
    SubsidiaryReturn,
)

NS = {"irs": "http://www.irs.gov/efile"}


class EFileParser:
    """Parse IRS e-file XML returns into structured data."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"XML file not found: {self.path}")
        self._tree = etree.parse(str(self.path))
        self._root = self._tree.getroot()

    def parse(self) -> ParsedReturn:
        """Full extraction — parse entire return into structured objects."""
        result = ParsedReturn(source_path=self.path)
        result.header = self._parse_header()
        result.subsidiaries = self._parse_subsidiaries()
        return result

    def list_subsidiaries(self) -> list[dict]:
        """Quick scan — return entity summary without full form parsing."""
        entities = []
        for sub_elem in self._root.findall(".//irs:SubsidiaryReturn", NS):
            entity = self._extract_entity_info(sub_elem)
            entities.append({
                "name": entity.name,
                "ein": entity.ein,
                "reference_id": entity.reference_id,
                "country_code": entity.country_code,
                "functional_currency": entity.functional_currency,
                "dormant": entity.dormant,
            })
        return entities

    # Forms that can have multiple instances per entity (one per basket)
    MULTI_INSTANCE_FORMS = {"IRS5471ScheduleJ", "IRS5471ScheduleQ", "IRS5471ScheduleP"}

    # 8858 schedules that live inside the <IRS8858> element
    FORMS_8858 = {"IRS8858", "IRS8858ScheduleC", "IRS8858ScheduleF",
                  "IRS8858ScheduleG", "IRS8858ScheduleH"}

    def extract_form_8858(self, form_name: str) -> pd.DataFrame:
        """Extract a Form 8858 schedule across all subsidiaries.

        Handles the structural difference: 8858 schedules are nested INSIDE
        the <IRS8858> element (not siblings like 5471 schedules).
        Schedule M is a sibling — use extract_form("IRS8858ScheduleM") for that.
        """
        records = []
        is_main = (form_name == "IRS8858")

        for sub_elem in self._root.findall(".//irs:SubsidiaryReturn", NS):
            ret_data = sub_elem.find("irs:ReturnData", NS)
            if ret_data is None:
                continue

            for irs8858 in ret_data.findall("irs:IRS8858", NS):
                entity = self._extract_8858_entity_info(irs8858)

                if is_main:
                    target_elem = irs8858
                else:
                    target_elem = irs8858.find(f"irs:{form_name}", NS)
                    if target_elem is None:
                        continue

                record = {
                    "_entity_name": entity.name,
                    "_country_code": entity.country_code,
                    "_functional_currency": entity.functional_currency,
                    "_reference_id": entity.reference_id,
                    "_tax_owner": entity.tax_owner_name,
                    "_tax_owner_ref_id": entity.tax_owner_ref_id,
                    "_dormant": entity.dormant,
                    "_document_id": irs8858.get("documentId", ""),
                }

                self._flatten_element(target_elem, form_name, record)
                records.append(record)

        return pd.DataFrame(records)

    def detect_forms(self) -> set[str]:
        """Detect which form types are present in this return.

        Returns a set of form type strings: {"5471", "8858"}.
        Scans ReturnData for IRS5471 and IRS8858 elements.
        """
        forms = set()
        for sub_elem in self._root.findall(".//irs:SubsidiaryReturn", NS):
            ret_data = sub_elem.find("irs:ReturnData", NS)
            if ret_data is None:
                continue
            if ret_data.find("irs:IRS5471", NS) is not None:
                forms.add("5471")
            if ret_data.find("irs:IRS8858", NS) is not None:
                forms.add("8858")
            if len(forms) == 2:
                break
        return forms

    def list_8858_entities(self) -> list[dict]:
        """Quick scan of all Form 8858 FDE/FB entities."""
        entities = []
        for sub_elem in self._root.findall(".//irs:SubsidiaryReturn", NS):
            ret_data = sub_elem.find("irs:ReturnData", NS)
            if ret_data is None:
                continue
            for irs8858 in ret_data.findall("irs:IRS8858", NS):
                entity = self._extract_8858_entity_info(irs8858)
                entities.append({
                    "name": entity.name,
                    "ein": entity.ein,
                    "reference_id": entity.reference_id,
                    "country_code": entity.country_code,
                    "functional_currency": entity.functional_currency,
                    "tax_owner": entity.tax_owner_name,
                    "tax_owner_ref_id": entity.tax_owner_ref_id,
                    "dormant": entity.dormant,
                    "category": "FDE" if entity.is_fde_us_person else "FB",
                })
        return entities

    def extract_form(self, form_name: str) -> pd.DataFrame:
        """Extract a specific form across all subsidiaries into a DataFrame.

        For multi-instance forms (Schedule J, Q, P) that appear once per
        basket (GEN/PAS/TOTAL), each instance becomes its own row.
        """
        records = []
        multi = form_name in self.MULTI_INSTANCE_FORMS

        for sub_elem in self._root.findall(".//irs:SubsidiaryReturn", NS):
            entity = self._extract_entity_info(sub_elem)
            ret_data = sub_elem.find("irs:ReturnData", NS)
            if ret_data is None:
                continue

            if multi:
                form_elems = ret_data.findall(f"irs:{form_name}", NS)
            else:
                found = ret_data.find(f"irs:{form_name}", NS)
                form_elems = [found] if found is not None else []

            for form_elem in form_elems:
                record = {
                    "_entity_name": entity.name,
                    "_country_code": entity.country_code,
                    "_functional_currency": entity.functional_currency,
                    "_reference_id": entity.reference_id,
                    "_document_id": form_elem.get("documentId", ""),
                }

                self._flatten_element(form_elem, form_name, record)

                if multi:
                    sep_key = f"{form_name}_SeparateCategoryCd"
                    record["_basket"] = record.get(sep_key, "")

                records.append(record)

        return pd.DataFrame(records)

    def get_field(self, entity_name: str, xpath: str) -> Optional[str]:
        """Get a single field value for a specific entity."""
        for sub_elem in self._root.findall(".//irs:SubsidiaryReturn", NS):
            name_elem = sub_elem.find(
                ".//irs:SubsidiaryCorpGrp/irs:BusinessName/irs:BusinessNameLine1Txt", NS
            )
            if name_elem is None or entity_name.lower() not in (name_elem.text or "").lower():
                continue
            result = sub_elem.find(xpath, NS)
            return result.text if result is not None else None
        return None

    def extract_top_level_form(self, form_name: str) -> pd.DataFrame:
        """Extract a form from top-level ReturnData (parent/consolidated return).

        Unlike extract_form() which searches inside SubsidiaryReturn elements,
        this searches for forms at the top-level ReturnData — used for forms
        like IRS8990, IRS1120, etc. that exist once per return (not per entity).

        Returns a single-row DataFrame with all flattened fields, or empty DataFrame.
        """
        # Search patterns: Return/ReturnData/form, Return/ParentReturn/ReturnData/form
        search_paths = [
            f".//irs:ReturnData/irs:{form_name}",
            f".//irs:ParentReturn/irs:ReturnData/irs:{form_name}",
            f"irs:ReturnData/irs:{form_name}",
        ]

        for xpath in search_paths:
            form_elem = self._root.find(xpath, NS)
            if form_elem is not None:
                record = {"_document_id": form_elem.get("documentId", "")}
                self._flatten_element(form_elem, form_name, record)
                return pd.DataFrame([record])

        return pd.DataFrame()

    def to_dataframe(self, forms: Optional[list[str]] = None) -> pd.DataFrame:
        """Parse all forms into a single wide DataFrame (Alteryx-compatible output).

        Multi-instance forms (Schedule J/Q/P) are handled specially: if the
        requested forms include ONLY multi-instance forms, each instance gets
        its own row (with _basket column). Otherwise, only the first instance
        per entity is included to preserve the one-row-per-entity layout.
        """
        if forms is None:
            forms = ["IRS5471", "IRS5471ScheduleH", "IRS5471ScheduleI1",
                     "IRS5471ScheduleE", "IRS5471ScheduleJ", "IRS5471ScheduleQ"]

        # If ALL requested forms are multi-instance, use extract_form for full coverage
        all_multi = all(f in self.MULTI_INSTANCE_FORMS for f in forms)
        if all_multi and len(forms) == 1:
            return self.extract_form(forms[0])

        all_records = []
        for sub_elem in self._root.findall(".//irs:SubsidiaryReturn", NS):
            entity = self._extract_entity_info(sub_elem)
            ret_data = sub_elem.find("irs:ReturnData", NS)
            if ret_data is None:
                continue

            if all_multi:
                # Multiple multi-instance forms: expand by basket
                baskets_data = {}  # basket -> merged record
                for form_name in forms:
                    for form_elem in ret_data.findall(f"irs:{form_name}", NS):
                        fields = {}
                        self._flatten_element(form_elem, form_name, fields)
                        sep_key = f"{form_name}_SeparateCategoryCd"
                        basket = fields.get(sep_key, "")
                        if basket not in baskets_data:
                            baskets_data[basket] = {
                                "_entity_name": entity.name,
                                "_ein": entity.ein,
                                "_reference_id": entity.reference_id,
                                "_country_code": entity.country_code,
                                "_functional_currency": entity.functional_currency,
                                "_voting_stock_pct": entity.voting_stock_pct,
                                "_dormant": entity.dormant,
                                "_basket": basket,
                            }
                        baskets_data[basket].update(fields)
                all_records.extend(baskets_data.values())
            else:
                # Mixed forms: one row per entity, first instance of multi-instance
                record = {
                    "_entity_name": entity.name,
                    "_ein": entity.ein,
                    "_reference_id": entity.reference_id,
                    "_country_code": entity.country_code,
                    "_functional_currency": entity.functional_currency,
                    "_voting_stock_pct": entity.voting_stock_pct,
                    "_dormant": entity.dormant,
                }

                for form_name in forms:
                    form_elem = ret_data.find(f"irs:{form_name}", NS)
                    if form_elem is not None:
                        self._flatten_element(form_elem, form_name, record)

                all_records.append(record)

        return pd.DataFrame(all_records)

    def _parse_header(self) -> ReturnHeader:
        header_elem = self._root.find("irs:ReturnHeader", NS)
        if header_elem is None:
            return ReturnHeader()

        return ReturnHeader(
            filer_ein=self._text(header_elem, ".//irs:Filer/irs:EIN"),
            filer_name=self._text(header_elem, ".//irs:Filer/irs:BusinessName/irs:BusinessNameLine1Txt"),
            return_type=self._text(header_elem, "irs:ReturnTypeCd"),
            tax_year=self._text(header_elem, "irs:TaxYr"),
            tax_period_begin=self._text(header_elem, "irs:TaxPeriodBeginDt"),
            tax_period_end=self._text(header_elem, ".//irs:TaxPeriodEndDt"),
            software_id=self._text(header_elem, "irs:SoftwareId"),
            software_version=self._text(header_elem, "irs:SoftwareVersionNum"),
            subsidiary_count=int(header_elem.get("subsidiaryReturnCount", "0")),
            return_timestamp=self._text(header_elem, "irs:ReturnTs"),
        )

    def _parse_subsidiaries(self) -> list[SubsidiaryReturn]:
        subs = []
        for sub_elem in self._root.findall(".//irs:SubsidiaryReturn", NS):
            entity = self._extract_entity_info(sub_elem)
            sub_return = SubsidiaryReturn(
                entity=entity,
                tax_period_begin=self._text(sub_elem, ".//irs:ReturnHeader/irs:TaxPeriodBeginDt"),
                tax_period_end=self._text(sub_elem, ".//irs:ReturnHeader/irs:TaxPeriodEndDt"),
            )

            ret_data = sub_elem.find("irs:ReturnData", NS)
            if ret_data is not None:
                for child in ret_data:
                    if not isinstance(child.tag, str):
                        continue
                    tag = etree.QName(child).localname
                    fields = {}
                    self._flatten_element(child, tag, fields)

                    # Multi-instance forms: store with basket suffix
                    if tag in self.MULTI_INSTANCE_FORMS:
                        sep_key = f"{tag}_SeparateCategoryCd"
                        basket = fields.get(sep_key, "")
                        if basket:
                            form_key = f"{tag}_{basket}"
                        else:
                            form_key = tag
                    else:
                        form_key = tag

                    sub_return.forms[form_key] = FormData(
                        form_name=tag,
                        document_id=child.get("documentId", ""),
                        fields=fields,
                    )

            subs.append(sub_return)
        return subs

    def _extract_entity_info(self, sub_elem) -> SubsidiaryEntity:
        entity = SubsidiaryEntity()

        # From SubsidiaryCorpGrp in header
        name_elem = sub_elem.find(
            ".//irs:ReturnHeader//irs:SubsidiaryCorpGrp/irs:BusinessName/irs:BusinessNameLine1Txt", NS
        )
        entity.name = name_elem.text if name_elem is not None else ""

        addr = sub_elem.find(".//irs:ReturnHeader//irs:SubsidiaryCorpGrp/irs:ForeignAddress", NS)
        if addr is not None:
            entity.address_line1 = self._text(addr, "irs:AddressLine1Txt")
            entity.city = self._text(addr, "irs:CityNm")
            entity.province = self._text(addr, "irs:ProvinceOrStateNm")
            entity.country_code = self._text(addr, "irs:CountryCd")
            entity.postal_code = self._text(addr, "irs:ForeignPostalCd")

        # From IRS5471 main form (if present)
        irs5471 = sub_elem.find(".//irs:ReturnData/irs:IRS5471", NS)
        if irs5471 is not None:
            entity.ein = self._text(irs5471, "irs:EIN") or self._text(irs5471, "irs:EmployerEIN")
            entity.reference_id = self._text(
                irs5471, ".//irs:ForeignEntityIdentificationGrp/irs:ForeignEntityReferenceIdNum"
            )
            entity.country_code = entity.country_code or self._text(irs5471, "irs:CountryUnderWhoseLawsIncCd")
            entity.functional_currency = self._text(irs5471, "irs:FunctionalCurrencyCd")
            entity.incorporation_date = self._text(irs5471, "irs:IncorporationDt")
            entity.voting_stock_pct = self._text(irs5471, "irs:VotingStockOwnedPct")
            entity.dormant = self._text(irs5471, "irs:dormantForeignCorporationCd") == "Y"

            # Category filers
            for cat in ["1a", "1b", "1c", "2", "3", "4", "5a", "5b", "5c"]:
                cat_elem = irs5471.find(f"irs:CategoryOfFiler{cat.replace('a','1a').replace('b','1b')}Ind", NS)
                if cat_elem is None:
                    cat_elem = irs5471.find(f"irs:CategoryOfFiler{cat[0]}Ind", NS)
                if cat_elem is not None and cat_elem.text == "X":
                    entity.category_filers.append(cat)

        return entity

    def _extract_8858_entity_info(self, irs8858_elem) -> SubsidiaryEntity:
        """Extract entity identification from an IRS8858 element."""
        entity = SubsidiaryEntity()

        entity.name = self._text(irs8858_elem, "irs:FDEOrFBName/irs:BusinessNameLine1Txt")
        entity.ein = self._text(irs8858_elem, "irs:FDEOrFBUSIdNumberDetail/irs:EIN")
        entity.reference_id = self._text(
            irs8858_elem, "irs:ForeignEntityIdentificationGrp/irs:ForeignEntityReferenceIdNum"
        )
        entity.functional_currency = self._text(irs8858_elem, "irs:FunctionalCurrencyCd")

        # Country from organization details
        entity.country_code = self._text(
            irs8858_elem, "irs:CountryEntityOrgDetail/irs:CntryUnderWhoseLawsOrganizedCd"
        )

        # Address
        addr = irs8858_elem.find("irs:FDEOrFBForeignAddress", NS)
        if addr is not None:
            entity.address_line1 = self._text(addr, "irs:AddressLine1Txt")
            entity.city = self._text(addr, "irs:CityNm")
            entity.province = self._text(addr, "irs:ProvinceOrStateNm")
            entity.country_code = entity.country_code or self._text(addr, "irs:CountryCd")
            entity.postal_code = self._text(addr, "irs:ForeignPostalCd")

        # Tax owner
        entity.tax_owner_name = self._text(irs8858_elem, "irs:TaxOwnerName/irs:BusinessNameLine1Txt")
        entity.tax_owner_ref_id = self._text(
            irs8858_elem, "irs:TaxOwnerEntityIdGrp/irs:ForeignEntityReferenceIdNum"
        )
        entity.tax_owner_ein = self._text(irs8858_elem, "irs:TaxOwnerUSIdNumberDetail/irs:EIN")
        entity.tax_owner_country = self._text(irs8858_elem, "irs:TxOwnerCntryLawsOrganizedCd")

        # Category indicators
        fde_ind = self._text(irs8858_elem, "irs:FDEUSPersonInd")
        fb_ind = self._text(irs8858_elem, "irs:FBCFCInd")
        entity.is_fde_us_person = fde_ind == "X"
        entity.is_fb_cfc = fb_ind == "X"

        # Dormant indicator (attribute on element)
        entity.dormant = irs8858_elem.get("summaryDormantFDECd", "") in ("1", "Y", "true")

        return entity

    def _flatten_element(self, elem, prefix: str, record: dict, max_depth: int = 15):
        """Recursively flatten XML element into prefix_path → value dict."""
        if max_depth <= 0:
            return

        for child in elem:
            if not isinstance(child.tag, str):
                continue
            tag = etree.QName(child).localname
            child_prefix = f"{prefix}_{tag}"

            # Store attributes
            for attr_name, attr_val in child.attrib.items():
                if attr_name not in ("xmlns", "xsi"):
                    record[f"{child_prefix}_{attr_name}"] = attr_val

            if len(child) == 0:
                # Leaf node
                record[child_prefix] = child.text or ""
            else:
                # Recurse into children
                self._flatten_element(child, child_prefix, record, max_depth - 1)

    def _text(self, elem, xpath: str) -> str:
        """Safely extract text from XPath result."""
        result = elem.find(xpath, NS)
        return result.text if result is not None and result.text else ""
