"""Shared pieces of the Population module: tables, constants, the fetch and the growth measures."""

# --- dependencies
from dataclasses import dataclass

import pandas as pd
import readabs as ra
from mgplot import get_color
from readabs import metacol as mc

from au_econ.series.population import get_civ15, get_implicit_population, smoothed_monthly_pop_growth

# --- catalogues and tables
CATALOGUE = "3101.0"
MOVEMENTS_CATALOGUE = "3401.0"
AGGREGATES, STATES_TABLE = "310101", "310104"
ARRIVALS, DEPARTURES = "340101", "340102"
AGE_TABLES = tuple(f"31010{i}" for i in range(51, 60))
AUSTRALIA_AGE_TABLE = "3101059"

# --- sources
SOURCE_3101 = "ABS: 3101.0"
SOURCE_POP = "ABS: 3101.0, 5206.0, 6202.0"  # population estimates from three releases
SOURCE_3101_3401 = "ABS: 3101.0, 3401.0"
SOURCE_3101_6202 = "ABS: 3101.0, 6202.0"
SOURCE_LIFE_TABLES = "ABS: 3101.0, 3302.0.55.001"  # with the life tables

# --- windows
RECENT_MONTHS = 88  # about seven years, for the monthly growth charts

# --- age profiles
GROUPS = ("Female", "Male", "Persons")  # Persons must be last
STATES = {"NSW", "Vic", "Qld", "SA", "WA", "Tas", "NT", "ACT", "Australia"}
STATE_COLORS = {state: get_color(state) for state in STATES}
HMA_SMOOTHER = 5
LINESTYLES = ["-", "-.", "--", ":"] * 3

# --- seasonal decomposition break-points (COVID)
DISCONTINUITIES = {
    "Births": [pd.Period("2020-Q4", freq="Q")],
    "Deaths": [],
    "Natural Increase": [pd.Period("2020-Q4", freq="Q")],
    "Overseas Arrivals": [pd.Period("2020-Q1", freq="Q")],
    "Overseas Departures": [pd.Period("2020-Q1", freq="Q")],
    "Net Overseas Migration": [pd.Period("2020-Q1", freq="Q")],
}

COVID_YEARS = (2020, 2021)  # left out of the seasonal estimates
QUARTERS_PER_YEAR, MONTHS_PER_YEAR = 4, 12
PERCENT, THOUSAND = 100, 1_000
HMA_TERMS = 25
ORIGINAL = "Original"
SCALE_WORDS = {"000": "Thousands"}  # ABS unit -> a word ra.recalibrate understands

# --- the growth measures, from 3101.0 (310101) and 3401.0
GROWTH_SERIES: dict[str, tuple[str, ...]] = {  # key: (table, data item description[, unit])
    "Estimated Resident Population": (AGGREGATES, "Estimated Resident Population (ERP) ;  Australia ;"),
    # the unit separates it from the percentage change, whose description contains it
    "Estimated Resident Population Annual Growth": (
        AGGREGATES,
        "ERP Change Over Previous Year ;  Australia ;",
        "000",
    ),
    "Estimated Resident Population Annual Growth Rate": (
        AGGREGATES,
        "Percentage ERP Change Over Previous Year ;  Australia ;",
    ),
    "Natural Increase": (AGGREGATES, "Natural Increase ;  Australia ;"),
    "Deaths": (AGGREGATES, "Deaths ;  Australia ;"),
    "Births": (AGGREGATES, "Births ;  Australia ;"),
    "Total Monthly Arrivals": (ARRIVALS, "Number of movements ;  Total Arrivals ;"),
    "Total Monthly Departures": (DEPARTURES, "Number of movements ;  Total Departures ;"),
}
ERP_GROWTH = "Estimated Resident Population Annual Growth"


@dataclass(frozen=True)
class PopulationData:
    """The 3101.0 tables used (aggregates, states, ages), the 3401.0 movements, and the growth measures."""

    tables: dict[str, pd.DataFrame]
    meta: dict[str, pd.DataFrame]  # by table
    age_data: dict[str, pd.DataFrame]
    age_meta: pd.DataFrame
    growth: dict[str, pd.Series]  # monthly
    erp_growth_units: str  # the ABS unit of the ERP annual growth series


# --- data
def _read(catalogue: str, table: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """One ABS table and its metadata; raise if it is missing."""
    data, meta = ra.read_abs_cat(catalogue, single_excel_only=table, verbose=False)
    if table not in data or data[table].empty:
        raise ValueError(f"ABS {catalogue}: table {table} not returned")
    return data[table], meta


def _growth(tables: dict[str, pd.DataFrame], meta: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.Series], str]:
    """Collect the growth measures and derive the annual aggregates, all on a monthly index."""
    data: dict[str, pd.Series] = {}
    units: dict[str, str] = {}
    for key, (table, did, *unit) in GROWTH_SERIES.items():
        selector = {table: mc.table, did: mc.did, ORIGINAL: mc.stype} | dict.fromkeys(unit, mc.unit)
        _table, series_id, units[key] = ra.find_abs_id(meta[table], selector, verbose=False)
        data[key] = tables[table][series_id]

    civ15, _ = get_civ15()
    data["LFS Civilian Population 15+"] = civ15
    # the level steps at each ERP benchmark, so its growth comes from the smoothed increment
    civ15_growth = smoothed_monthly_pop_growth(civ15).rolling(MONTHS_PER_YEAR).sum()
    data["LFS Civilian Population 15+ Annual Growth"] = civ15_growth
    data["LFS Civilian Population 15+ Annual Growth Rate"] = civ15_growth / civ15 * PERCENT
    data["12 month rolling net total arrivals"] = (
        data["Total Monthly Arrivals"] - data["Total Monthly Departures"]
    ).rolling(MONTHS_PER_YEAR).sum() / THOUSAND
    for name in ("Natural Increase", "Deaths", "Births"):
        data[f"Annual {name}"] = data[name].rolling(QUARTERS_PER_YEAR).sum()
    data["ERP Growth less Natural Increase"] = data[ERP_GROWTH] - data["Annual Natural Increase"]
    implicit = get_implicit_population()[0] / THOUSAND
    data["Implicit population from National Accounts"] = implicit
    data["Implicit population (from National Accounts) growth"] = implicit.diff(periods=QUARTERS_PER_YEAR)
    data["Implicit population (from National Accounts) growth rate"] = (
        implicit.pct_change(periods=QUARTERS_PER_YEAR, fill_method=None) * PERCENT
    )

    monthly = {}
    for key, series in data.items():
        index = series.index
        if not isinstance(index, pd.PeriodIndex):
            raise TypeError(f"{key}: expected a PeriodIndex")
        monthly[key] = ra.qtly_to_monthly(series) if index.freqstr[0] == "Q" else series
    return monthly, units[ERP_GROWTH]


def load() -> PopulationData:
    """Fetch the 3101.0 aggregate, state and age tables and the 3401.0 movements; derive the growth measures."""
    tables, meta = {}, {}
    for catalogue, table in (
        (CATALOGUE, AGGREGATES),
        (CATALOGUE, STATES_TABLE),
        (MOVEMENTS_CATALOGUE, ARRIVALS),
        (MOVEMENTS_CATALOGUE, DEPARTURES),
    ):
        tables[table], meta[table] = _read(catalogue, table)
    print(f"ERP (310101)         current to: {tables[AGGREGATES].index[-1]}")
    print(f"State ERP (310104)   current to: {tables[STATES_TABLE].index[-1]}")

    age_data, age_meta_parts = {}, []
    for table in AGE_TABLES:
        age_data[table], table_meta = _read(CATALOGUE, table)
        age_meta_parts.append(table_meta[table_meta[mc.table] == table])

    growth, erp_growth_units = _growth(tables, meta)
    return PopulationData(
        tables=tables,
        meta=meta,
        age_data=age_data,
        age_meta=pd.concat(age_meta_parts),
        growth=growth,
        erp_growth_units=erp_growth_units,
    )


# --- helpers
def recalibrated[T: (pd.Series, pd.DataFrame)](data: T, units: str) -> tuple[T, str]:
    """Recalibrate to readable units."""
    result, units = ra.recalibrate(data, units)
    if not isinstance(result, type(data)):
        raise TypeError(f"recalibrate returned {type(result).__name__}")
    return result, units


def aggregate(data: PopulationData, did: str) -> tuple[pd.Series, str]:
    """One Original 310101 series, by description, with its units."""
    selector = {AGGREGATES: mc.table, ORIGINAL: mc.stype, did: mc.did}
    _table, series_id, units = ra.find_abs_id(data.meta[AGGREGATES], selector, verbose=False)
    return data.tables[AGGREGATES][series_id], units
