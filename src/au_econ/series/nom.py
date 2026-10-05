"""Net Overseas Migration (3101.0): the official series, through the year, and a timely forward proxy.

The getters are cached for the run and return copies, so a caller changing a series
cannot corrupt the cache.
"""

from functools import cache
from typing import TYPE_CHECKING

import readabs as ra
from pandas import Period, PeriodIndex
from readabs import metacol as mc

from au_econ.series.population import complete_trailing_quarter, erp_age_sum, get_civ15, interp_june

if TYPE_CHECKING:
    from pandas import DataFrame, Series

NOM_CATALOGUE = "3101.0"
NOM_TABLE = "310101"
NOM_DID = "Net Overseas Migration ;  Australia ;"
DEATHS_DID = "Deaths ;  Australia ;"
NATURAL_INCREASE_DID = "Natural Increase ;  Australia ;"
ERP_CHANGE_DID, ERP_CHANGE_UNIT = "ERP Change Over Previous Year ;  Australia ;", "000"  # unit: not the % change
NOM_STYPE = "Original"  # 310101 is published Original only
QUARTERS_PER_YEAR = 4
MONTHS_PER_QUARTER = 3
THOUSAND = 1_000.0


@cache
def _table() -> tuple[DataFrame, DataFrame]:
    """Fetch 3101.0 table 310101 and its metadata (cached; not for mutation)."""
    data, meta = ra.read_abs_cat(NOM_CATALOGUE, single_excel_only=NOM_TABLE, verbose=False)
    return data[NOM_TABLE], meta


def _rolling_annual(did: str) -> tuple[Series, str]:
    """One 310101 series, by description, as a four-quarter rolling sum, with its units."""
    data, meta = _table()
    selector = {NOM_TABLE: mc.table, NOM_STYPE: mc.stype, did: mc.did}
    _, series_id, units = ra.find_abs_id(meta, selector, verbose=False)
    return data[series_id].rolling(QUARTERS_PER_YEAR).sum(), units


@cache
def _nom() -> tuple[Series, str]:
    """Fetch official NOM as a four-quarter rolling sum (cached; not for mutation)."""
    nom, units = _rolling_annual(NOM_DID)
    nom = nom.dropna()
    if nom.empty:
        raise ValueError(f"No Net Overseas Migration data in {NOM_TABLE}")
    return nom, units


def get_nom() -> tuple[Series, str, str]:
    """Return official Net Overseas Migration: quarterly, as a four-quarter rolling sum ('000 a year).

    The series type is reported rather than chosen: 310101 is published Original only.
    """
    nom, units = _nom()
    return nom.copy(), units, NOM_STYPE


# --- the 6202-based forward proxy
@cache
def _forward_proxy() -> tuple[Series, Series, Period, Period]:
    """Build the forward proxy for NOM (cached; not for mutation).

    proxy = civ15 year-on-year growth - 15-year-olds ageing in + 15+ deaths + child migration

    Deaths are added back because in a headcount a death looks like an emigration. Child
    migration (0-14 cohort survival, 3101.0) is observed while ERP by age exists, then
    extended by its median ratio to civ15 growth. civ15 is monthly, so a part-filled final
    quarter is completed before differencing; quarters after `last_complete` rest on
    extrapolated months.
    """
    civ15, _ = get_civ15()
    months_in_quarter = civ15.resample("Q").count()
    last_complete = months_in_quarter[months_in_quarter.eq(MONTHS_PER_QUARTER)].index[-1]
    filled = complete_trailing_quarter(civ15)
    filled_counts = filled.resample("Q").count()
    level = filled.resample("Q").mean().where(filled_counts.eq(MONTHS_PER_QUARTER))
    growth = level.diff(QUARTERS_PER_YEAR)
    growth_index = growth.index
    if not isinstance(growth_index, PeriodIndex):
        raise TypeError("Expected a quarterly PeriodIndex for civ15 growth")

    def aged(min_age: int) -> Series:
        return erp_age_sum(min_age) / THOUSAND  # persons -> '000, at June

    fifteen_year_olds = aged(15) - aged(16)
    child_migration_yearly = ((aged(1) - aged(16)) - (aged(0) - aged(15)).shift(1)).dropna()
    ageing_in = interp_june(fifteen_year_olds, growth_index)
    child_migration_observed = interp_june(child_migration_yearly, growth_index)

    deaths, _deaths_units = _rolling_annual(DEATHS_DID)
    nom, _units = _nom()
    natural_increase = (ageing_in - deaths).ffill()  # ageing in less deaths
    migration_15_plus = growth - natural_increase

    last_age = Period(f"{child_migration_yearly.index[-1].year}Q2", freq="Q-DEC")
    ratio = (child_migration_observed.loc[:last_age] / growth.loc[:last_age]).dropna().median()
    child_migration = child_migration_observed.copy()
    later = child_migration.index > last_age
    child_migration[later] = ratio * growth[later]

    proxy = (migration_15_plus + child_migration).dropna()
    if proxy.empty:
        raise ValueError("NOM forward proxy is empty: check the 6202 and 3101 inputs")
    nom_last = nom.index[-1]
    if not isinstance(nom_last, Period) or not isinstance(last_complete, Period):
        raise TypeError("Expected quarterly Periods")
    return proxy, nom, nom_last, last_complete


def get_nom_forward_proxy() -> tuple[Series, Series, Period, Period]:
    """Return (proxy, official NOM, last official quarter, last complete civ15 quarter).

    Both series are quarterly through-the-year counts ('000 a year). The proxy, built from
    the monthly civilian population aged 15+ (6202.0), runs one to two quarters past the
    official series; beyond the last complete civ15 quarter it rests on extrapolated months,
    so a chart should mark that segment. It is an indication of direction, not a substitute:
    first-published civ15 months are usually revised.
    """
    proxy, nom, last_official, last_complete = _forward_proxy()
    return proxy.copy(), nom.copy(), last_official, last_complete


# --- total population growth, forward
def _erp_annual_change() -> Series:
    """Return the published annual ERP change ('000), Original."""
    data, meta = _table()
    selector = {NOM_TABLE: mc.table, NOM_STYPE: mc.stype, ERP_CHANGE_DID: mc.did, ERP_CHANGE_UNIT: mc.unit}
    _, series_id, _units = ra.find_abs_id(meta, selector, verbose=False)
    return data[series_id].dropna()


@cache
def _population_growth_proxy() -> tuple[Series, Series, Period, Period]:
    """Build the forward proxy for annual ERP growth (cached; not for mutation).

    proxy = the NOM forward proxy + natural increase. Births and deaths come out with NOM,
    so past the last official quarter natural increase is held at its latest four-quarter sum.
    """
    nom_proxy, _nom, last_official, last_complete = _forward_proxy()
    natural_increase, _units = _rolling_annual(NATURAL_INCREASE_DID)
    natural_increase = natural_increase.dropna().reindex(nom_proxy.index).ffill()
    proxy = (nom_proxy + natural_increase).dropna()
    if proxy.empty:
        raise ValueError("Population growth proxy is empty: check the NOM proxy and natural increase")
    return proxy, _erp_annual_change(), last_official, last_complete


def get_population_growth_proxy() -> tuple[Series, Series, Period, Period]:
    """Return (proxy, official ERP growth, last official quarter, last complete civ15 quarter).

    Both series are quarterly through-the-year counts ('000 a year). The proxy is the NOM
    forward proxy plus natural increase, so it runs past the official series as that proxy
    does, with natural increase held at its latest value, and carries the same caveats.
    """
    proxy, official, last_official, last_complete = _population_growth_proxy()
    return proxy.copy(), official.copy(), last_official, last_complete
