"""Banque de France: Webstat series observations by series key, through its API, as CSV.

The API needs a key (KEYS/webstat.api), sent in a header so it never reaches a cache
file name. It sends no Last-Modified, so downloads are cached for RECENT_MAX_AGE, and a
failed download falls back to the cached copy. Daily series carry every calendar day,
with weekends and holidays left empty.
"""

import io
from functools import cache

import pandas as pd

from au_econ import paths
from au_econ.sources.http_cache import RECENT_MAX_AGE, get_recent

OBSERVATIONS_URL = "https://webstat.banque-france.fr/api/explore/v2.1/catalog/datasets/observations/exports/csv"
KEY_FILE = paths.KEYS_DIR / "webstat.api"


@cache
def _api_key() -> str:
    """Read the API key once per run."""
    return KEY_FILE.read_text().strip()


def get_series(series_key: str) -> pd.Series:
    """Return a daily Webstat series (e.g. a French government bond yield) with a daily PeriodIndex."""
    params = {
        "delimiter": ",",
        "select": "time_period,obs_value",
        "where": f'series_key="{series_key}"',
        "order_by": "time_period",
    }
    content = get_recent(
        OBSERVATIONS_URL,
        params,
        "banque-de-france",
        RECENT_MAX_AGE,
        headers={"Authorization": f"Apikey {_api_key()}"},
        fallback=True,
    )
    frame = pd.read_csv(io.BytesIO(content), encoding="utf-8-sig")
    series = pd.Series(
        pd.to_numeric(frame["obs_value"], errors="coerce").to_numpy(),
        index=pd.PeriodIndex(frame["time_period"], freq="D"),
        name=series_key,
    ).dropna()
    if series.empty:
        raise ValueError(f"Banque de France returned no observations for {series_key}")
    return series
