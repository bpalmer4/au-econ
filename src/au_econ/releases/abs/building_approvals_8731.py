"""Building Approvals, Australia (8731.0): dwellings approved and the value of building approved, monthly.

Also approvals by state against the dwelling stock, population and adult population growth;
approvals per adult; a quarterly growth model on the unemployment rate; and the value of
building approved as a share of GDP.
"""

# --- dependencies
from typing import Any

import mgplot as mg
import pandas as pd
import readabs as ra
from mgplot import line_plot_finalise, multi_start, seastrend_plot_finalise, series_growth_plot_finalise
from readabs import metacol as mc
from statsmodels.regression.linear_model import OLS, RegressionResults
from statsmodels.stats.stattools import durbin_watson
from statsmodels.tools.tools import add_constant

from au_econ.charting.footers import SERIES_TYPE_NOTES
from au_econ.charting.windows import monthly_plot_times, quarterly_plot_times
from au_econ.series.gdp import get_gdp
from au_econ.series.population import get_state_erp
from au_econ.sources.abs import AbsRelease, fetch_release

# --- module contract
RELEASE = ("8731", "approvals")
TOPICS = ("building",)
TITLE = "Building Approvals"

# --- constants
CATALOGUE = "8731.0"
WITH_LFS_SOURCE = "ABS: 6202.0, 8731.0"  # charts that use the Labour Force
SA, TREND, ORIGINAL = "Seasonally Adjusted", "Trend", "Original"
MONTHS_PER_QUARTER, MONTHS_PER_YEAR, QUARTERS_PER_YEAR = 3, 12, 4
PERCENT, THOUSAND, PER_100K = 100.0, 1_000, 100_000

APPROVALS_TABLE = "8731006"
TOTAL_DID = "Total number of dwelling units ;  Total (Type of Building) ;  Total Sectors ;"
HOUSES_DID = "Total number of dwelling units ;  Houses ;  Total Sectors ;"
HEADLINE = (
    (HOUSES_DID, "Houses"),
    (
        "Total number of dwelling units ;  Dwellings excluding houses ;  Total Sectors ;",
        "Dwellings excluding houses",
    ),
    (TOTAL_DID, "Total Dwellings"),
)

# by state
STATE_TABLE = "8731009"
STOCK_CATALOGUE, STOCK_TABLE = "6432.0", "643201"
LFS_CATALOGUE = "6202.0"
LFS_STATE_TABLES = ("62020002", "62020003", "62020004", "62020005", "62020006", "62020007", "62020008", "62020009")
LFS_NATIONAL_TABLE = "62020001"
CIV_POP_DID = "Civilian population aged 15 years and over ;  Persons ;"

# approvals per adult
POST_COVID_START = pd.Period("2022-07", freq="M")
CLIPPED_YLIM = (0.2, 1.5)
COVID_SPAN = {
    "xmin": pd.Period("2020-04"),
    "xmax": pd.Period("2024-10"),
    "color": "goldenrod",
    "alpha": 0.3,
    "label": "COVID impacted inc. migration rebound",
}
LEGEND = {"loc": "best", "fontsize": "x-small"}

# the approvals model
HAC_LAGS = 4

# value of building approved
VALUE_TABLE = "87310038"  # nominal $'000, monthly
CVM_TABLE = "87310078"  # chain volume measures, $ millions, quarterly
NOMINAL_COMPONENTS = (
    ("Total value of building jobs ;  Total Residential ;  Total Work ;", "Residential"),
    ("Total value of building jobs ;  Total Non-residential ;  Total Work ;", "Non-residential"),
)
CVM_PREFIX = "Total value of building jobs ;  Chain Volume Measures ;  Total Sectors ;  "
CVM_COMPONENTS = (
    (f"{CVM_PREFIX}Total Residential ;  Total Work ;", "Residential"),
    (f"{CVM_PREFIX}Total Non-residential ;  Total Work ;", "Non-residential"),
)
NOMINAL_NOTE = "Nominal: construction cost inflation not removed. "
CVM_NOTE = "Chain volume measures. "


# --- data
def fetch() -> AbsRelease:
    """Fetch the release once; every chart function receives it."""
    return fetch_release(CATALOGUE, ignore_errors=True)


# --- helpers
def _plot_times(release: AbsRelease) -> tuple[int, pd.Period]:
    return 0, pd.Period(release.recent, freq="M")


def _recalibrated[T: (pd.Series, pd.DataFrame)](data: T, units: str) -> tuple[T, str]:
    result, units = ra.recalibrate(data, units)
    if not isinstance(result, type(data)):
        raise TypeError(f"recalibrate returned {type(result).__name__}")
    return result, units


def _to_quarterly(monthly: pd.Series, how: str) -> pd.Series:
    """Aggregate a monthly series to quarters, keeping only complete ones (a part quarter would plot too small)."""
    grouped = monthly.resample("Q")
    aggregate = grouped.sum() if how == "sum" else grouped.mean()
    return aggregate[grouped.count() == MONTHS_PER_QUARTER]


def _selected(release: AbsRelease, table: str, did: str, stype: str) -> tuple[pd.Series, str]:
    _table, series_id, units = ra.find_abs_id(release.meta, {did: mc.did, table: mc.table, stype: mc.stype})
    return release.data[table][series_id], units


def _building_value(release: AbsRelease, table: str, did: str, stype: str) -> tuple[pd.Series, str]:
    """One building-value series, with its ABS unit; raise if it is empty."""
    series, units = _selected(release, table, did, stype)
    series = series.dropna()
    if series.empty:
        raise ValueError(f"No data for {table} / {did} / {stype}")
    return series, units


def _civ_pop_national() -> pd.Series:
    """Return the national civilian population aged 15+, in persons, monthly (6202.0, Original)."""
    data, meta = ra.read_abs_cat(LFS_CATALOGUE, single_excel_only=LFS_NATIONAL_TABLE)
    _table, series_id, _units = ra.find_abs_id(
        meta, {CIV_POP_DID: mc.did, LFS_NATIONAL_TABLE: mc.table, ORIGINAL: mc.stype}
    )
    return data[LFS_NATIONAL_TABLE][series_id].dropna() * THOUSAND


def _hbar(series: pd.Series, title: str, xlabel: str, *, rounding: bool | int, rfooter: str) -> None:
    """Draw a horizontal bar chart by state, sorted, in state colours."""
    by_state = series.rename(index=dict(zip(mg.state_names, mg.state_abbrs, strict=True))).sort_values()
    mg.bar_plot_finalise(
        by_state,
        horizontal=True,
        color=[mg.get_color(name) for name in by_state.index],
        annotate=True,
        above=True,
        rounding=rounding,  # True: about 3 significant figures
        title=title,
        xlabel=xlabel,
        rfooter=rfooter,
        lfooter="Australia. Original series. ",
    )


def _dur12() -> pd.Series:
    """Return the four-quarter change in the SA unemployment rate (6202.0), from complete quarters."""
    data, meta = ra.read_abs_cat(LFS_CATALOGUE, single_excel_only=LFS_NATIONAL_TABLE)
    _table, series_id, _units = ra.find_abs_id(
        meta, {"Unemployment rate ;  Persons ;": mc.did, LFS_NATIONAL_TABLE: mc.table, SA: mc.stype}
    )
    return _to_quarterly(data[LFS_NATIONAL_TABLE][series_id].dropna(), "mean").diff(QUARTERS_PER_YEAR)


def _fit_model(approvals: pd.Series, dur12: pd.Series, label: str) -> RegressionResults:
    """Fit QoQ(t) = b0 + b1 QoQ(t-1) + b2 dUR12(t), with HAC (Newey-West) standard errors."""
    qoq = approvals.pct_change(1) * PERCENT
    frame = pd.DataFrame({"qoq": qoq, "qoq_lag1": qoq.shift(1), "dur12": dur12}).dropna()
    model = OLS(frame["qoq"], add_constant(frame[["qoq_lag1", "dur12"]])).fit(
        cov_type="HAC", cov_kwds={"maxlags": HAC_LAGS}
    )
    print(f"=== {label} ===")
    print(model.summary())
    print(f"Durbin-Watson: {durbin_watson(model.resid):.2f}\n")
    return model


def _plot_model(model: RegressionResults, approvals: pd.Series, dur12: pd.Series, *, label: str, tag: str) -> None:
    """Chart modelled against actual approvals; the model runs a quarter past the actuals as a nowcast."""
    qoq = approvals.pct_change(1) * PERCENT
    design = pd.DataFrame({"qoq_lag1": qoq.shift(1), "dur12": dur12}).dropna()
    fitted = approvals.shift(1).reindex(design.index) * (
        1 + model.predict(add_constant(design, has_constant="add")) / PERCENT
    )
    multi_start(
        pd.DataFrame({"Actual": approvals, "Modelled": fitted}).dropna(how="all"),
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title=f"Building Approvals Model: {label}",
        ylabel="Residential dwelling units / quarter",
        rheader="QoQ(t) = β₀ + β₁·QoQ(t-1) + β₂·ΔUR₁₂(t)",
        rfooter=WITH_LFS_SOURCE,
        lfooter="Australia. Seasonally adjusted, quarterly. "
        "QoQ growth on its lag and the 12m change in unemployment. "
        f"Adj. R²={model.rsquared_adj:.2f}. ",
        width=[2, 1.5],
        style=["-", "--"],
        annotate=False,
        tag=tag,
    )


def _value_seastrend(
    release: AbsRelease,
    table: str,
    components: tuple[tuple[str, str], ...],
    *,
    starts: tuple[int, int | pd.Period],
    title_prefix: str,
    note: str,
    period_label: str,
) -> None:
    """Chart seasonally adjusted against trend, one chart per building component."""
    for did, label in components:
        frame = pd.DataFrame()
        units = ""
        for stype in (SA, TREND):
            frame[stype], units = _building_value(release, table, did, stype)
        frame, units = _recalibrated(frame, units)
        multi_start(
            frame,
            function=seastrend_plot_finalise,
            starts=starts,
            title=f"{title_prefix}, {label}",
            ylabel=f"{units} / {period_label}",
            rfooter=release.source,
            lfooter=f"Australia. {label} building. {note}",
            rounding=1,
        )


def _value_trend_comparison(
    release: AbsRelease,
    table: str,
    components: tuple[tuple[str, str], ...],
    *,
    starts: tuple[int, int | pd.Period],
    title: str,
    note: str,
    period_label: str,
) -> None:
    """Chart the trend value approved: residential against non-residential."""
    frame = pd.DataFrame()
    units = ""
    for did, label in components:
        frame[label], units = _building_value(release, table, did, TREND)
    frame, units = _recalibrated(frame, units)
    multi_start(
        frame,
        function=line_plot_finalise,
        starts=starts,
        title=title,
        ylabel=f"{units} / {period_label}",
        rfooter=release.source,
        lfooter=f"Australia. Trend series. {note}",
        rounding=1,
    )


# --- charts
def building_approvals(release: AbsRelease) -> None:
    """Chart dwelling approvals (houses, other dwellings, total): SA against trend, and growth."""
    for did, label in HEADLINE:
        frame = pd.DataFrame()
        units = ""
        for stype in (SA, TREND):
            frame[stype], units = _selected(release, APPROVALS_TABLE, did, stype)
        frame, units = _recalibrated(frame, units)
        title = f"Building Approvals Australia: {label}"
        multi_start(
            frame,
            function=seastrend_plot_finalise,
            starts=_plot_times(release),
            title=title,
            ylabel=f"{units} of residential dwellings / month",
            rfooter=release.source,
            lfooter="Australia. ",
            rounding=1,
        )
        multi_start(
            frame[SA],
            function=series_growth_plot_finalise,
            starts=monthly_plot_times,
            plot_from=monthly_plot_times[1],
            title=title,
            rfooter=release.source,
            lfooter=f"Australia. {SERIES_TYPE_NOTES[SA]}",
            tag="growth",
            bar_rounding=1,
        )


def approvals_by_state(release: AbsRelease) -> None:
    """Chart approvals by state: counts, share of the dwelling stock, per 100,000 people, per adult growth."""
    approvals = pd.DataFrame(
        {
            state: _selected(
                release,
                STATE_TABLE,
                f"Total number of dwelling units ;  Total (Type of Building) ;  {state} ;",
                ORIGINAL,
            )[0]
            for state in mg.state_names
        }
    )
    latest_period = approvals.index[-1]
    latest_month = approvals.iloc[-1]
    latest_12m = approvals.iloc[-MONTHS_PER_YEAR:].sum()

    stock_data, stock_meta = ra.read_abs_cat(STOCK_CATALOGUE, single_excel_only=STOCK_TABLE)
    stock, stock_period = {}, None
    for state in mg.state_names:
        _table, series_id, _units = ra.find_abs_id(
            stock_meta, {f"Number of residential dwellings ;  {state} ;": mc.did, STOCK_TABLE: mc.table}
        )
        series = stock_data[STOCK_TABLE][series_id].dropna() * THOUSAND
        stock[state], stock_period = series.iloc[-1], series.index[-1]
    stock_by_state = pd.Series(stock)

    population, pop_period = {}, None
    for state in mg.state_names:
        series = get_state_erp(state)[0].dropna()
        population[state], pop_period = series.iloc[-1], series.index[-1]
    population_by_state = pd.Series(population)

    # adult (15+) population growth over 12 months, from the per-state 6202.0 tables
    lf_data, lf_meta = ra.read_abs_cat(LFS_CATALOGUE, selected_excel=LFS_STATE_TABLES)
    state_tables = {}
    for table, row in lf_meta.drop_duplicates("Table").set_index("Table").iterrows():
        if str(table).endswith("a"):
            continue
        description = str(row["Table Description"])
        for state in mg.state_names:
            if f", {state} -" in description:
                state_tables[state] = str(table)
                break
    adult_growth, adult_period = {}, None
    for state in mg.state_names:
        table = state_tables[state]
        _table, series_id, _units = ra.find_abs_id(
            lf_meta, {CIV_POP_DID: mc.did, table: mc.table, ORIGINAL: mc.stype}
        )
        series = lf_data[table][series_id].dropna() * THOUSAND
        adult_growth[state], adult_period = series.iloc[-1] - series.iloc[-MONTHS_PER_YEAR - 1], series.index[-1]
    adult_growth_by_state = pd.Series(adult_growth)

    source = release.source
    approvals_footer = source
    latest_month_cal, units_month = _recalibrated(latest_month, "Number")
    _hbar(
        latest_month_cal,
        f"Building Approvals by State: {latest_period}",
        f"{units_month} of residential dwelling units",
        rounding=True,
        rfooter=approvals_footer,
    )
    latest_12m_cal, units_12m = _recalibrated(latest_12m, "Number")
    _hbar(
        latest_12m_cal,
        f"Building Approvals by State: 12 months to {latest_period}",
        f"{units_12m} of residential dwelling units",
        rounding=True,
        rfooter=approvals_footer,
    )
    stock_footer = "ABS: 6432.0, 8731.0"
    _hbar(
        latest_month / stock_by_state * PERCENT,
        f"Building Approvals by State as % of Dwelling Stock: {latest_period}",
        f"Per cent of residential dwelling stock (stock at {stock_period})",
        rounding=3,
        rfooter=stock_footer,
    )
    _hbar(
        latest_12m / stock_by_state * PERCENT,
        f"Building Approvals by State as % of Dwelling Stock: 12 months to {latest_period}",
        f"Per cent of residential dwelling stock (stock at {stock_period})",
        rounding=2,
        rfooter=stock_footer,
    )
    pop_footer = "ABS: 3101.0, 8731.0"
    _hbar(
        latest_month / population_by_state * PER_100K,
        f"Building Approvals by State per 100,000 Population: {latest_period}",
        f"Residential approvals per 100,000 people (population at {pop_period})",
        rounding=1,
        rfooter=pop_footer,
    )
    _hbar(
        latest_12m / population_by_state * PER_100K,
        f"Building Approvals by State per 100,000 Population: 12 months to {latest_period}",
        f"Residential approvals per 100,000 people (population at {pop_period})",
        rounding=0,
        rfooter=pop_footer,
    )
    _hbar(
        latest_12m / adult_growth_by_state * PERCENT,
        f"Approvals (12 months) as % of Adult Population Growth: {latest_period}",
        f"Residential approvals as % of 15+ civilian population growth (12 months to {adult_period})",
        rounding=1,
        rfooter=WITH_LFS_SOURCE,
    )


def approvals_vs_civpop(release: AbsRelease) -> None:
    """Chart approvals per 1,000 adults, per new adult, and per new adult clipped past the COVID spike."""
    approvals = _selected(release, APPROVALS_TABLE, TOTAL_DID, SA)[0].dropna()
    civpop = _civ_pop_national()
    common_index = approvals.index.intersection(civpop.index)
    approvals, civpop = approvals.loc[common_index], civpop.loc[common_index]

    common: dict[str, Any] = {
        "function": line_plot_finalise,
        "starts": [0, POST_COVID_START],
        "rfooter": WITH_LFS_SOURCE,
        "lfooter": "Australia. Approvals seasonally adjusted. Civilian population original. ",
        "annotate": True,
        "rounding": 2,
    }
    multi_start(
        approvals / civpop * THOUSAND,
        title="Building Approvals per 1,000 Civilian Population (15+)",
        ylabel="Monthly residential approvals / 1,000 adults",
        **common,
    )
    ratio = (approvals / ((civpop - civpop.shift(MONTHS_PER_YEAR)) / MONTHS_PER_YEAR)).dropna()
    ratio.name = "Approvals per monthly population growth aged 15+"
    common["lfooter"] += " Monthly civilian population growth is a 12m rolling average."
    multi_start(
        ratio,
        title="Building Approvals per New Person Aged 15+ Years",
        ylabel="Monthly residential approvals /\nmonthly growth in 15+ population",
        **common,
    )
    line_plot_finalise(
        ratio,
        title="Building Approvals per New Person Aged 15+ Years",
        ylabel="Monthly residential approvals /\nmonthly growth in 15+ population",
        ylim=CLIPPED_YLIM,
        axvspan=COVID_SPAN,
        legend=LEGEND,
        **{key: value for key, value in common.items() if key not in ("function", "starts")},
    )


def approvals_models(release: AbsRelease) -> None:
    """Fit and chart the quarterly approvals model for total dwellings and houses."""
    dur12 = _dur12()
    for did, label, tag in ((TOTAL_DID, "Total dwellings", "total"), (HOUSES_DID, "Houses", "houses")):
        approvals = _to_quarterly(_selected(release, APPROVALS_TABLE, did, SA)[0].dropna(), "sum")
        model = _fit_model(approvals, dur12, label)
        _plot_model(model, approvals, dur12, label=label, tag=tag)


def value_nominal(release: AbsRelease) -> None:
    """Chart the nominal value of building approved (monthly): residential and non-residential."""
    starts = _plot_times(release)
    prefix = "Building Approvals Australia: Value"
    _value_seastrend(
        release,
        VALUE_TABLE,
        NOMINAL_COMPONENTS,
        starts=starts,
        title_prefix=prefix,
        note=NOMINAL_NOTE,
        period_label="month",
    )
    _value_trend_comparison(
        release,
        VALUE_TABLE,
        NOMINAL_COMPONENTS,
        starts=starts,
        title="Building Approvals Australia: Value, Residential and Non-residential",
        note=NOMINAL_NOTE,
        period_label="month",
    )


def value_volume(release: AbsRelease) -> None:
    """Chart the volume of building approved (quarterly, chain volume measures)."""
    starts = quarterly_plot_times
    prefix = "Building Approvals Australia: Volume (CVM)"
    _value_seastrend(
        release,
        CVM_TABLE,
        CVM_COMPONENTS,
        starts=starts,
        title_prefix=prefix,
        note=CVM_NOTE,
        period_label="quarter",
    )
    _value_trend_comparison(
        release,
        CVM_TABLE,
        CVM_COMPONENTS,
        starts=starts,
        title="Building Approvals Australia: Volume (CVM), Residential and Non-residential",
        note=CVM_NOTE,
        period_label="quarter",
    )


def value_share_of_gdp(release: AbsRelease) -> None:
    """Chart the value of building approved as a per cent of nominal GDP (quarterly, SA, current prices)."""
    gdp, gdp_units = get_gdp("CP", "SA")
    if gdp_units != "$ Millions":
        raise ValueError(f"Unexpected GDP units: {gdp_units}")
    frame = pd.DataFrame()
    for did, label in NOMINAL_COMPONENTS:
        monthly, units = _building_value(release, VALUE_TABLE, did, SA)
        if units != "$'000":
            raise ValueError(f"Unexpected approvals units: {units}")
        frame[label] = _to_quarterly(monthly, "sum") / THOUSAND / gdp * PERCENT
    multi_start(
        frame.dropna(),
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title="Building Approvals: Value as a Share of GDP",
        ylabel="Per cent of nominal GDP",
        rfooter="ABS: 5206.0, 8731.0",
        lfooter="Australia. Seasonally adjusted, quarterly. Approvals and GDP both in current prices. ",
        rounding=2,
    )


# --- table of contents, in run order
CHARTS = (
    (building_approvals, ()),
    (approvals_by_state, ()),
    (approvals_vs_civpop, ()),
    (approvals_models, ()),
    (value_nominal, ()),
    (value_volume, ()),
    (value_share_of_gdp, ()),
)
