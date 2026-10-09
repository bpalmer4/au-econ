"""Net Overseas Migration (3101.0): the official series, through the year, and a timely forward proxy.

The proxy rests on a split of civilian population 15+ (6202.0) growth into 15+ natural
increase and 15+ migration, which is also available on its own.

The getters are cached for the run and return copies, so a caller changing a series
cannot corrupt the cache.
"""

from functools import cache
from math import isnan

import readabs as ra
from pandas import DataFrame, Period, PeriodIndex, Series
from readabs import metacol as mc

from au_econ.series.population import complete_trailing_quarter, erp_age_sum, get_civ15, interp_june

NOM_CATALOGUE = "3101.0"
NOM_TABLE = "310101"
NOM_DID = "Net Overseas Migration ;  Australia ;"
DEATHS_DID = "Deaths ;  Australia ;"
BIRTHS_DID = "Births ;  Australia ;"
COHORT_AGE = 15  # civ15's youngest age: the cohort ageing in each year
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
def _aged(min_age: int) -> Series:
    """ERP aged min_age and over, '000, at June."""
    return erp_age_sum(min_age) / THOUSAND


@cache
def _civ15_split() -> tuple[Series, Series, Period]:
    """Split civ15 year-on-year growth into 15+ natural increase and 15+ migration (cached; not for mutation).

    migration 15+ = civ15 growth - 15-year-olds ageing in + 15+ deaths

    Deaths are added back because in a headcount a death looks like an emigration. civ15 is
    monthly, so a part-filled final quarter is completed before differencing; quarters after
    `last_complete` rest on extrapolated months. Returns (civ15 growth, migration 15+,
    last complete civ15 quarter).
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
    if not isinstance(last_complete, Period):
        raise TypeError("Expected a quarterly Period for the last complete civ15 quarter")

    ageing_in = interp_june(_aged(15) - _aged(16), growth_index)
    deaths, _deaths_units = _rolling_annual(DEATHS_DID)
    natural_increase = (ageing_in - deaths).ffill()  # ageing in less deaths
    return growth, growth - natural_increase, last_complete


@cache
def _migrant_ageing_in() -> Series:
    """15-year-olds who arrived as child migrants, '000 a year, on civ15's quarters (cached; not for mutation).

    Each June, the 15-year-olds less the births of the year to June COHORT_AGE years earlier:
    the cohort's net child migration, less its child deaths (so slightly understated). Spread
    between Junes and held after the latest, as the ageing-in term is.
    """
    growth, _migration_15_plus, _last_complete = _civ15_split()
    growth_index = growth.index
    if not isinstance(growth_index, PeriodIndex):
        raise TypeError("Expected a quarterly PeriodIndex for civ15 growth")
    births, _units = _rolling_annual(BIRTHS_DID)
    fifteen_year_olds = _aged(COHORT_AGE) - _aged(COHORT_AGE + 1)
    migrants: dict[Period, float] = {}
    for june, cohort in fifteen_year_olds.items():
        if not isinstance(june, Period):
            raise TypeError("Expected a PeriodIndex on ERP by age")
        birth_year = Period(year=june.year - COHORT_AGE, quarter=2, freq="Q-DEC")
        cohort_births = births.get(birth_year)
        if isinstance(cohort_births, float) and not isnan(cohort_births):
            migrants[june] = float(cohort) - cohort_births
    if not migrants:
        raise ValueError("No June with both 15-year-olds and births 15 years earlier")
    return interp_june(Series(migrants, dtype=float), growth_index)


@cache
def _child_migration() -> tuple[Series, Period]:
    """Net child migration, quarterly through the year ('000 a year), and its last observed quarter (cached).

    Observed by cohort survival while ERP by age exists (those aged 1-15 each June less those
    aged 0-14 a June earlier: children 14 and under, net of their few deaths), spread onto
    civ15's quarters between Junes, then extended by its median ratio to civ15 growth.
    """
    growth, _migration_15_plus, _last_complete = _civ15_split()
    growth_index = growth.index
    if not isinstance(growth_index, PeriodIndex):
        raise TypeError("Expected a quarterly PeriodIndex for civ15 growth")
    child_migration_yearly = ((_aged(1) - _aged(16)) - (_aged(0) - _aged(15)).shift(1)).dropna()
    child_migration_observed = interp_june(child_migration_yearly, growth_index)

    last_age = Period(f"{child_migration_yearly.index[-1].year}Q2", freq="Q-DEC")
    ratio = (child_migration_observed.loc[:last_age] / growth.loc[:last_age]).dropna().median()
    child_migration = child_migration_observed.copy()
    later = child_migration.index > last_age
    child_migration[later] = ratio * growth[later]
    return child_migration, last_age


@cache
def _forward_proxy() -> tuple[Series, Series, Period, Period]:
    """Build the forward proxy for NOM (cached; not for mutation).

    proxy = civ15 migration 15+ (see _civ15_split) + child migration (see _child_migration)
    """
    _growth, migration_15_plus, last_complete = _civ15_split()
    child_migration, _last_age = _child_migration()
    nom, _units = _nom()

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


def get_civ15_migration_split() -> tuple[Series, Series, Series, Period]:
    """Return (civ15 annual growth, of which migration 15+, migrant 15-year-olds, last complete civ15 quarter).

    The series are quarterly through-the-year counts ('000 a year), from the same split as
    the NOM forward proxy, without its child migration: children are not in civ15. Migrant
    15-year-olds (see _migrant_ageing_in) sit inside the split's natural increase, as part of
    the ageing-in cohort. The civ15 level steps at each ERP benchmark, and quarters after the
    last complete one rest on extrapolated months.
    """
    growth, migration_15_plus, last_complete = _civ15_split()
    return growth.copy(), migration_15_plus.copy(), _migrant_ageing_in().copy(), last_complete


def get_nom_by_age() -> tuple[DataFrame, Period]:
    """Return (official NOM split by age, last quarter of observed child migration).

    Quarterly through-the-year counts ('000 a year): aged 14 and under is the forward proxy's
    child migration (see _child_migration), aged 15+ is official NOM less it, and the two sum
    to official NOM. After the returned quarter, child migration is extended, not observed.
    """
    nom, _units = _nom()
    child, last_age = _child_migration()
    frame = DataFrame({"Aged 14 and under": child, "Aged 15+": nom - child}).dropna()
    if frame.empty:
        raise ValueError("No quarters with both official NOM and child migration")
    return frame, last_age


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
