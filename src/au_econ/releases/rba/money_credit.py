"""RBA money and credit: money supply, velocity, credit growth and its decompositions, housing credit.

Tables: D1 (growth in financial aggregates), D2 (lending and credit aggregates), D3
(monetary aggregates), D12 (ADI balance sheet) and D13 (monetary survey); nominal GDP
from ABS 5206.0. D12 and D13 are Original series and run a month behind D1.
"""

# --- dependencies
from dataclasses import dataclass

import mgplot as mg
import numpy as np
import pandas as pd
import readabs as ra
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter

from au_econ.charting.footers import SERIES_TYPE_NOTES
from au_econ.charting.windows import monthly_plot_times
from au_econ.series.gdp import get_gdp
from au_econ.sources import rba

# --- module contract
RELEASE = ("rba-money",)
TOPICS = ("rba",)
TITLE = "Money and Credit"

# --- constants
SOURCE = "RBA:"  # followed by the table(s), e.g. "RBA: D1, D2"
ABS_GDP_SOURCE = "ABS: 5206.0"
TABLES = ("D1", "D2", "D3", "D12", "D13")
MONTHS_PER_YEAR = 12
QUARTERS_PER_YEAR = 4
PERCENT = 100

# chart windows: full history, then the recent years (plus the period growth starts from)
plot_times = 0, -(5 * MONTHS_PER_YEAR) - 1
money_starts = 0, -(10 * MONTHS_PER_YEAR) - 1
velocity_starts = 0, -(20 * QUARTERS_PER_YEAR) - 1

# money supply (D3)
MONEY_AGGREGATES = ("Currency: Seasonally adjusted", "Money base", "M1", "M3", "Broad money")
M1_TREND_WINDOW = (pd.Period("2016-05-01", "D"), pd.Period("2019-05-01", "D"))  # pre-COVID trend fitted over
TREND_WINDOW = (pd.Period("2017-01-01", "D"), pd.Period("2020-01-01", "D"))
LOG_TICK_STEPS = (1.0, 2.0, 5.0)  # log-axis ticks at 1, 2 and 5 times each power of ten

# velocity of money
M3_TITLE = "M3"
BILLION_IN_MILLIONS = 1_000

# credit, from D1 and D2
CREDIT_GROWTH_TITLES = {  # RBA D1 title: chart title
    "Credit; Housing; Monthly growth": "Housing Credit: Monthly Growth",
    "Credit; Owner-occupier housing; Monthly growth": "Owner-occupier Housing Credit: Monthly Growth",
    "Credit; Investor housing; Monthly growth": "Investor Housing Credit: Monthly Growth",
    "Credit; Other personal; Monthly growth": "Other Personal Credit: Monthly Growth",
}
TOTAL_CREDIT_STEM = "Total excluding financial businesses"
TOTAL_CREDIT_GROWTH = f"Credit; {TOTAL_CREDIT_STEM}; 12-month ended growth"
BROAD_MONEY_GROWTH = "Broad money; 12-month ended growth"
CREDIT_COMPONENTS = {  # label: (D1 growth title stem, D2 level title stem); D1 capitalises "Business"
    "Owner-occupier housing": ("Owner-occupier housing", "Owner-occupier housing"),
    "Investor housing": ("Investor housing", "Investor housing"),
    "Other personal": ("Other personal", "Other personal"),
    "Business": ("Non-financial Business", "Non-financial business"),
}
LEGEND_HEADROOM = 0.35  # empty space above the bars, as a share of their y-range, for the legend

# ADI funding (D12)
FUNDING_GROUPS = {
    "Deposits": (
        "Liabilities: Transferable deposits included in broad money",
        "Liabilities: Other deposits included in broad money",
    ),
    "Domestic wholesale": (
        "Liabilities: Securities other than shares included in broad money",
        "Liabilities: Securities other than shares excluded from broad money",
    ),
    "Offshore": ("Liabilities: Liabilities to non-residents",),
    "Other": (
        "Liabilities: Liabilities to central government",
        "Liabilities: Deposits excluded from broad money",
        "Liabilities: Loans",
        "Liabilities: Financial derivatives",
        "Liabilities: Shares and other equity",
    ),
}

# broad money counterparts (D13)
NON_MONEY_LIABILITIES = (
    "Liabilities: Deposits excluded from broad money",
    "Liabilities: Securities other than shares excluded from broad money",
    "Liabilities: Loans",
    "Liabilities: Financial derivatives",
    "Liabilities: Shares and other equity",
)
PRIVATE_CLAIMS = "Assets: Claims on other sectors: Private sector"
ALL_SECTOR_CLAIMS = "Assets subtotal: Claims on other sectors: Total"
NET_GOVERNMENT_CLAIMS = "Subtotal: Net claims on central government"
NET_FOREIGN_ASSETS = "Subtotal: Net foreign assets"
OTHER_ITEMS = "Assets: Other balancing items (net) (computed as assets minus liabilities)"
BROAD_MONEY_LEVEL = "Liabilities subtotal: Broad money liabilities: Total"

# housing and business credit (D2)
RBA_SERIES = {  # label: RBA D2 series ID
    "Owner-occupier housing credit": "DLCACOHS",
    "Investor housing credit": "DLCACIHS",
    "Non-financial business credit": "DLCACNFBS",
    "Total credit excluding financial businesses": "DLCACFS",
}
HOUSING_CREDIT = {
    "Owner-occupier": "Credit; Owner-occupier housing; Seasonally adjusted",
    "Investor": "Credit; Investor housing; Seasonally adjusted",
}
HOUSING_CREDIT_CAVEAT = "Split affected by loan purpose switching. "


@dataclass(frozen=True)
class MoneyData:
    """Each RBA table used, as (data, metadata), and quarterly nominal GDP (CP, SA) with its units."""

    tables: dict[str, tuple[pd.DataFrame, pd.DataFrame]]
    gdp: pd.Series
    gdp_units: str


# --- data
def fetch() -> MoneyData:
    """Fetch the D1, D2, D3, D12 and D13 tables and nominal GDP."""
    gdp, gdp_units = get_gdp("CP", "SA")
    return MoneyData(tables={table: rba.get_table(table) for table in TABLES}, gdp=gdp, gdp_units=gdp_units)


# --- helpers
def _series_id(data: MoneyData, table: str, title: str) -> str:
    """Return the ID of the one series in a table with this exact title."""
    _, meta = data.tables[table]
    matches = meta[meta.Title == title]
    if len(matches) != 1:
        raise ValueError(f"RBA {table}: expected one series titled {title!r}, found {len(matches)}")
    return str(matches.index[0])


def _column(data: MoneyData, table: str, title: str) -> pd.Series:
    """One series by title, as floats, gaps kept."""
    frame, _ = data.tables[table]
    return frame[_series_id(data, table, title)].astype(float)


def _by_title(data: MoneyData, table: str, title: str) -> pd.Series:
    """One series by title, as floats, without gaps."""
    series = _column(data, table, title).dropna()
    if series.empty:
        raise ValueError(f"RBA {table}: no data for {title!r}")
    return series


def _meta_value(data: MoneyData, table: str, title: str, column: str) -> str:
    """One metadata field (e.g. "Type", "Units") of the series with this title."""
    _, meta = data.tables[table]
    return str(meta.loc[_series_id(data, table, title), column])


def _type_note(rba_type: str) -> str:
    """Return the standard series-type note (e.g. "Original series.") for an RBA Type field."""
    notes = {key.lower(): note for key, note in SERIES_TYPE_NOTES.items()}
    if rba_type.lower() not in notes:
        raise ValueError(f"Unknown RBA series type {rba_type!r}")
    return notes[rba_type.lower()]


def _year_ago(series: pd.Series) -> pd.Series:
    """Relabel a monthly series so each value sits at the date a year later."""
    lagged = series.copy()
    lagged.index = lagged.index + MONTHS_PER_YEAR
    return lagged


def _total(data: MoneyData, table: str, titles: tuple[str, ...]) -> pd.Series:
    """Sum several series by title; a month missing any of them is missing."""
    return pd.concat([_by_title(data, table, title) for title in titles], axis=1).sum(
        axis=1, min_count=len(titles)
    )


def _growth_contributions(levels: pd.DataFrame, total: pd.Series) -> pd.DataFrame:
    """Each level's 12-month change as a percentage of the total a year earlier."""
    year_ago_total = _year_ago(total)
    return pd.DataFrame(
        {label: (level - _year_ago(level)) / year_ago_total * PERCENT for label, level in levels.items()}
    )


def _plot_contributions(
    contributions: pd.DataFrame, total: pd.Series, *, title: str, lfooter: str, rfooter: str, pre_tag: str
) -> None:
    """Plot stacked-bar contributions with the total as a line, over the recent window."""
    contributions = contributions.dropna()
    total = total.reindex(contributions.index)
    gap = (contributions.sum(axis=1) - total).abs().max()
    print(f"{title}: largest gap between summed bars and total line = {gap:.2f} ppt")

    start = contributions.index[monthly_plot_times[-1]]
    axes = mg.bar_plot(contributions.loc[start:], stacked=True)
    mg.line_plot(total.loc[start:], ax=axes, color="black", annotate=True)
    bottom, top = axes.get_ylim()
    mg.finalise_plot(
        axes,
        title=title,
        ylabel="Percentage points",
        lfooter=lfooter,
        rfooter=rfooter,
        ylim=(bottom, top + (top - bottom) * LEGEND_HEADROOM),
        legend={"loc": "upper left", "fontsize": "x-small", "ncol": 3},
        y0=True,
        pre_tag=pre_tag,
    )


def _mid_quarter_months(index: pd.Index) -> pd.PeriodIndex:
    """Return each quarter of a quarterly PeriodIndex as its middle month."""
    if not isinstance(index, pd.PeriodIndex):
        raise TypeError(f"expected a quarterly PeriodIndex, got {type(index).__name__}")
    return index.asfreq("M", how="END") - 1


def _plain_number(value: float, _position: int) -> str:
    """Format a log-axis tick as a plain number (0.5, 2, 1000), not a power of ten."""
    return f"{value:g}"


def _log_line_charts(
    series: pd.Series,
    starts: tuple[int, ...],
    *,
    title: str,
    ylabel: str,
    lfooter: str,
    rfooter: str,
    pre_tag: str,
) -> None:
    """Chart a series on a log y-axis from each start, with 1-2-5 ticks as labelled, gridded majors.

    mgplot's yscale="log" leaves the in-decade ticks minor, so they print in scientific
    notation and get no gridline; the ticks are set here between plotting and finalising.
    """
    for i, start in enumerate(starts):
        axes = mg.line_plot(series, plot_from=start, annotate=True)
        axes.set_yscale("log")  # resets the locators, so set ticks after this
        axes.yaxis.set_major_locator(LogLocator(base=10, subs=LOG_TICK_STEPS))
        axes.yaxis.set_major_formatter(FuncFormatter(_plain_number))
        axes.yaxis.set_minor_formatter(NullFormatter())
        mg.finalise_plot(
            axes, title=title, ylabel=ylabel, lfooter=lfooter, rfooter=rfooter, pre_tag=pre_tag, tag=f"log-{i}"
        )


def _monthly_nominal_gdp(data: MoneyData) -> pd.Series:
    """Quarterly nominal GDP on a monthly index: each quarter on its middle month, log-linear between."""
    log_gdp = np.log(data.gdp)
    log_gdp.index = _mid_quarter_months(data.gdp.index)
    months = pd.period_range(log_gdp.index[0], log_gdp.index[-1], freq="M")
    return np.exp(log_gdp.reindex(months).interpolate())


def _housing_credit(data: MoneyData) -> tuple[pd.DataFrame, str]:
    """Owner-occupier and investor housing credit outstanding, and their unit."""
    frame = pd.DataFrame({label: _by_title(data, "D2", title) for label, title in HOUSING_CREDIT.items()})
    return frame, _meta_value(data, "D2", HOUSING_CREDIT["Investor"], "Units")


# --- charts
def money_supply(data: MoneyData) -> None:
    """Chart each monetary aggregate against its pre-COVID trend, and on linear and log scales."""
    print(f"Last date: {data.tables['D3'][0].index[-1]}")
    for title in MONEY_AGGREGATES:
        series, unit = ra.recalibrate(_by_title(data, "D3", title), _meta_value(data, "D3", title, "Units"))
        series.name = title
        chart_title = f"{title} - Money Supply"
        type_note = _type_note(_meta_value(data, "D3", title, "Type"))
        lfooter = f"Australia. {type_note} Data to {series.index[-1]}. "
        start_r, end_r = M1_TREND_WINDOW if title == "M1" else TREND_WINDOW
        mg.postcovid_plot_finalise(
            series,
            start_r=start_r,
            end_r=end_r,
            title=chart_title,
            tag="COVID",
            ylabel=unit,
            rfooter=f"{SOURCE} D3",
            lfooter=lfooter,
            pre_tag="d3-",
        )
        mg.multi_start(
            series,
            function=mg.line_plot_finalise,
            starts=money_starts,
            title=chart_title,
            ylabel=unit,
            lfooter=lfooter,
            rfooter=f"{SOURCE} D3",
            pre_tag="d3-",
        )
        _log_line_charts(
            series,
            money_starts,
            title=chart_title,
            ylabel=f"{unit} (log scale)",
            lfooter=lfooter,
            rfooter=f"{SOURCE} D3",
            pre_tag="d3-",
        )


def velocity_of_money(data: MoneyData) -> None:
    """Chart velocity (annualised nominal GDP / M3), and nominal GDP against M3 indexed."""
    m3 = _by_title(data, "D3", M3_TITLE)
    m3_units = _meta_value(data, "D3", M3_TITLE, "Units")
    print(f"GDP units: {data.gdp_units}, M3 units: {m3_units}")
    multiplier = BILLION_IN_MILLIONS if "billion" in m3_units.lower() else 1  # GDP is in $ millions
    m3_quarterly = (m3 * multiplier).resample("Q").mean()
    common = data.gdp.index.intersection(m3_quarterly.index)
    gdp, m3_aligned = data.gdp.loc[common], m3_quarterly.loc[common]

    gdp_type = SERIES_TYPE_NOTES["Seasonally Adjusted"].rstrip(".").lower()  # fetch() asks for SA GDP
    m3_type = _type_note(_meta_value(data, "D3", M3_TITLE, "Type")).rstrip(".").lower()
    types = f"GDP {gdp_type}, M3 {m3_type}."

    velocity = (gdp / m3_aligned) * QUARTERS_PER_YEAR
    velocity.name = "Velocity of Money"
    mg.multi_start(
        velocity,
        function=mg.line_plot_finalise,
        starts=velocity_starts,
        title="Velocity of Money (V = Nominal GDP / M3)",
        ylabel="Ratio (annualised)",
        rfooter=f"{SOURCE} D3; {ABS_GDP_SOURCE}",
        lfooter=f"Australia. {types} Quarterly. MV=PQ identity. Data to {velocity.index[-1]}. ",
        pre_tag="d3-",
        annotate=True,
    )

    base = common[0]
    components = pd.DataFrame(
        {"Nominal GDP": gdp / gdp.loc[base] * PERCENT, "M3": m3_aligned / m3_aligned.loc[base] * PERCENT},
        index=common,
    )
    mg.line_plot_finalise(
        components,
        title="Nominal GDP vs M3 (indexed)",
        ylabel=f"Index ({base}=100)",
        rfooter=f"{SOURCE} D3; {ABS_GDP_SOURCE}",
        lfooter=f"Australia. {types} Quarterly. Data to {common[-1]}. ",
        pre_tag="d3-",
        legend={"loc": "upper left", "fontsize": "small"},
    )


def credit_growth(data: MoneyData) -> None:
    """Chart monthly growth in housing, owner-occupier, investor and other personal credit."""
    print(f"Last date: {data.tables['D1'][0].index[-1]}")
    for rba_title, chart_title in CREDIT_GROWTH_TITLES.items():
        series = _column(data, "D1", rba_title)
        type_note = _type_note(_meta_value(data, "D1", rba_title, "Type"))
        mg.multi_start(
            series,
            function=mg.line_plot_finalise,
            starts=plot_times,
            y0=True,
            title=chart_title,
            ylabel="Per cent",
            rfooter=f"{SOURCE} D1",
            lfooter=f"Australia. {type_note} Data to {series.index[-1]}. ",
            pre_tag="d1-",
            annotate=True,
        )


def credit_vs_broad_money(data: MoneyData) -> None:
    """Chart 12-month ended growth in total credit and in broad money."""
    wanted = {"Credit": TOTAL_CREDIT_GROWTH, "Broad money": BROAD_MONEY_GROWTH}
    series_types = {_meta_value(data, "D1", title, "Type") for title in wanted.values()}
    if len(series_types) != 1:
        raise ValueError(f"D1 series types differ: {series_types}")
    type_note = _type_note(series_types.pop())
    frame = pd.DataFrame({label: _by_title(data, "D1", title) for label, title in wanted.items()}).dropna()
    mg.multi_start(
        frame,
        function=mg.line_plot_finalise,
        starts=plot_times,
        y0=True,
        title="Credit and Broad Money: 12-month ended growth",
        ylabel="Per cent",
        rfooter=f"{SOURCE} D1",
        lfooter=f"Australia. {type_note} Data to {frame.index[-1]}. Credit excludes financial businesses. ",
        pre_tag="d1-",
        annotate=True,
    )


def credit_contributions(data: MoneyData) -> None:
    """Chart contributions to 12-month credit growth by borrower: growth times last year's share."""
    total_level = _by_title(data, "D2", f"Credit; {TOTAL_CREDIT_STEM}; Seasonally adjusted")
    contributions = pd.DataFrame(
        {
            label: _by_title(data, "D1", f"Credit; {d1_stem}; 12-month ended growth")
            * _year_ago(_by_title(data, "D2", f"Credit; {d2_stem}; Seasonally adjusted") / total_level)
            for label, (d1_stem, d2_stem) in CREDIT_COMPONENTS.items()
        }
    )
    total_growth = _by_title(data, "D1", TOTAL_CREDIT_GROWTH).rename("Total credit growth (%)")
    type_note = _type_note(_meta_value(data, "D1", TOTAL_CREDIT_GROWTH, "Type"))
    _plot_contributions(
        contributions,
        total_growth,
        title="Credit growth: contributions by borrower",
        lfooter=f"Australia. {type_note} Data to {total_growth.index[-1]}. Credit excludes financial businesses. ",
        rfooter=f"{SOURCE} D1, D2",
        pre_tag="d1-",
    )


def funding_contributions(data: MoneyData) -> None:
    """Chart contributions to 12-month growth in ADI liabilities by funding source."""
    levels = pd.DataFrame({label: _total(data, "D12", titles) for label, titles in FUNDING_GROUPS.items()})
    total_level = levels.sum(axis=1, min_count=len(FUNDING_GROUPS))
    total_growth = ((total_level / _year_ago(total_level) - 1) * PERCENT).rename("Total liabilities growth (%)")
    _, meta = data.tables["D12"]
    _plot_contributions(
        _growth_contributions(levels, total_level),
        total_growth,
        title="ADI funding growth: contributions by source",
        lfooter=f"Australia. {_type_note(str(meta.Type.iloc[0]))} Data to {total_level.index[-1]}. "
        "ADIs only. Offshore includes exchange-rate valuation effects. ",
        rfooter=f"{SOURCE} D12",
        pre_tag="d12-",
    )


def broad_money_counterparts(data: MoneyData) -> None:
    """Chart contributions to 12-month broad money growth by monetary survey counterpart."""
    private_claims = _by_title(data, "D13", PRIVATE_CLAIMS)
    counterparts = pd.DataFrame(
        {
            "Claims on private sector": private_claims,
            "Other domestic claims": _by_title(data, "D13", ALL_SECTOR_CLAIMS) - private_claims,
            "Net claims on central govt": _by_title(data, "D13", NET_GOVERNMENT_CLAIMS),
            "Net foreign assets": _by_title(data, "D13", NET_FOREIGN_ASSETS),
            "Non-money liabilities (negative)": -_total(data, "D13", NON_MONEY_LIABILITIES),
            "Other items (net)": _by_title(data, "D13", OTHER_ITEMS),
        }
    )
    broad_money = _by_title(data, "D13", BROAD_MONEY_LEVEL)
    money_growth = ((broad_money / _year_ago(broad_money) - 1) * PERCENT).rename("Broad money growth (%)")
    _, meta = data.tables["D13"]
    _plot_contributions(
        _growth_contributions(counterparts, broad_money),
        money_growth,
        title="Broad money growth: contributions by counterpart",
        lfooter=f"Australia. {_type_note(str(meta.Type.iloc[0]))} Data to {broad_money.index[-1]}. "
        "IMF-framework broad money. ",
        rfooter=f"{SOURCE} D13",
        pre_tag="d13-",
    )


def nominal_gdp_vs_credit(data: MoneyData) -> None:
    """Chart 12-month growth in nominal GDP (interpolated to months) against private credit."""
    credit = _by_title(data, "D1", TOTAL_CREDIT_GROWTH)
    gdp = _monthly_nominal_gdp(data)
    gdp_growth = ((gdp / _year_ago(gdp) - 1) * PERCENT).dropna()

    # audit: on mid-quarter months the monthly growth must equal the quarterly growth
    quarterly_growth = (data.gdp / data.gdp.shift(QUARTERS_PER_YEAR) - 1) * PERCENT
    quarterly_growth.index = _mid_quarter_months(quarterly_growth.index)
    gap = (gdp_growth - quarterly_growth).abs().max()
    print(f"Largest gap between monthly and quarterly GDP growth on mid-quarter months: {gap:.2e} ppt")

    frame = pd.DataFrame({"Nominal GDP": gdp_growth, "Private credit": credit})
    frame = frame.loc[credit.index[0] :]
    mg.multi_start(
        frame,
        function=mg.line_plot_finalise,
        starts=plot_times,
        title="Nominal GDP vs private credit: 12-month growth",
        ylabel="Per cent",
        lfooter=f"Australia. Seasonally adjusted. GDP interpolated from quarterly, "
        f"to {gdp_growth.index[-1]}. Credit excl. financial businesses. ",
        rfooter=f"{SOURCE} D1; {ABS_GDP_SOURCE}",
        y0=True,
        pre_tag="d1-",
        annotate=True,
    )


def housing_vs_business_credit(data: MoneyData) -> None:
    """Chart housing and non-financial business credit as shares of total credit."""
    frame, _ = data.tables["D2"]

    def series(label: str) -> pd.Series:
        return frame[RBA_SERIES[label]].dropna()

    owner_occupier = series("Owner-occupier housing credit")
    investor = series("Investor housing credit")
    business = series("Non-financial business credit")
    total = series("Total credit excluding financial businesses")
    start = max(business.index[0], total.index[0])
    housing = (owner_occupier + investor).loc[start:]
    shares = pd.DataFrame(
        {
            "Housing": (housing / total.loc[start:] * PERCENT).dropna(),
            "Business (non-financial)": (business.loc[start:] / total.loc[start:] * PERCENT).dropna(),
        }
    )
    mg.line_plot_finalise(
        shares,
        annotate=True,
        rounding=1,
        title="Bank credit allocation: housing vs business, share of total credit",
        ylabel="Per cent of total credit outstanding",
        rfooter=f"{SOURCE} D2",
        lfooter="Australia. Seasonally adjusted. Bank/AFI credit, excluding lending to financial businesses.",
        legend={"loc": "center right", "fontsize": "small"},
        pre_tag="d2",
    )


def housing_credit_levels(data: MoneyData) -> None:
    """Chart owner-occupier and investor housing credit outstanding."""
    credit, unit = _housing_credit(data)
    print(f"Last date: {credit.index[-1]}")
    frame, unit = ra.recalibrate(credit, unit)
    mg.multi_start(
        frame,
        function=mg.line_plot_finalise,
        starts=plot_times,
        title="Housing Credit: Owner-occupier vs Investor",
        ylabel=unit,
        annotate=True,
        rfooter=f"{SOURCE} D2",
        lfooter=f"Australia. Seasonally adjusted. {HOUSING_CREDIT_CAVEAT}",
        legend={"loc": "upper left", "fontsize": "small"},
        pre_tag="d2-",
    )


def investor_share_of_housing_credit(data: MoneyData) -> None:
    """Chart investor housing credit as a share of total housing credit."""
    credit, _ = _housing_credit(data)
    share = (credit["Investor"] / credit.sum(axis=1) * PERCENT).dropna()
    share.name = "Investor share"
    mg.multi_start(
        share,
        function=mg.line_plot_finalise,
        starts=plot_times,
        title="Investor Share of Total Housing Credit",
        ylabel="Per cent of total housing credit",
        annotate=True,
        rounding=1,
        rfooter=f"{SOURCE} D2",
        lfooter=f"Australia. Seasonally adjusted. {HOUSING_CREDIT_CAVEAT}",
        pre_tag="d2-",
    )


CHARTS = (
    (money_supply, ()),
    (velocity_of_money, ()),
    (credit_growth, ()),
    (credit_vs_broad_money, ()),
    (credit_contributions, ()),
    (funding_contributions, ()),
    (broad_money_counterparts, ()),
    (nominal_gdp_vs_credit, ()),
    (housing_vs_business_credit, ()),
    (housing_credit_levels, ()),
    (investor_share_of_housing_credit, ()),
)
