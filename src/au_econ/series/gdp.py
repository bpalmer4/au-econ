"""National Accounts (5206.0) series wanted by more than one module: GDP, compensation per hour.

Every 5206.0 table is read through one cached reader, so each workbook is fetched once per
run whichever getters use it. The getters are cached for the run and return (series,
units), with the series a copy, so a caller changing it cannot corrupt the cache.
"""

from functools import cache
from typing import TYPE_CHECKING

import readabs as ra
from readabs import metacol as mc

if TYPE_CHECKING:
    from pandas import DataFrame, Series

GDP_CATALOGUE = "5206.0"
GDP_TABLE = "5206001_Key_Aggregates"
GDP_MEASURES = {
    "CP": "Gross domestic product: Current prices ;",
    "CVM": "Gross domestic product: Chain volume measures ;",
}
SERIES_TYPES = {"SA": "Seasonally Adjusted", "T": "Trend", "O": "Original"}
ANALYTICAL_TABLE = "5206024_Selected_Analytical_Series"
COE_PER_HOUR_DID = "Compensation of employees per hour: Current prices ;"


@cache
def _table(table: str) -> tuple[dict[str, DataFrame], DataFrame]:
    """Read one 5206.0 table (cached; not for mutation): the data and its metadata."""
    data, meta = ra.read_abs_cat(GDP_CATALOGUE, single_excel_only=table, verbose=False)
    if table not in data:
        raise ValueError(f"ABS {GDP_CATALOGUE}: table {table} not returned")
    return data, meta


@cache
def _gdp(measure: str, series_type: str) -> tuple[Series, str]:
    """Fetch one GDP series (cached; not for mutation)."""
    if measure not in GDP_MEASURES:
        raise ValueError(f"Unknown GDP measure {measure!r}: choose from {sorted(GDP_MEASURES)}")
    if series_type not in SERIES_TYPES:
        raise ValueError(f"Unknown series type {series_type!r}: choose from {sorted(SERIES_TYPES)}")
    data, meta = _table(GDP_TABLE)
    selector = {GDP_MEASURES[measure]: mc.did, SERIES_TYPES[series_type]: mc.stype}
    table, series_id, units = ra.find_abs_id(meta, selector, verbose=False)
    series = data[table][series_id]
    if series.dropna().empty:
        raise ValueError(f"ABS {GDP_CATALOGUE} returned no {measure} {series_type} GDP values")
    return series, units


def get_gdp(measure: str = "CP", series_type: str = "SA") -> tuple[Series, str]:
    """Return quarterly GDP and its units: measure "CP" (current prices) or "CVM"; series type "SA", "T" or "O"."""
    series, units = _gdp(measure, series_type)
    return series.copy(), units


def get_table(table: str) -> tuple[dict[str, DataFrame], DataFrame]:
    """Return one 5206.0 table (e.g. "5206002_Expenditure_Volume_Measures") and its metadata, as copies."""
    data, meta = _table(table)
    return {name: frame.copy() for name, frame in data.items()}, meta.copy()


@cache
def _compensation_per_hour() -> tuple[Series, str]:
    """Fetch compensation of employees per hour (cached; not for mutation)."""
    data, meta = _table(ANALYTICAL_TABLE)
    selector = {ANALYTICAL_TABLE: mc.table, COE_PER_HOUR_DID: mc.did, "Seasonally Adjusted": mc.stype}
    table, series_id, units = ra.find_abs_id(meta, selector, verbose=False)
    series = data[table][series_id].dropna()
    if series.empty:
        raise ValueError(f"ABS {GDP_CATALOGUE} returned no compensation of employees per hour")
    return series, units


def get_compensation_per_hour() -> tuple[Series, str]:
    """Return compensation of employees per hour, current prices, seasonally adjusted, and its units."""
    series, units = _compensation_per_hour()
    return series.copy(), units
