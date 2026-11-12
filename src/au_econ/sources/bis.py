"""Bank for International Settlements, via the BIS SDMX API.

Dataflows: policy rates (WS_CBPOL), property prices (WS_SPP), credit by sector (WS_TC),
debt service ratios (WS_DSR), consumer prices (WS_LONG_CPI).
One request covers every country ("+"-joined keys). The API sends no Last-Modified, so
responses are cached for RECENT_MAX_AGE by file age.
"""

import io
from typing import TYPE_CHECKING

import pandas as pd

from au_econ.sources.http_cache import RECENT_MAX_AGE, get_recent

if TYPE_CHECKING:
    from collections.abc import Iterable

POLICY_RATES_URL = "https://stats.bis.org/api/v2/data/dataflow/BIS/WS_CBPOL/1.0/{frequency}.{areas}"
TIMEOUT = 120  # seconds
COLUMNS = ["REF_AREA", "TIME_PERIOD", "OBS_VALUE"]
PROPERTY_PRICES_URL = "https://stats.bis.org/api/v2/data/dataflow/BIS/WS_SPP/1.0/Q.AU"  # Australia, quarterly
NOMINAL, INDEX_UNIT = "N", 628  # nominal; index (not year-on-year change)
# quarterly; real or nominal; index
PROPERTY_PRICE_INDEXES_URL = "https://stats.bis.org/api/v2/data/dataflow/BIS/WS_SPP/1.0/Q.{areas}.{value}.{unit}"
PRICE_VALUES = {"real": "R", "nominal": "N"}  # price basis label: BIS code
# quarterly; borrowing sector; from all sectors; valuation; per cent of GDP; adjusted for breaks
CREDIT_URL = "https://stats.bis.org/api/v2/data/dataflow/BIS/WS_TC/2.0/Q.{areas}.{borrower}.A.{valuation}.770.A"
BORROWERS = {  # borrowing sector label: BIS code
    "households": "H",  # households and NPISHs
    "non-financial corporations": "N",
    "general government": "G",
}
VALUATIONS = {"market": "M", "nominal": "N"}  # valuation label: BIS code
DEBT_SERVICE_URL = "https://stats.bis.org/api/v2/data/dataflow/BIS/WS_DSR/1.0/Q.{areas}.H"  # households and NPISHs
# monthly; index
CONSUMER_PRICES_URL = "https://stats.bis.org/api/v2/data/dataflow/BIS/WS_LONG_CPI/1.0/M.{areas}.628"


def get_policy_rates(frequency: str, areas: Iterable[str], start: str) -> pd.DataFrame:
    """Return policy rates (per cent), one row per country and period: REF_AREA, TIME_PERIOD, OBS_VALUE.

    frequency is "D" (daily) or "M" (monthly); areas are BIS two-letter codes ("XM" is the euro area).
    """
    url = POLICY_RATES_URL.format(frequency=frequency, areas="+".join(areas))
    content = get_recent(url, {"startPeriod": start, "format": "csv"}, "bis", RECENT_MAX_AGE, TIMEOUT)
    rows = pd.read_csv(io.BytesIO(content))
    if rows.empty:
        raise ValueError(f"BIS policy rates {frequency}: no data from {start}")
    return rows[COLUMNS]


def get_residential_property_prices() -> pd.Series:
    """Return the BIS nominal residential property price index for Australia, quarterly from 1970Q1.

    The BIS documents it as the ABS all-dwellings RPPI from 2003Q3, ABS established houses
    from 1986Q3, and REIA capital-city median prices before that: a median, so before 1986
    it moves with the mix of what sold as well as with prices.
    """
    content = get_recent(PROPERTY_PRICES_URL, {"format": "csv"}, "bis", RECENT_MAX_AGE, TIMEOUT)
    rows = pd.read_csv(io.BytesIO(content))
    wanted = rows[(rows["VALUE"] == NOMINAL) & (rows["UNIT_MEASURE"] == INDEX_UNIT)]
    if wanted.empty:
        raise ValueError("BIS: no nominal residential property price index for Australia")
    index = pd.PeriodIndex(wanted["TIME_PERIOD"].str.replace("-", ""), freq="Q-DEC")
    prices = pd.Series(wanted["OBS_VALUE"].to_numpy(dtype=float), index=index).sort_index()
    return prices.rename("BIS residential property prices")


def _quarterly_by_country(url: str, what: str, country: str = "BORROWERS_CTY") -> pd.DataFrame:
    """Return a quarterly BIS dataflow, one column per BIS country code; country names the country column."""
    content = get_recent(url, {"format": "csv"}, "bis", RECENT_MAX_AGE, TIMEOUT)
    rows = pd.read_csv(io.BytesIO(content))
    if rows.empty:
        raise ValueError(f"BIS {what}: no data for {url}")
    wide = rows.pivot_table(index="TIME_PERIOD", columns=country, values="OBS_VALUE")
    wide.index = pd.PeriodIndex(wide.index.str.replace("-", ""), freq="Q-DEC")
    wide.columns.name = None
    return wide.sort_index().astype(float)


def get_credit_to_gdp(borrower: str, valuation: str, areas: Iterable[str]) -> pd.DataFrame:
    """Return credit to a borrowing sector as a per cent of GDP, quarterly, one column per BIS country code.

    borrower is a BORROWERS label and valuation a VALUATIONS label. Credit from all sectors,
    adjusted for breaks: the BIS total credit measure.
    """
    url = CREDIT_URL.format(areas="+".join(areas), borrower=BORROWERS[borrower], valuation=VALUATIONS[valuation])
    return _quarterly_by_country(url, f"credit to {borrower}")


def get_household_debt_service_ratio(areas: Iterable[str]) -> pd.DataFrame:
    """Return the household debt service ratio (per cent of income), quarterly, one column per BIS country code.

    Interest and principal repayments by households and NPISHs as a share of their income.
    """
    return _quarterly_by_country(DEBT_SERVICE_URL.format(areas="+".join(areas)), "debt service ratio")


def get_consumer_prices(areas: Iterable[str], start: str) -> pd.DataFrame:
    """Return consumer price indexes, monthly from start (e.g. "2019-12"), one column per BIS country code.

    The BIS long series: national CPIs, original (not seasonally adjusted).
    """
    url = CONSUMER_PRICES_URL.format(areas="+".join(areas))
    content = get_recent(url, {"startPeriod": start, "format": "csv"}, "bis", RECENT_MAX_AGE, TIMEOUT)
    rows = pd.read_csv(io.BytesIO(content))
    if rows.empty:
        raise ValueError(f"BIS consumer prices: no data from {start}")
    wide = rows.pivot_table(index="TIME_PERIOD", columns="REF_AREA", values="OBS_VALUE")
    wide.index = pd.PeriodIndex(wide.index, freq="M")
    wide.columns.name = None
    return wide.sort_index().astype(float)


def get_property_price_indexes(value: str, areas: Iterable[str]) -> pd.DataFrame:
    """Return residential property price indexes, quarterly, one column per BIS country code.

    value is a PRICE_VALUES label: "real" (deflated by consumer prices) or "nominal".
    """
    url = PROPERTY_PRICE_INDEXES_URL.format(areas="+".join(areas), value=PRICE_VALUES[value], unit=INDEX_UNIT)
    return _quarterly_by_country(url, f"{value} property prices", country="REF_AREA")
