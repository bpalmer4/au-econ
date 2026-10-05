"""Bank for International Settlements, via the BIS SDMX API: policy rates (WS_CBPOL), property prices (WS_SPP).

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
