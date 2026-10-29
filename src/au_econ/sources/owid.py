"""Our World in Data: its catalogue copy of the Energy Institute Statistical Review of World Energy.

The Energy Institute's own site refuses scripted downloads, so the Review's data are read
from OWID's ETL catalogue, which republishes the full country-year table (oil, gas, coal
and so on, in physical and energy units). The catalogue path carries the dataset's
version date, which changes with each annual Review (released about June): update
EI_VERSION then. The file is downloaded through http_cache.
"""

import io

import pandas as pd

from au_econ.sources.http_cache import get_file

PREFIX = "owid"
EI_VERSION = "2026-06-30"  # the 2026 Review, data to 2025
EI_URL = (
    "https://catalog.ourworldindata.org/garden/energy_institute/"
    f"{EI_VERSION}/statistical_review_of_world_energy/statistical_review_of_world_energy.feather"
)
TIMEOUT = 60  # seconds


def get_statistical_review(country: str, column: str) -> pd.Series:
    """Return one Statistical Review column for one country, on an annual PeriodIndex."""
    content = get_file(EI_URL, prefix=PREFIX, timeout=TIMEOUT, fallback=True)
    frame = pd.read_feather(io.BytesIO(content))
    if column not in frame.columns:
        raise ValueError(f"OWID Statistical Review: no column {column!r}")
    rows = frame[frame["country"] == country]
    series = pd.Series(
        rows[column].to_numpy(dtype=float),
        index=pd.PeriodIndex(rows["year"].astype(int), freq="Y-DEC"),
        name=f"{country} {column}",
    ).dropna()
    if series.empty:
        raise ValueError(f"OWID Statistical Review: no {column} for {country!r}")
    return series.sort_index()
