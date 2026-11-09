"""International Monetary Fund: the World Economic Outlook, via the DataMapper API.

One request returns an indicator for every country and IMF aggregate. Years past each
country's latest actual are IMF estimates and projections. The API sends no Last-Modified,
so responses are cached for RECENT_MAX_AGE by file age.
"""

import json

import pandas as pd

from au_econ.sources.http_cache import RECENT_MAX_AGE, get_recent

DATAMAPPER_URL = "https://www.imf.org/external/datamapper/api/v1/{indicator}"
TIMEOUT = 60  # seconds


def get_weo(indicator: str) -> pd.DataFrame:
    """Return a WEO indicator, annual, one column per IMF code (ISO3 for countries, e.g. "AUS").

    indicator is a DataMapper code, e.g. "LP" for population (millions).
    """
    content = get_recent(DATAMAPPER_URL.format(indicator=indicator), None, "imf", RECENT_MAX_AGE, TIMEOUT)
    values = json.loads(content).get("values", {}).get(indicator, {})
    if not values:
        raise ValueError(f"IMF WEO {indicator}: no data")
    frame = pd.DataFrame({code: pd.Series(years, dtype=float) for code, years in values.items()})
    frame.index = pd.PeriodIndex(frame.index.astype(int), freq="Y")
    return frame.sort_index()
