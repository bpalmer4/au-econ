"""Population by government: the level and its growth, net overseas migration, and natural increase."""

# --- dependencies
import io
from functools import cache
from typing import TYPE_CHECKING

import mgplot as mg
import pandas as pd
import readabs as ra
from pandas import DataFrame, Series
from readabs import metacol as mc

from au_econ.analysis.decompose import FINAL_SEASADJ, FINAL_TREND, decompose
from au_econ.analysis.epochs import (
    QUARTERS_PER_YEAR,
    cagr_by_government,
    governments_since,
    index_by_government,
    mean_by_government,
    segment_by_government,
)
from au_econ.charting.epochs import epoch_vlines
from au_econ.series.population import get_implicit_population
from au_econ.sources.http_cache import get_file
from au_econ.topics.political.common import DECEMBER, INDEX_BASE_LINE, JUNE, LFOOTER

if TYPE_CHECKING:
    from collections.abc import Hashable

# --- constants
PERCENT = 100

# ABS Historical Population (3105.0.65.001), data cube HPDC1. Table 2 holds the
# 30 June estimates and table 1 the 31 December ones, so between them there are
# two observations a year. Both are laid out wide: row 4 carries the years,
# column 0 the sex and column 1 the state, and the national total is footnoted
# as "Australia(e)". Table 1 reaches back to 1788, but the colonial figures are
# of no use here, so the fetch starts at 1900.
HPDC1_URL = "https://www.abs.gov.au/statistics/people/population/historical-population/2021/HPDC1.xlsx"
HPDC1_CACHE_PREFIX = "abs_hpdc1"
HPDC1_SHEETS = {"Table 2": JUNE, "Table 1": DECEMBER}
HPDC1_HEADER_ROW = 4
HPDC1_SEX_COL, HPDC1_STATE_COL = 0, 1
HPDC1_FIRST_YEAR = 1900

# population
POP_SOURCE = "ABS: 3105.0.65.001, 5206.0"
POP_LFOOTER = LFOOTER + "Implicit population. Pre-1959Q3 interpolated from semi-annual data. "

# net overseas migration
NOM_SOURCE = "ABS: 3101.0"
NOM_NOTE = "From 1981Q2. Additive decomposition, ARIMA-extended. "
ERP_TABLE = "310101"
FIRST_NOM_GOVERNMENT = "Hawke-Keating"
# the COVID border closure, as used for this series in the ABS Population notebook
NOM_DISCONTINUITY = (pd.Period("2020Q1", freq="Q"),)
# lines use the trend - that is what the Henderson smoother is for; the means use the
# seasonally adjusted series, because the ARIMA extension synthesises the ends and the
# incumbent's term runs to the end of the data
TREND, SEASADJ = "Trend", "Seasonally adjusted"

# population growth: migration and natural increase
POP_DECOMP_SOURCE = "ABS: 3101.0"
POP_DECOMP_LFOOTER = LFOOTER + "Original series. From 1981Q2. "
NATURAL_INCREASE = "Natural increase"
MIGRATION = "Net overseas migration"
ERP = "Estimated resident population"
# the 12/16-month rule: NOM is measured on a new basis from this quarter on
NOM_METHOD_CHANGE = pd.Period("2006Q3", freq="Q")
NOM_METHOD_VLINE = {
    "text": "NOM 12/16-month rule",
    "loc": "bottom left",
    "color": "darkgrey",
    "linestyle": "--",
    "linewidth": 0.75,
}
CONTRIBUTION_ROUNDING = 2


# --- data
@cache
def _historical_population() -> Series:
    """Return quarterly population from 1900Q2, from the ABS historical population cube (cached; not for mutation).

    No quarterly population is published this far back - 3101.0 starts only 1981Q2 - so the
    quarters are interpolated between the cube's two observed points a year, 30 June and
    31 December. Checked against the true quarterly figures over 1959Q3-2021Q2, that
    interpolation is out by a median of 0.002 per cent and never by more than 0.6.
    """
    content = get_file(HPDC1_URL, prefix=HPDC1_CACHE_PREFIX)
    observations: list[Series] = []
    for sheet, month in HPDC1_SHEETS.items():
        raw = pd.read_excel(io.BytesIO(content), sheet_name=sheet, header=None)
        years = pd.to_numeric(raw.iloc[HPDC1_HEADER_ROW], errors="coerce")
        wanted = (raw[HPDC1_SEX_COL].astype(str).str.strip() == "Person") & (
            raw[HPDC1_STATE_COL].astype(str).str.strip().str.startswith("Australia")
        )
        if wanted.sum() != 1:
            raise ValueError(f"Expected one national row in {sheet}, found {wanted.sum()}")
        counts = pd.to_numeric(raw[wanted].iloc[0], errors="coerce")
        keep = years.notna() & counts.notna() & (years >= HPDC1_FIRST_YEAR)
        observations.append(
            Series(
                counts[keep].to_numpy(),
                index=pd.PeriodIndex(
                    [pd.Period(year=int(y), month=month, freq="Q") for y in years[keep]],
                    freq="Q",
                ),
            )
        )

    semi_annual = pd.concat(observations).sort_index()
    quarters = pd.period_range(semi_annual.index[0], semi_annual.index[-1], freq="Q")
    # pandas will only interpolate a PeriodIndex linearly, so the cubic fit is
    # done on timestamps and the period index put back afterwards
    gapped = semi_annual.reindex(quarters)
    gapped.index = quarters.to_timestamp()
    filled = gapped.interpolate(method="cubic")
    filled.index = quarters
    return filled.dropna().rename("Population")


def _derived_population(govts: DataFrame) -> Series:
    """Return population, quarterly, from the first election in `govts`.

    The implicit population from 1959Q3 on, with the historical cube supplying the quarters
    before it. The implicit values are left exactly as they are; the backcast only fills what
    they do not reach. No rebasing is needed: the joining quarter grows 0.51 per cent against
    a 1955-65 mean of 0.54 (sd 0.05), so there is no step to smooth.
    """
    implicit, _units = get_implicit_population()
    implicit = implicit.dropna()
    historical = _historical_population()
    joined = pd.concat([historical[historical.index < implicit.index[0]], implicit]).sort_index()
    first_election = pd.Period(govts["start"].iloc[0], freq="Q")
    return joined[joined.index >= first_election].rename("Population")


@cache
def _population_components() -> tuple[Series, Series, Series]:
    """Return quarterly natural increase, net overseas migration and the ERP (cached; not for mutation).

    All three come from 3101.0 table 310101 in thousands, on the one basis: the quarterly
    change in the ERP is natural increase plus NOM, give or take the intercensal adjustment,
    so the two components account for population growth exactly rather than one being a
    residual. The ratio of NOM to the ERP needs no rescaling. All from 1981Q2.
    """
    data, meta = ra.read_abs_cat("3101.0", single_excel_only=ERP_TABLE, verbose=False)
    selector = {ERP_TABLE: mc.table, "Original": mc.stype}
    wanted = {
        NATURAL_INCREASE: "Natural Increase ;  Australia ;",
        MIGRATION: "Net Overseas Migration ;  Australia ;",
        ERP: "Estimated Resident Population (ERP) ;  Australia ;",
    }
    series: dict[str, Series] = {}
    for label, did in wanted.items():
        _t, series_id, _u = ra.find_abs_id(meta, selector | {did: mc.did}, verbose=False)
        found = data[ERP_TABLE][series_id].dropna()
        if found.empty:
            raise ValueError(f"No data for {label} in {ERP_TABLE}")
        series[label] = found.rename(label)
    return series[NATURAL_INCREASE], series[MIGRATION], series[ERP]


@cache
def _nom_decomposed() -> DataFrame:
    """Return the additive seasonal decomposition of net overseas migration (cached; not for mutation).

    Additive rather than multiplicative: migration turns negative for six quarters from 2020.
    The ends are ARIMA-extended before smoothing and the trend is a 9-term Henderson moving
    average, the quarterly default. The COVID border closure is passed as a discontinuity so
    the smoother does not run the trend through it.
    """
    _natural, migration, _erp = _population_components()
    return decompose(
        migration,
        model="additive",
        arima_extend=True,
        discontinuity_list=list(NOM_DISCONTINUITY),
    )


def _nom_trend() -> Series:
    """Return the trend of net overseas migration."""
    return _nom_decomposed()[FINAL_TREND].dropna().rename("NOM trend")


def _growth_contributions(
    components: dict[str, Series], erp: Series, govts: DataFrame
) -> tuple[DataFrame, DataFrame]:
    """Return each component's compound annual and cumulative contribution to population growth by epoch.

    A quarter's component is taken against the population it joined - the ERP of the quarter
    before - which gives the growth that component contributed in that quarter. Compounding
    those quarterly rates across the epoch runs the population forward as if only that
    component had accrued. They do not sum to the population growth rate exactly: the ERP is
    rebased at each Census, and that intercensal adjustment belongs to neither component.
    """
    annual: dict[str, Series] = {}
    cumulative: dict[str, Series] = {}
    for label, component in components.items():
        quarterly_rate = (component / erp.shift(1)).dropna()
        segments = segment_by_government(quarterly_rate, govts)
        annual_rates: dict[str, float] = {}
        cumulative_rates: dict[str, float] = {}
        for name in segments.columns:
            observed = segments[name].dropna()
            if observed.empty:
                raise ValueError(f"No data within the {name} epoch to decompose")
            product = (1 + observed).prod()
            if not isinstance(product, int | float):
                raise TypeError(f"Expected a number compounding the {name} epoch, got {type(product).__name__}")
            compounded = float(product)
            annual_rates[str(name)] = (compounded ** (QUARTERS_PER_YEAR / len(observed)) - 1) * PERCENT
            cumulative_rates[str(name)] = (compounded - 1) * PERCENT
        annual[label] = Series(annual_rates)
        cumulative[label] = Series(cumulative_rates)
    return DataFrame(annual), DataFrame(cumulative)


def _pop_components() -> dict[str, Series]:
    """Return the two ERP growth components, keyed for _growth_contributions()."""
    natural, migration, _erp = _population_components()
    return {MIGRATION: migration, NATURAL_INCREASE: natural}


# --- helpers
def _two_lines(name: Hashable) -> str:
    """Break an epoch name over lines at its hyphens, for a bar label."""
    return str(name).replace("-", "\n")


def _plot_nom_line(series: Series, govts: DataFrame, *, share: bool, basis: str) -> None:
    """Plot net overseas migration over time, coloured by the party in power."""
    segments = segment_by_government(series, govts)
    index = segments.index
    if not isinstance(index, pd.PeriodIndex):
        raise TypeError(f"segments must have a PeriodIndex, got {type(index).__name__}")

    mg.line_plot_finalise(
        segments,
        title=(
            "Net Overseas Migration by Government: Per Cent of Population"
            if share
            else "Net Overseas Migration by Government"
        ),
        ylabel="Per cent of population per quarter" if share else "'000 per quarter",
        color=mg.colorise_list(govts["party"]),
        style="-",
        annotate=False,
        legend=False,
        axvline=epoch_vlines(govts, index.freqstr, loc="top right"),
        y0=True,
        rfooter=NOM_SOURCE,
        lfooter=f"{LFOOTER}{basis}. {NOM_NOTE}",
    )


# --- charts
def population_index(govts: DataFrame) -> None:
    """Chart population, rebased to 100 at each government's election."""
    indexed = index_by_government(_derived_population(govts), govts)
    index = indexed.index
    if not isinstance(index, pd.PeriodIndex):
        raise TypeError(f"indexed must have a PeriodIndex, got {type(index).__name__}")

    mg.line_plot_finalise(
        indexed,
        title="Population by Government",
        ylabel="Index (= 100 at each election)",
        color=mg.colorise_list(govts["party"]),
        style="-",
        annotate=False,
        legend=False,
        axvline=epoch_vlines(govts, index.freqstr, loc="top right"),
        axhline=INDEX_BASE_LINE,
        rfooter=POP_SOURCE,
        lfooter=POP_LFOOTER,
    )


def population_cagr(govts: DataFrame) -> None:
    """Chart compound annual population growth for each government, first to last print."""
    cagr = cagr_by_government(_derived_population(govts), govts)
    mg.bar_plot_finalise(
        cagr.rename(index=_two_lines),
        title="Population by Government: Growth (first vs last print)",
        ylabel="Per cent per year",
        color=mg.colorise_list(govts["party"]),
        annotate=True,
        rounding=1,
        y0=True,
        rfooter=POP_SOURCE,
        lfooter=POP_LFOOTER + "Compound annual growth rate. ",
    )


def nom_trend(govts: DataFrame) -> None:
    """Chart the trend in net overseas migration, coloured by government."""
    _plot_nom_line(_nom_trend(), governments_since(govts, FIRST_NOM_GOVERNMENT), share=False, basis=TREND)


def nom_share_of_population(govts: DataFrame) -> None:
    """Chart the trend in net overseas migration as a share of population, coloured by government."""
    _natural, _migration, erp = _population_components()
    _plot_nom_line(
        (_nom_trend() / erp * PERCENT).dropna(),
        governments_since(govts, FIRST_NOM_GOVERNMENT),
        share=True,
        basis=TREND,
    )


def nom_mean(govts: DataFrame) -> None:
    """Chart the mean quarterly net overseas migration flow under each government."""
    nom_governments = governments_since(govts, FIRST_NOM_GOVERNMENT)
    nom_sa = _nom_decomposed()[FINAL_SEASADJ].dropna().rename("NOM seasonally adjusted")
    average = mean_by_government(nom_sa, nom_governments)
    mg.bar_plot_finalise(
        average.rename(index=_two_lines),
        title="Net Overseas Migration by Government: Mean Quarterly Flow",
        ylabel="'000 per quarter",
        color=mg.colorise_list(nom_governments["party"]),
        annotate=True,
        rounding=1,
        y0=True,
        rfooter=NOM_SOURCE,
        lfooter=f"{LFOOTER}{SEASADJ}. {NOM_NOTE}",
    )


def growth_contributions(govts: DataFrame) -> None:
    """Chart the compound annual contribution of migration and natural increase to population growth, stacked."""
    _natural, _migration, erp = _population_components()
    pop_annual, _pop_cumulative = _growth_contributions(
        _pop_components(), erp, governments_since(govts, FIRST_NOM_GOVERNMENT)
    )
    mg.bar_plot_finalise(
        pop_annual.rename(index=_two_lines),
        stacked=True,
        title="Population Growth by Government: Migration and Natural Increase",
        ylabel="Per cent per year",
        annotate=True,
        rounding=CONTRIBUTION_ROUNDING,
        y0=True,
        legend={"loc": "best", "fontsize": "small"},
        rfooter=POP_DECOMP_SOURCE,
        lfooter=POP_DECOMP_LFOOTER
        + f"Compound annual rates. Excludes intercensal rebasing. NOM basis changes {NOM_METHOD_CHANGE}. ",
    )


def contribution_lines(govts: DataFrame) -> None:
    """Chart the year-ended contributions of migration and natural increase to population growth."""
    nom_governments = governments_since(govts, FIRST_NOM_GOVERNMENT)
    _natural, _migration, erp = _population_components()
    frame = DataFrame(
        {
            label: (component.rolling(QUARTERS_PER_YEAR).sum() / erp.shift(QUARTERS_PER_YEAR) * PERCENT).dropna()
            for label, component in _pop_components().items()
        }
    )
    start = pd.Period(nom_governments["start"].iloc[0], freq="Q")
    frame = frame[frame.index >= start]
    index = frame.index
    if not isinstance(index, pd.PeriodIndex):
        raise TypeError(f"frame must have a PeriodIndex, got {type(index).__name__}")

    mg.line_plot_finalise(
        frame,
        title="Contributions to Population Growth: Migration and Natural Increase",
        ylabel="Per cent per year",
        annotate=True,
        rounding=CONTRIBUTION_ROUNDING,
        legend={"loc": "best", "fontsize": "small"},
        axvline=[
            *epoch_vlines(nom_governments, index.freqstr, loc="top right"),
            {"x": NOM_METHOD_CHANGE.ordinal, **NOM_METHOD_VLINE},
        ],
        y0=True,
        rfooter=POP_DECOMP_SOURCE,
        lfooter=POP_DECOMP_LFOOTER + "Year-ended contributions. ",
    )


# --- table of contents, in run order
CHARTS = (
    (population_index, ()),
    (population_cagr, ()),
    (nom_trend, ()),
    (nom_share_of_population, ()),
    (nom_mean, ()),
    (growth_contributions, ()),
    (contribution_lines, ()),
)
