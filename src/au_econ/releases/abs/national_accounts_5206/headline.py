"""National Accounts headline charts: the summary, the basic series set, demand, growth, income and shares."""

# --- dependencies
import textwrap
from typing import TYPE_CHECKING, Any

import mgplot as mg
import numpy as np
import pandas as pd
import readabs as ra
from mgplot import (
    finalise_plot,
    line_plot_finalise,
    multi_start,
    postcovid_plot_finalise,
    series_growth_plot_finalise,
    state_abbrs,
    state_names,
    summary_plot_finalise,
)
from readabs import metacol as mc

from au_econ.analysis.henderson import hma
from au_econ.charting.footers import SERIES_TYPE_NOTES
from au_econ.charting.windows import quarterly_plot_times
from au_econ.releases.abs.national_accounts_5206.common import (
    ANALYTICAL,
    AUSTRALIA,
    CAPITAL_ACCOUNT,
    CP,
    CP_NOTE,
    CVM,
    CVM_NOTE,
    DEFLATORS,
    EXPENDITURE_CP,
    EXPENDITURE_VOLUME,
    HFCE_TABLE,
    HOUSEHOLD_INCOME,
    INCOME_FROM_GDP,
    INDEX_NUMBERS,
    INDUSTRY_GVA,
    KEY_AGGS,
    MILLIONS,
    NFC_INCOME,
    ORIGINAL,
    ORIGINAL_NOTE,
    QUARTERS_PER_YEAR,
    SA_NOTE,
    SEASONALLY_ADJUSTED,
    SFD_SUMMARY,
    TAXES,
    data_to,
    fix_abs_title,
)
from au_econ.series.gdp import get_gdp
from au_econ.series.population import get_state_erp

if TYPE_CHECKING:
    from au_econ.sources.abs import AbsRelease

# --- constants
PERCENT = 100
SA = SEASONALLY_ADJUSTED  # short name, to keep the tables below readable

# summary: (chart label, metadata selector, growth periods), least important first (plots bottom to top)
HFCE_DID = "Households ;  Final consumption expenditure ;"
SUMMARY_FROM = pd.Period("1995Q1", freq="Q")
SUMMARY = (
    (
        "Households price deflator",
        {DEFLATORS: mc.table, HFCE_DID: mc.did, SA: mc.stype, INDEX_NUMBERS: mc.unit},
        (1, 4),
    ),
    (
        "GNE price deflator",
        {DEFLATORS: mc.table, "Gross national expenditure ;": mc.did, SA: mc.stype, INDEX_NUMBERS: mc.unit},
        (1, 4),
    ),
    (
        "Household saving ratio",
        {KEY_AGGS: mc.table, "Household saving ratio: Ratio ;": mc.did, SA: mc.stype, "proportion": mc.unit},
        (0,),
    ),
    (
        "GDP per Hour Worked",
        {KEY_AGGS: mc.table, "GDP per hour worked: Index ;": mc.did, SA: mc.stype, INDEX_NUMBERS: mc.unit},
        (1, 4),
    ),
    (
        "Hours Worked",
        {KEY_AGGS: mc.table, "Hours worked: Index ;": mc.did, SA: mc.stype, INDEX_NUMBERS: mc.unit},
        (1, 4),
    ),
    (
        "Household consumption",
        {EXPENDITURE_VOLUME: mc.table, HFCE_DID: mc.did, SA: mc.stype, MILLIONS: mc.unit},
        (1, 4),
    ),
    (
        "GVA market sector",
        {
            KEY_AGGS: mc.table,
            "Gross value added market sector: Chain volume measures ;": mc.did,
            SA: mc.stype,
            MILLIONS: mc.unit,
        },
        (1, 4),
    ),
    (
        "GDP/Capita",
        {KEY_AGGS: mc.table, "GDP per capita: Chain volume measures ;": mc.did, SA: mc.stype, "$": mc.unit},
        (1, 4),
    ),
    (
        "GDP",
        {
            KEY_AGGS: mc.table,
            "Gross domestic product: Chain volume measures ;": mc.did,
            SA: mc.stype,
            MILLIONS: mc.unit,
        },
        (1, 4),
    ),
)

# basic charts: every key-aggregate CVM series, plus these (description, series type, table)
BASIC_EXTRA = (
    ("GDP per hour worked: Index ;", SA, KEY_AGGS),
    ("Gross value added per hour worked market sector: Index ;", SA, KEY_AGGS),
    ("Terms of trade: Index ;", SA, KEY_AGGS),
    ("Public ;  Final demand: Chain volume measures ;", SA, ANALYTICAL),
    ("Private ;  Final demand: Chain volume measures ;", SA, ANALYTICAL),
    ("Households ;  Final consumption expenditure - Goods: Chain volume measures ;", SA, ANALYTICAL),
    ("Households ;  Final consumption expenditure - Services: Chain volume measures ;", SA, ANALYTICAL),
    (
        "Households ;  Final consumption expenditure - Essential consumption: Chain volume measures ;",
        SA,
        ANALYTICAL,
    ),
    (
        "Households ;  Final consumption expenditure - Discretionary consumption: Chain volume measures ;",
        SA,
        ANALYTICAL,
    ),
    ("Compensation of employees per hour: Current prices ;", SA, ANALYTICAL),
    ("Non-farm compensation of employees per hour: Current prices ;", SA, ANALYTICAL),
    ("Gross fixed capital formation - New private business investment: Chain volume measures ;", SA, ANALYTICAL),
)
BASIC_TITLE_WIDTH = 65
CVM_INDEXES = (  # ABS indexes of chain volume output: their descriptions name no price measure
    "GDP per hour worked: Index ;",
    "Gross value added per hour worked market sector: Index ;",
)
BASIC_GROWTH_YEARS = (1, 10)  # annual growth, and compound annual growth over a decade
LONG_RUN_YEARS = 10  # horizons this long or longer are smoothed
LONG_RUN_HENDERSON = 9

# long-run growth
LONG_RUN_CHARTS = ("Gross domestic product", "GDP per capita")
LONG_RUN_TERMS = 13
DECADE_YEARS = 10

# trend growth
TREND_TERMS = 9
trend_starts = 0, -60

# public final demand share
PUBLIC_SHARE_FROM = pd.Period("2022Q1", freq="Q")

# state final demand
STATE_AREAS_KM2 = {
    "New South Wales": 809_952,
    "Victoria": 237_657,
    "Queensland": 1_851_736,
    "South Australia": 1_044_353,
    "Western Australia": 2_642_753,
    "Tasmania": 90_758,
    "Northern Territory": 1_420_970,
    "Australian Capital Territory": 2_358,
}
SFD_DID = ";  STATE FINAL DEMAND ;"
SMALLEST_TERRITORY = "ACT"  # dropped for the second chart, so the states can be compared

# household income and taxes
HOUSEHOLD_ITEMS = ("GROSS DISPOSABLE INCOME", "TOTAL GROSS INCOME")
INCOME_TAX_DID = "Taxes on income - Individuals - Total"
HFCE_TOTAL = "FINAL CONSUMPTION EXPENDITURE"

# profits
PROFIT_SHARE_DID = "Profits share of total factor income: Ratio ;"
COE_DID = "Compensation of employees ;"
PROFITS_TERMS = 7
THOUSAND = 1000

# market and non-market sector shares of GVA
GVA_TOTAL_DID = "Gross value added at basic prices ;"
GVA_SECTOR_DIDS = {
    "Market sector": ("Gross value added market sector: Chain volume measures ;", KEY_AGGS),
    "Non-market sector": ("Gross value added non-market sector: Chain volume measures ;", KEY_AGGS),
    "Ownership of dwellings": ("Ownership of dwellings ;", INDUSTRY_GVA),
}
# Chain volume measures are additive only from the reference year, so the three sectors sum
# to a little either side of published GVA (within +/-1.3 ppt, exactly from 2021Q1).
GVA_SHARE_TOLERANCE = 2.0  # ppt: how far the shares may stray from summing to 100

# business investment against corporate earnings
PRIVATE_GFCF_DID = "Private ;  Gross fixed capital formation ;"
DWELLINGS_GFCF_DID = "Private ;  Gross fixed capital formation - Dwellings - Total ;"
NFC_SURPLUS_DID = "Gross operating surplus ;"
NFC_DEPRECIATION_DID = "Consumption of fixed capital ;"

# labour share
GDP_CP_DID = "Gross domestic product: Current prices ;"


# --- helpers
def _get(release: AbsRelease, did: str, table: str) -> pd.Series:
    """Return a seasonally adjusted $ Millions series by description, or raise if it is empty."""
    _table, series_id, _units = ra.find_abs_id(
        release.meta, {did: mc.did, SA: mc.stype, MILLIONS: mc.unit, table: mc.table}
    )
    series = release.data[table][series_id].dropna()
    if series.empty:
        raise ValueError(f"No data returned for '{did}' in {table}")
    return series


def _tdesc_series(release: AbsRelease, table: str, item: str) -> pd.Series:
    """Return the first seasonally adjusted current price series in a table whose description has item."""
    meta = release.meta
    rows = meta[
        (meta[mc.table] == table)
        & (meta[mc.stype] == SA)
        & (meta[mc.did].str.contains(item))
        & (meta[mc.tdesc].str.contains(CP))
    ]
    if rows.empty:
        raise ValueError(f"No {item} series in {table}")
    return release.data[table][rows[mc.id].iloc[0]]


def _basic_wanted(release: AbsRelease) -> dict[str, dict[str, str]]:
    """Return the basic chart items, {description: {"table", "stype", "did"}}."""
    meta = release.meta
    key_cvm = meta.loc[
        (meta[mc.stype] == SA)
        & meta[mc.did].str.contains(CVM)
        & ~meta[mc.did].str.contains("Percentage")
        & (meta[mc.table] == KEY_AGGS),
        mc.did,
    ].tolist()
    wanted = {did: {"table": KEY_AGGS, "stype": SA, "did": did} for did in key_cvm}
    return wanted | {did: {"did": did, "stype": stype, "table": table} for did, stype, table in BASIC_EXTRA}


def _sfd(release: AbsRelease) -> tuple[str, pd.DataFrame]:
    """Return the State Final Demand units and data, one column per state."""
    rows = ra.search_abs_meta(release.meta, {SFD_SUMMARY: mc.table, SFD_DID: mc.did, SA: mc.stype})
    data = release.data[SFD_SUMMARY][rows[mc.id]].rename_axis("Quarter")
    data.columns = rows[mc.did].str.replace(SFD_DID, "").str.strip().tolist()
    return rows[mc.unit].iloc[0], data


# --- charts
def summary(release: AbsRelease) -> None:
    """Key GDP statistics, as z-scores and z-scaled, for the latest quarter."""
    frame = pd.DataFrame()
    for label, selector, periods in SUMMARY:
        table, series_id, _units = ra.find_abs_id(release.meta, selector)
        for n in periods:
            series = release.data[table][series_id]
            if n:
                series = series.pct_change(periods=n, fill_method=None) * PERCENT
            frame[f"{n}Q growth: {label}" if n else label] = series
    summary_plot_finalise(
        frame,
        plot_from=SUMMARY_FROM,
        title=f"Key GDP statistics {release.data[KEY_AGGS].index[-1]}",
        rfooter=release.source,
        lfooter=f"{AUSTRALIA}{SA_NOTE}All values are percentages. ",
        pre_tag="summary-",
    )


def basic(release: AbsRelease) -> None:
    """For each core series: the level, its COVID recovery, its growth, and its decade compound growth."""
    wrap = textwrap.TextWrapper(width=BASIC_TITLE_WIDTH)
    data, data_meta = ra.read_abs_by_desc(
        wanted=_basic_wanted(release), abs_dict=release.data, abs_meta=release.meta
    )
    for did_label, raw_series in data.items():
        raw_units = data_meta.at[raw_series.name, mc.unit]  # the series name is its ABS series ID
        if not isinstance(raw_units, str):
            raise TypeError(f"Expected a unit string for {did_label}, got {type(raw_units).__name__}")
        series, units = ra.recalibrate(raw_series, raw_units)
        stype = data_meta.at[series.name, mc.stype]
        if not isinstance(stype, str):
            raise TypeError(f"Expected a series type string for {did_label}, got {type(stype).__name__}")
        measure = CVM_NOTE if did_label in CVM_INDEXES else ""
        title, lfooter = fix_abs_title(did_label, f"{AUSTRALIA}{SERIES_TYPE_NOTES[stype]} {measure}")
        ylabel = f"{units}{' / Quarter' if 'hour' not in title and 'Index' not in title else ''}"
        common: dict[str, Any] = {
            "y0": True,
            "lfooter": f"{lfooter}{data_to(series)}",
            "rfooter": release.source,
        }
        multi_start(
            series,
            function=line_plot_finalise,
            starts=quarterly_plot_times,
            dropna=True,
            title=wrap.fill(title),
            ylabel=ylabel,
            pre_tag="basic-as-is-",
            annotate=True,
            **common,
        )
        postcovid_plot_finalise(
            series,
            dropna=True,
            title=wrap.fill(title),
            ylabel=ylabel,
            pre_tag="basic-covid-",
            annotate=[False, True],
            **common,
        )
        multi_start(
            series,
            starts=quarterly_plot_times,
            function=series_growth_plot_finalise,
            title=wrap.fill(f"{title} growth" if ":" in title else f"{title}: growth"),
            pre_tag="basic-growth-",
            annotate_line=True,
            **common,
        )

        growth = pd.DataFrame()
        for years in BASIC_GROWTH_YEARS:
            post = ""
            n_growth = ((series / series.shift(periods=years * QUARTERS_PER_YEAR)) ** (1 / years) - 1) * PERCENT
            if years >= LONG_RUN_YEARS:
                n_growth = hma(n_growth.dropna(), LONG_RUN_HENDERSON)
                post = f" ({LONG_RUN_HENDERSON}-term HMA)"
            pre = "" if years == 1 else f"{years}-year compound "
            growth[f"{pre}annual growth rate".capitalize() + post] = n_growth
        longest = max(BASIC_GROWTH_YEARS)
        line_plot_finalise(
            growth,
            title=wrap.fill(f"{longest}-year Growth: {title}"),
            ylabel="Per cent growth",
            legend={"loc": "best", "fontsize": 9},
            width=[1, 3],
            annotate=[False, True],
            pre_tag=f"basic-growth-{longest}-year",
            **common,
        )


def final_demand(release: AbsRelease) -> None:
    """Public and private final demand: through-the-year growth, and the public share of nominal GDP."""
    growth = pd.DataFrame()
    for sector in ("Public", "Private"):
        _, series_id, _ = ra.find_abs_id(
            release.meta,
            {ANALYTICAL: mc.table, SA: mc.stype, f"{sector} ;  Final demand: Chain volume measures ;": mc.did},
        )
        series = release.data[ANALYTICAL][series_id].dropna()
        if series.empty:
            raise ValueError(f"No data for {sector} final demand")
        growth[f"{sector} final demand"] = (series / series.shift(QUARTERS_PER_YEAR) - 1) * PERCENT
    growth = growth.dropna()
    multi_start(
        growth,
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title="Final Demand: Through the Year Growth",
        ylabel="Per cent",
        y0=True,
        annotate=True,
        rfooter=release.source,
        lfooter=f"{AUSTRALIA}{SA_NOTE}{CVM_NOTE}{data_to(growth)}",
        pre_tag="demand-sector-",
    )

    _, series_id, units = ra.find_abs_id(
        release.meta, {ANALYTICAL: mc.table, SA: mc.stype, "Public ;  Final demand: Current prices ;": mc.did}
    )
    public = release.data[ANALYTICAL][series_id].dropna()
    gdp, gdp_units = get_gdp("CP", "SA")
    if public.empty or gdp.empty:
        raise ValueError("No data for public final demand or nominal GDP")
    if units != gdp_units:
        raise ValueError(f"Unit mismatch: {units} vs {gdp_units}")
    share = (public / gdp * PERCENT).dropna()
    share.name = "Public final demand share of GDP"
    multi_start(
        share,
        function=line_plot_finalise,
        starts=(*quarterly_plot_times, PUBLIC_SHARE_FROM),
        title="Public Final Demand: Share of Nominal GDP",
        ylabel="Per cent of GDP",
        annotate=True,
        rfooter=release.source,
        lfooter=f"{AUSTRALIA}{SA_NOTE}{CP_NOTE}{data_to(share)}",
        pre_tag="demand-sector-",
    )


def long_run_growth(release: AbsRelease) -> None:
    """GDP and GDP per capita: annual growth, its Henderson trend, decade means and decade compound growth."""
    data = release.data[KEY_AGGS]
    for chart in LONG_RUN_CHARTS:
        selector = {KEY_AGGS: mc.table, chart: mc.did, SA: mc.stype, CVM: mc.did, "$": mc.unit}
        _table, series_id, _units = ra.find_abs_id(release.meta, selector, verbose=False)
        q_gdp = data[series_id].dropna()
        series = (q_gdp.pct_change(periods=QUARTERS_PER_YEAR) * PERCENT).dropna()
        lines = pd.DataFrame(
            {
                "Annual growth": series,
                f"{LONG_RUN_TERMS}-term Henderson moving average": hma(series, LONG_RUN_TERMS),
            }
        )
        ax = mg.line_plot(lines, color=["darkblue", "darkorange"], width=[0.5, 1.5])

        index = series.index
        if not isinstance(index, pd.PeriodIndex):
            raise TypeError(f"Expected a PeriodIndex for {chart}, got {type(index).__name__}")
        decade_of = index.year.astype(str).str[2:3]
        label = "Decadal mean (DM) annual growth"
        for decade in decade_of.unique():
            subset = series[decade_of == decade]
            d_series = pd.Series(np.repeat(subset.mean(), len(subset)), index=pd.PeriodIndex(subset.index))
            d_series.name = label  # matplotlib hides "_no_legend_" labels
            mg.line_plot(d_series, ax=ax, color=["darkred"], width=2, style="--")
            label = "_no_legend_"
            ax.text(
                x=d_series.index[-1].ordinal,  # mgplot maps a PeriodIndex to period ordinals on the x-axis
                y=series.min(),
                s=f"DM = {d_series.iloc[-1]:0.2f}%",
                rotation=90,
                ha="center",
                size="x-small",
            )

        annual = ((q_gdp / q_gdp.shift(DECADE_YEARS * QUARTERS_PER_YEAR)) ** (1 / DECADE_YEARS) - 1) * PERCENT
        annual.name = "Annual compound growth over decade"
        mg.line_plot(annual, ax=ax, color=["dodgerblue"], width=3)
        finalise_plot(
            ax,
            title=f"Long-run YoY Growth: {chart}",
            ylabel="Per cent / year",
            legend={"loc": "best", "fontsize": "x-small"},
            rfooter=release.source,
            lfooter=f"{AUSTRALIA}{SA_NOTE}{CVM_NOTE}Compared with the same quarter in the previous year. "
            f"{data_to(series)}",
            pre_tag="long-run-growth-",
            y0=True,
        )


def trend_growth(release: AbsRelease) -> None:
    """Nominal and real GDP growth, from a Henderson trend of the seasonally adjusted series."""
    data = release.data[KEY_AGGS]
    growth = {}
    for price_type, label in ((CP, "Nominal"), (CVM, "Real")):
        selector = {
            KEY_AGGS: mc.table,
            "Gross domestic product": mc.did,
            SA: mc.stype,
            price_type: mc.did,
            "$": mc.unit,
        }
        _table, series_id, _units = ra.find_abs_id(release.meta, selector, verbose=False)
        trend = hma(data[series_id].dropna(), TREND_TERMS)
        growth[label] = (trend.pct_change(periods=QUARTERS_PER_YEAR) * PERCENT).dropna()
    frame = pd.DataFrame(growth)
    multi_start(
        frame,
        function=line_plot_finalise,
        starts=trend_starts,
        title="Trend GDP Growth: Nominal vs Real",
        ylabel="Per cent / year",
        rfooter=release.source,
        lfooter=f"{AUSTRALIA}{SA_NOTE}{TREND_TERMS}-term HMA trend. Year-on-year growth. {data_to(frame)}",
        pre_tag="gdp-trend-growth-",
        y0=True,
        annotate=True,
        legend={"loc": "best", "fontsize": 9},
    )


def rolling_totals(release: AbsRelease) -> None:
    """GDP and GDP per capita, original series, as four-quarter rolling sums against the pre-COVID path."""
    data = release.data[KEY_AGGS]
    for chart in LONG_RUN_CHARTS:
        selector = {KEY_AGGS: mc.table, chart: mc.did, ORIGINAL: mc.stype, CVM: mc.did, "$": mc.unit}
        _table, series_id, units = ra.find_abs_id(release.meta, selector, verbose=False)
        rolling_4q, units = ra.recalibrate(data[series_id].rolling(QUARTERS_PER_YEAR).sum(), units)
        rolling_4q.name = chart
        did = release.meta.loc[release.meta[mc.id] == series_id, mc.did].iloc[0]
        title, lfooter = fix_abs_title(did, f"{AUSTRALIA}{ORIGINAL_NOTE}4Q rolling sum. ")
        postcovid_plot_finalise(
            rolling_4q,
            title=f"4Q rolling sum: {title}",
            ylabel=f"{units} / year",
            tag="covid-annual",
            rfooter=release.source,
            lfooter=f"{lfooter}{data_to(rolling_4q)}",
            pre_tag="4Qrolling-",
            annotate=[False, True],
        )


def implicit_population(release: AbsRelease) -> None:
    """Chart the population implied by nominal GDP over nominal GDP per capita: level and growth."""
    data = release.data[KEY_AGGS]
    series = {}
    for did in ("GDP per capita: Current prices ;", GDP_CP_DID):
        _table, series_id, _units = ra.find_abs_id(
            release.meta, {KEY_AGGS: mc.table, ORIGINAL: mc.stype, did: mc.did}
        )
        series[did] = data[series_id]
    population = (series[GDP_CP_DID] / series["GDP per capita: Current prices ;"]).dropna()
    population.name = "Australian population"
    print(population.index[0], population.index[-1])

    title = "Implicit population from ABS National Accounts"
    common: dict[str, Any] = {
        "rfooter": release.source,
        "lfooter": f"{AUSTRALIA}{ORIGINAL_NOTE}{CP_NOTE}GDP / GDP per capita. {data_to(population)}",
        "pre_tag": "population-",
    }
    postcovid_plot_finalise(
        population,
        title=title,
        ylabel="Millions",
        tag="population-covid",
        annotate=[False, True],
        **common,
    )
    multi_start(
        data=population,
        function=series_growth_plot_finalise,
        starts=quarterly_plot_times,
        title=title,
        tag="population-growth",
        **common,
    )


def state_final_demand(release: AbsRelease) -> None:
    """State Final Demand in the latest quarter, per km² (with and without the ACT) and per person."""
    sfd_units, sfd_data = _sfd(release)

    # per km²
    areas = pd.Series(STATE_AREAS_KM2, name="Area (km²)")
    per_area = sfd_data.div(areas, axis="columns").iloc[-1]
    state_map = dict(zip(state_names, state_abbrs, strict=True))
    per_area.index = [state_map[s] for s in per_area.index]
    units = sfd_units
    for loop in (0, 1):
        per_area, units = ra.recalibrate(per_area, units)
        per_area = per_area.sort_values()
        mg.bar_plot_finalise(
            per_area,
            horizontal=True,
            color=[mg.get_color(s) for s in per_area.index],
            annotate=True,
            above=True,
            title="State Final Demand per km², Latest Quarter",
            xlabel=units,
            rfooter=release.source,
            tag=str(loop),
            lfooter=f"{AUSTRALIA}{SA_NOTE}{CVM_NOTE}SFD at {sfd_data.index[-1]}.",
        )
        if SMALLEST_TERRITORY in per_area.index:
            per_area = per_area.drop(SMALLEST_TERRITORY)

    # per person
    state_pops = pd.DataFrame({state: get_state_erp(state)[0] for state in state_names})
    recent_pop, recent_pop_date = state_pops.iloc[-1], state_pops.index[-1]
    per_capita, pc_units = ra.recalibrate(sfd_data.iloc[-1].div(recent_pop), sfd_units)
    per_capita = per_capita.sort_values()
    mg.bar_plot_finalise(
        per_capita,
        horizontal=True,
        color=[mg.get_color(s) for s in per_capita.index],
        annotate=True,
        above=True,
        title="State Final Demand per Capita, Latest Quarter",
        xlabel=pc_units,
        rfooter=release.source,
        lfooter=f"{AUSTRALIA}{SA_NOTE}{CVM_NOTE}SFD at {sfd_data.index[-1]}. Population at {recent_pop_date}.",
    )


def hfce_share(release: AbsRelease) -> None:
    """Household final consumption expenditure as a share of GDP (chain volume measures)."""
    meta = release.meta
    rows = meta[
        (meta[mc.table] == HFCE_TABLE)
        & (meta[mc.stype] == SA)
        & (meta[mc.unit] == MILLIONS)
        & meta[mc.did].str.contains(CVM)
        & meta[mc.did].str.contains(HFCE_TOTAL)
    ]
    if rows.empty:
        raise ValueError(f"No total household consumption series in {HFCE_TABLE}")
    hfce = release.data[HFCE_TABLE][rows[mc.id].iloc[-1]].dropna()
    hfce_units = rows[mc.unit].iloc[-1]
    gdp, gdp_units = get_gdp("CVM", "SA")
    if gdp_units.strip().lower() != hfce_units.strip().lower():
        raise ValueError(f"HFCE and GDP units do not match: {hfce_units} != {gdp_units}")
    share = hfce / gdp * PERCENT
    line_plot_finalise(
        share,
        title="HFCE as a proportion of GDP",
        ylabel="Per cent",
        rfooter=release.source,
        lfooter=f"{AUSTRALIA}{SA_NOTE}{CVM_NOTE}HFCE = household final consumption expenditure. {data_to(share)}",
        pre_tag="hfce-",
        annotate=True,
    )


def household_income(release: AbsRelease) -> None:
    """Household gross disposable income as a share of total gross income."""
    disposable, total = (_tdesc_series(release, HOUSEHOLD_INCOME, item) for item in HOUSEHOLD_ITEMS)
    share = disposable / total * PERCENT
    multi_start(
        share,
        starts=quarterly_plot_times,
        function=line_plot_finalise,
        annotate=True,
        title=f"Households: {' / '.join(HOUSEHOLD_ITEMS).title()}",
        ylabel="Per cent",
        rfooter=release.source,
        lfooter=f"{AUSTRALIA}{SA_NOTE}{CP_NOTE}{data_to(share)}",
        pre_tag="household_income-",
    )


def income_tax_share(release: AbsRelease) -> None:
    """Gross individual income tax as a share of gross household income."""
    gross_income = _tdesc_series(release, HOUSEHOLD_INCOME, "TOTAL GROSS INCOME")
    income_tax = _tdesc_series(release, TAXES, INCOME_TAX_DID)
    share = income_tax / gross_income * PERCENT
    multi_start(
        share,
        starts=quarterly_plot_times,
        function=line_plot_finalise,
        title="Gross Individual Income Tax / Gross Household Income",
        ylabel="Per cent",
        rfooter=release.source,
        lfooter=f"{AUSTRALIA}{SA_NOTE}{CP_NOTE}{data_to(share)}",
        pre_tag="taxes-",
        annotate=True,
    )


def profits(release: AbsRelease) -> None:
    """Profits against wages: the profit share, the levels, and both indexed to their first quarter."""
    _table, wages_id, wage_units = ra.find_abs_id(
        release.meta,
        {INCOME_FROM_GDP: mc.table, SA: mc.stype, COE_DID: mc.did},
        exact_match=True,
        verbose=False,
    )
    wages = release.data[INCOME_FROM_GDP][wages_id]
    _table, tf_income_id, tf_income_units = ra.find_abs_id(
        release.meta,
        {INCOME_FROM_GDP: mc.table, SA: mc.stype, "Total factor income ;": mc.did},
        exact_match=True,
        verbose=False,
    )
    tf_income = release.data[INCOME_FROM_GDP][tf_income_id]
    if wage_units != tf_income_units:
        raise ValueError(f"Wages and total factor income units differ: {wage_units} vs {tf_income_units}")
    _table, profit_ratio_id, _share_units = ra.find_abs_id(
        release.meta,
        {ANALYTICAL: mc.table, SA: mc.stype, PROFIT_SHARE_DID: mc.did},
        exact_match=True,
        verbose=False,
    )
    profit = release.data[ANALYTICAL][profit_ratio_id] / PERCENT * tf_income
    rfooter = release.source

    share = profit / (profit + wages) * PERCENT
    lfooter = f"{AUSTRALIA}{SA_NOTE}{CP_NOTE}"
    ends = data_to(share)
    line_plot_finalise(
        pd.DataFrame({"Profit share": share, "Henderson moving average": hma(share, PROFITS_TERMS)}),
        width=[1, 3],
        annotate=[False, True],
        title="Profits as a share of profits plus wages",
        ylabel="Per cent",
        rfooter=rfooter,
        lfooter=f"{lfooter}{PROFITS_TERMS}-term Henderson moving average. {ends}",
        pre_tag="profits-",
    )

    if "Millions" not in wage_units:
        raise ValueError(f"Expected wages in millions, got {wage_units}")
    line_plot_finalise(
        pd.DataFrame({"Wages": wages / THOUSAND, "Profits": profit / THOUSAND}),
        title="Profits vs Wages",
        ylabel="$ Billions",
        rfooter=rfooter,
        lfooter=f"{lfooter}{ends}",
        pre_tag="profits-",
        annotate=True,
    )

    if wages.index[0] != profit.index[0]:
        raise ValueError("Wages and profits start in different quarters")
    line_plot_finalise(
        pd.DataFrame({"Wages": wages / wages.iloc[0], "Profits": profit / profit.iloc[0]}),
        title="Profits index vs Wages index",
        ylabel=f"Index ({wages.index[0]} = 1)",
        rfooter=rfooter,
        lfooter=f"{lfooter}{ends}",
        pre_tag="profits-",
        annotate=True,
    )


def market_sector_shares(release: AbsRelease) -> None:
    """Market, non-market and ownership of dwellings shares of GVA at basic prices (volume terms)."""
    total = _get(release, GVA_TOTAL_DID, INDUSTRY_GVA)
    parts = pd.DataFrame(
        {name: _get(release, did, table) for name, (did, table) in GVA_SECTOR_DIDS.items()}
    ).dropna()
    shares = parts.div(total, axis=0).dropna() * PERCENT
    gap = (shares.sum(axis=1) - PERCENT).abs().max()
    if gap > GVA_SHARE_TOLERANCE:
        raise ValueError(f"Sector shares do not sum to GVA (max gap {gap:.3f} ppt)")
    multi_start(
        shares,
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title="Market and Non-market Sectors: Share of Gross Value Added",
        ylabel="Per cent of GVA",
        legend={"loc": "best", "fontsize": "small"},
        rfooter=release.source,
        lfooter=f"{AUSTRALIA}{SA_NOTE}{CVM_NOTE}{data_to(shares)}",
    )


def investment_to_earnings(release: AbsRelease) -> None:
    """Private non-dwelling investment over non-financial corporations' gross operating surplus, gross and net."""
    investment = (
        _get(release, PRIVATE_GFCF_DID, CAPITAL_ACCOUNT) - _get(release, DWELLINGS_GFCF_DID, EXPENDITURE_CP)
    ).dropna()
    surplus = _get(release, NFC_SURPLUS_DID, NFC_INCOME)
    depreciation = _get(release, NFC_DEPRECIATION_DID, NFC_INCOME)
    net_surplus = (surplus - depreciation).dropna()
    if (net_surplus <= 0).any():
        raise ValueError("Net corporate surplus is not positive: net ratio undefined")
    ratios = pd.DataFrame(
        {
            "Gross": investment / surplus * PERCENT,
            "Net of depreciation": (investment - depreciation) / net_surplus * PERCENT,
        }
    ).dropna()
    if ratios.empty:
        raise ValueError("No overlapping quarters between investment and income")
    multi_start(
        ratios,
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title="Business Investment as a Share of Corporate Earnings",
        ylabel="Per cent of corporate gross operating surplus",
        legend={"loc": "best", "fontsize": "small"},
        rfooter=release.source,
        lfooter=f"{AUSTRALIA}{SA_NOTE}{CP_NOTE}{data_to(ratios)}",
    )


def labour_share(release: AbsRelease) -> None:
    """Compensation of employees as a share of published nominal GDP."""
    _table, gdp_id, _units = ra.find_abs_id(
        release.meta,
        {KEY_AGGS: mc.table, SA: mc.stype, GDP_CP_DID: mc.did, MILLIONS: mc.unit},
        exact_match=True,
        verbose=False,
    )
    gdp = release.data[KEY_AGGS][gdp_id].dropna()
    _table, coe_id, _units = ra.find_abs_id(
        release.meta,
        {INCOME_FROM_GDP: mc.table, SA: mc.stype, COE_DID: mc.did},
        exact_match=True,
        verbose=False,
    )
    coe = release.data[INCOME_FROM_GDP][coe_id].dropna()
    share = (coe / gdp * PERCENT).dropna()
    if share.empty:
        raise ValueError("No overlapping periods for COE and nominal GDP")
    share.name = "COE share of GDP"
    multi_start(
        share,
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title="Compensation of Employees: Share of Nominal GDP",
        ylabel="Per cent of nominal GDP",
        annotate=True,
        rounding=1,
        rfooter=release.source,
        lfooter=f"{AUSTRALIA}{SA_NOTE}{CP_NOTE}{data_to(share)}",
        pre_tag="coe-share-",
    )


# --- table of contents, in run order
CHARTS = (
    (summary, ()),
    (basic, ()),
    (final_demand, ()),
    (long_run_growth, ()),
    (trend_growth, ()),
    (rolling_totals, ()),
    (implicit_population, ()),
    (state_final_demand, ()),
    (hfce_share, ()),
    (household_income, ()),
    (income_tax_share, ()),
    (profits, ()),
    (market_sector_shares, ()),
    (investment_to_earnings, ()),
    (labour_share, ()),
)
