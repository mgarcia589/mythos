"""FX rate management and currency conversion."""

from dataclasses import dataclass


@dataclass
class FXRate:
    currency: str
    spot_rate: float  # FC per 1 USD (spot at year-end)
    avg_rate: float   # FC per 1 USD (annual average)


# Sample FX rates for testing (IRS published annual averages, publicly available)
SAMPLE_RATES = {
    "USD": FXRate("USD", 1.0, 1.0),
    "GBP": FXRate("GBP", 0.75, 0.76),
    "EUR": FXRate("EUR", 0.85, 0.89),
    "SGD": FXRate("SGD", 1.34, 1.31),
    "AUD": FXRate("AUD", 1.60, 1.53),
    "BMD": FXRate("BMD", 1.0, 1.0),
}


class FXRateManager:
    """Manage FX rates and perform conversions."""

    def __init__(self, rates: dict[str, FXRate] | None = None):
        self._rates = rates or SAMPLE_RATES.copy()

    def get_avg_rate(self, currency: str) -> float:
        """Get average annual rate (FC per 1 USD). Used for E&P translation."""
        rate = self._rates.get(currency)
        if not rate:
            raise ValueError(f"No FX rate for {currency}")
        return rate.avg_rate

    def get_spot_rate(self, currency: str) -> float:
        """Get spot rate at year-end. Used for balance sheet."""
        rate = self._rates.get(currency)
        if not rate:
            raise ValueError(f"No FX rate for {currency}")
        return rate.spot_rate

    def fc_to_usd(self, amount_fc: float, currency: str, use_avg: bool = True) -> float:
        """Convert functional currency amount to USD.

        For E&P: divide FC amount by avg rate (FC/USD).
        The workbook formula is: E&P_USD = E&P_FC / avg_rate
        """
        if currency == "USD":
            return amount_fc
        rate = self.get_avg_rate(currency) if use_avg else self.get_spot_rate(currency)
        return amount_fc / rate

    def usd_to_fc(self, amount_usd: float, currency: str, use_avg: bool = True) -> float:
        """Convert USD to functional currency."""
        if currency == "USD":
            return amount_usd
        rate = self.get_avg_rate(currency) if use_avg else self.get_spot_rate(currency)
        return amount_usd * rate

    def load_from_workbook(self, xlsx_reader, sheet_name: str = "FX Rates"):
        """Load rates from the workbook's FX Rates sheet."""
        # Will be refined once workbook is re-ingested
        pass
