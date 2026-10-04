"""Productivity: labour productivity, its long-run splice, MFP, growth accounting, and productivity by industry."""

# --- dependencies
from typing import TYPE_CHECKING, Any

import pandas as pd
import readabs as ra
from mgplot import line_plot_finalise, multi_start, postcovid_plot_finalise, series_growth_plot_finalise
from readabs import metacol as mc
from statsmodels.tsa.filters.hp_filter import hpfilter

from au_econ.analysis.henderson import hma
from au_econ.charting.windows import quarterly_plot_times
from au_econ.releases.abs.modellers_database_1364.common import (
    BOTH_SOURCE,
    HENDERSON_TERMS,
    INCOME_TABLE,
    KEY_AGGS,
    LEGEND,
    PERCENT,
    QUARTERS_PER_YEAR,
    SA,
    SA_CVM,
    data_to,
    decade_average_plot,
    get_productivity_index,
    get_productivity_splice_report,
)

if TYPE_CHECKING:
    from au_econ.releases.abs.modellers_database_1364.common import ModellersData

# --- constants
GROWTH_FROM = quarterly_plot_times[1]
GVA_NOTE = "GVA = gross value added. "
MFP_NOTE = "MFP = multifactor productivity. "
HP_LAMBDA = 1600  # quarterly data
PRODUCTIVITY_DIDS = {
    "GDP per hour worked": "GDP per hour worked: Index ;",
    "GVA per hour worked (Market sector)": "Gross value added per hour worked market sector: Index ;",
}
EMA_SPAN = 20  # quarters
RECENT_QUARTERS = 60
MOVING_AVERAGE_QUARTERS = 40  # ten years
INDUSTRY_GVA = "5206006_Industry_GVA"
LABOUR_ACCOUNT = "6150.0.55.003"
HOURS_DID = "Labour Account hours actually worked in all jobs"
MARKET_INDUSTRIES = {  # ANZSIC division: (legend name, Labour Account table)
    "A": ("Agriculture", "6150055003DO002"),
    "B": ("Mining", "6150055003DO003"),
    "C": ("Manufacturing", "6150055003DO004"),
    "D": ("Electricity, gas & water", "6150055003DO005"),
    "E": ("Construction", "6150055003DO006"),
    "F": ("Wholesale trade", "6150055003DO007"),
    "G": ("Retail trade", "6150055003DO008"),
    "H": ("Accommodation & food", "6150055003DO009"),
    "I": ("Transport", "6150055003DO010"),
    "J": ("Info media & telco", "6150055003DO011"),
    "K": ("Finance & insurance", "6150055003DO012"),
    "L": ("Rental & real estate", "6150055003DO013"),
    "M": ("Professional & technical", "6150055003DO014"),
    "N": ("Admin & support", "6150055003DO015"),
    "R": ("Arts & recreation", "6150055003DO019"),
    "S": ("Other services", "6150055003DO020"),
}
INDUSTRY_COLOURS = (  # 16 distinct colours; line style varied in blocks so similar hues stay apart
    "#000000",
    "#e6194B",
    "#3cb44b",
    "#4363d8",
    "#f58231",
    "#911eb4",
    "#008080",
    "#f032e6",
    "#9A6324",
    "#808000",
    "#000075",
    "#800000",
    "#42d4f4",
    "#DAA520",
    "#808080",
    "#1f9e89",
)
INDUSTRY_STYLES = ("-",) * 4 + ("--",) * 4 + ("-.",) * 4 + (":",) * 4


# --- helpers
def _sa(data: ModellersData, table: str, did: str) -> pd.Series:
    """Return a seasonally adjusted series by exact description, without gaps."""
    _table, series_id, _units = ra.find_abs_id(
        data.meta, {table: mc.table, SA: mc.stype, did: mc.did}, exact_match=True, verbose=False
    )
    return data.data[table][series_id].dropna()


def _labour_growth(data: ModellersData) -> pd.Series:
    """Return year-on-year growth in GDP per hour worked."""
    labour_prod, _ = data.used["gdp_per_hour"]
    return (labour_prod.pct_change(periods=QUARTERS_PER_YEAR) * PERCENT).dropna()


# --- charts
def labour_productivity(data: ModellersData) -> None:
    """Chart GDP and market sector GVA per hour worked: levels, COVID recovery, growth, comparisons, trends."""

    def common(title: str, plotted: pd.Series | pd.DataFrame) -> dict[str, Any]:
        gva = GVA_NOTE if "GVA" in title else ""
        return {
            "rfooter": data.source,
            "lfooter": f"{SA_CVM}{gva}{data_to(plotted)}",
            "pre_tag": "productivity-",
        }

    productivity = {}
    for label, did in PRODUCTIVITY_DIDS.items():
        _table, series_id, units = ra.find_abs_id(
            data.meta, {KEY_AGGS: mc.table, SA: mc.stype, did: mc.did}, verbose=False
        )
        series = data.data[KEY_AGGS][series_id].dropna()
        productivity[label] = series
        multi_start(
            series,
            function=line_plot_finalise,
            starts=quarterly_plot_times,
            title=label,
            ylabel=units,
            annotate=True,
            **common(label, series),
        )
        postcovid_plot_finalise(
            series, title=label, ylabel=units, tag="covid", annotate=[False, True], **common(label, series)
        )
        series_growth_plot_finalise(
            series, title=f"{label} growth", plot_from=GROWTH_FROM, tag="growth", **common(label, series)
        )

    comparison = pd.DataFrame(productivity).dropna()
    title = "Labour Productivity: GDP vs Market Sector GVA"
    line_plot_finalise(
        comparison / comparison.iloc[0] * PERCENT,
        title=title,
        ylabel="Index (start = 100)",
        annotate=True,
        legend=LEGEND,
        **common(title, comparison),
    )
    growth_comparison = (pd.DataFrame(productivity).pct_change(periods=QUARTERS_PER_YEAR) * PERCENT).dropna()
    line_plot_finalise(
        growth_comparison,
        title="Labour Productivity Growth (YoY)",
        ylabel="Per cent",
        tag="growth-comparison",
        annotate=True,
        y0=True,
        legend=LEGEND,
        **common("", growth_comparison),
    )
    for label, series in productivity.items():
        growth = (series.pct_change(periods=QUARTERS_PER_YEAR) * PERCENT).dropna()
        line_plot_finalise(
            pd.DataFrame({"Annual growth": growth, f"{HENDERSON_TERMS}-term HMA": hma(growth, HENDERSON_TERMS)}),
            title=f"Long-run Growth Trends: {label}",
            ylabel="Per cent growth (YoY)",
            width=[1, 3],
            annotate=[False, True],
            y0=True,
            legend=LEGEND,
            tag="long-run",
            **common(label, growth),
        )


def long_run_productivity(data: ModellersData) -> None:
    """Chart GDP per hour worked spliced back to 1966: level and annual growth."""
    index, units, _stype = get_productivity_index()
    junction = pd.Period(get_productivity_splice_report()["window_start"].iloc[0], freq="Q-DEC")
    common: dict[str, Any] = {
        "rfooter": f"{data.source}; RBA: OP8",
        "lfooter": f"{SA_CVM}Pre-{junction} derived from annual August hours. {data_to(index)}",
        "pre_tag": "longrun-",
        "axvline": {"x": junction, "color": "darkgrey", "linewidth": 0.75, "linestyle": "--"},
    }
    line_plot_finalise(index, title="GDP per Hour Worked: Long Run", ylabel=units, annotate=True, **common)
    growth = ((index / index.shift(QUARTERS_PER_YEAR) - 1) * PERCENT).dropna()
    line_plot_finalise(
        growth.rename("Year-ended growth"),
        title="GDP per Hour Worked: Long Run Annual Growth",
        ylabel="Per cent per year",
        annotate=True,
        y0=True,
        **common,
    )


def mfp(data: ModellersData) -> None:
    """Chart multifactor productivity as a Solow residual, with the Modellers' Database capital stock."""
    gdp, _ = data.used["gdp_cvm"]
    hours, _ = data.used["hours"]
    coe, _ = data.used["coe"]
    capital, _ = data.used["capital"]
    alpha = (coe / _sa(data, INCOME_TABLE, "Total factor income ;")).dropna().mean()  # long-run labour share

    l_norm, k_norm, y_norm = hours / hours.iloc[0], capital / capital.iloc[0], gdp / gdp.iloc[0]
    level = (y_norm / (l_norm**alpha * k_norm ** (1 - alpha)) * PERCENT).dropna()
    growth = (level.pct_change(periods=QUARTERS_PER_YEAR) * PERCENT).dropna()
    level_hp = pd.Series(hpfilter(level, lamb=HP_LAMBDA)[1], index=level.index)
    level_hma = hma(level, HENDERSON_TERMS)
    growth_hp = pd.Series(hpfilter(growth, lamb=HP_LAMBDA)[1], index=growth.index)
    growth_hma = hma(growth, HENDERSON_TERMS)

    lfooter = f"{SA_CVM}Solow residual. "
    common: dict[str, Any] = {
        "rfooter": BOTH_SOURCE,
        "lfooter": f"{lfooter}{data_to(level)}",
        "pre_tag": "mfp-",
    }
    mfp_titled = common | {"lfooter": f"{lfooter}{MFP_NOTE}{data_to(level)}"}
    line_plot_finalise(
        pd.DataFrame(
            {"MFP (Solow Residual)": level, "HP Filter Trend": level_hp, "13-term Henderson MA": level_hma}
        ).dropna(),
        title="Multifactor Productivity (Solow Residual)",
        ylabel="Index",
        width=[1, 2, 2],
        annotate=[False, False, True],
        legend=LEGEND,
        **common,
    )
    line_plot_finalise(
        pd.DataFrame({"HP Filter Trend": level_hp, "13-term Henderson MA": level_hma}).dropna(),
        title="MFP Trends: HP Filter vs Henderson MA",
        ylabel="Index",
        annotate=True,
        legend=LEGEND,
        tag="trends",
        **mfp_titled,
    )
    line_plot_finalise(
        pd.DataFrame(
            {"MFP Growth (YoY)": growth, "HP Filter Trend": growth_hp, "13-term Henderson MA": growth_hma}
        ).dropna(),
        title="MFP Growth with Smoothed Trends",
        ylabel="Per cent (YoY)",
        width=[1, 2, 2],
        annotate=[False, False, True],
        y0=True,
        legend=LEGEND,
        tag="growth",
        **mfp_titled,
    )
    labour_prod, _ = data.used["gdp_per_hour"]
    comparison = pd.DataFrame({"Labour Productivity": labour_prod, "MFP (Solow Residual)": level}).dropna()
    comparison = comparison / comparison.iloc[0] * PERCENT
    line_plot_finalise(
        comparison,
        title="Labour Productivity vs Multifactor Productivity",
        ylabel=f"Index ({comparison.index[0]} = 100)",
        annotate=True,
        legend=LEGEND,
        tag="vs-lp",
        **common,
    )
    print(f"Labour share (α): {alpha:.3f}")
    print(f"MFP growth (latest YoY): {growth.iloc[-1]:.2f}%")


def gdp_decomposition(data: ModellersData) -> None:
    """Chart Solow growth accounting with the Modellers' Database labour force and capital stock."""
    gdp, _ = data.used["gdp_cvm"]
    coe, _ = data.used["coe"]
    gos = _sa(data, INCOME_TABLE, "Total corporations ;  Gross operating surplus ;")
    alpha = (gos / (gos + coe)).dropna().mean()  # long-run capital share
    labour_force, _ = data.used["labour_force"]
    capital, _ = data.used["capital"]

    contributions = pd.DataFrame(
        {
            "GDP Growth": gdp.pct_change(periods=QUARTERS_PER_YEAR) * PERCENT,
            "Labour Growth": (
                (1 - alpha) * (labour_force.pct_change(periods=QUARTERS_PER_YEAR) * PERCENT)
            ).dropna(),
            "Capital Growth": (alpha * (capital.pct_change(periods=QUARTERS_PER_YEAR) * PERCENT)).dropna(),
        }
    ).dropna()
    contributions["MFP Growth"] = (
        contributions["GDP Growth"] - contributions["Labour Growth"] - contributions["Capital Growth"]
    )
    parts = ["Labour Growth", "Capital Growth", "MFP Growth"]
    method = f"ΔY = (1-α)ΔL + αΔK + ΔMFP, α = {alpha:.2f} (capital share). "
    common: dict[str, Any] = {
        "rfooter": BOTH_SOURCE,
        "lfooter": f"{SA_CVM}{method}{data_to(contributions)}",
        "pre_tag": "gdp-decomp-",
    }
    lines: dict[str, Any] = {"annotate": True, "y0": True, "legend": LEGEND}

    line_plot_finalise(
        contributions[parts],
        title="GDP Growth Contributions (YoY)",
        ylabel="Percentage points",
        tag="contributions",
        **lines,
        **common,
    )
    line_plot_finalise(
        pd.DataFrame(
            {
                "GDP Growth (actual)": contributions["GDP Growth"],
                "Sum of contributions": contributions[parts].sum(axis=1),
            }
        ),
        title="GDP Growth: Actual vs Decomposition",
        ylabel="Per cent (YoY)",
        tag="check",
        rfooter=common["rfooter"],
        lfooter=common["lfooter"],
        pre_tag="gdp-decomp-",
        **lines,
    )
    line_plot_finalise(
        pd.DataFrame({col: hma(contributions[col], HENDERSON_TERMS) for col in parts}),
        title=f"GDP Growth Contributions ({HENDERSON_TERMS}-term Henderson MA)",
        ylabel="Percentage points",
        tag="contributions-hma",
        **lines,
        **common,
    )
    line_plot_finalise(
        pd.DataFrame({col: contributions[col].ewm(span=EMA_SPAN, adjust=False).mean() for col in parts}),
        title=f"GDP Growth Contributions (EMA, span={EMA_SPAN})",
        ylabel="Percentage points",
        tag="contributions-ema",
        **lines,
        **common,
    )
    line_plot_finalise(
        contributions.iloc[-RECENT_QUARTERS:][parts],
        title="GDP Growth Contributions: Recent (YoY)",
        ylabel="Percentage points",
        tag="contributions-recent",
        **lines,
        **common,
    )


def productivity_decade_averages(data: ModellersData) -> None:
    """Chart labour productivity growth with decade averages: calendar decades and years ending 6 to 5."""
    growth = _labour_growth(data)
    decade_average_plot(
        growth,
        title="Labour Productivity Growth with Decade Averages",
        rfooter=data.source,
        lfooter=f"{SA_CVM}GDP per hour worked, YoY growth.",
        pre_tag="labour-productivity-",
        tag="decade-averages",
    )
    decade_average_plot(
        growth,
        title="Labour Productivity Growth with Decade Averages (6-to-5)",
        rfooter=data.source,
        lfooter=f"{SA_CVM}GDP per hour worked, YoY growth. Decades: years ending 6 to 5.",
        pre_tag="labour-productivity-",
        tag="decade-averages-6to5",
        six_to_five=True,
    )


def productivity_moving_average(data: ModellersData) -> None:
    """Chart labour productivity growth with its 10-year moving average."""
    growth = _labour_growth(data)
    moving = growth.rolling(window=MOVING_AVERAGE_QUARTERS, min_periods=MOVING_AVERAGE_QUARTERS).mean()
    line_plot_finalise(
        pd.DataFrame({"Annual growth (YoY)": growth, "10-year moving average": moving}),
        title="Labour Productivity Growth with 10-Year Moving Average",
        ylabel="Per cent (YoY)",
        width=[1, 3],
        color=["#888888", "navy"],
        style=["-", "-"],
        annotate=[False, True],
        rounding=2,
        y0=True,
        legend=LEGEND,
        rfooter=data.source,
        lfooter=f"{SA_CVM}GDP per hour worked, YoY growth. 40-quarter moving average. {data_to(growth)}",
        pre_tag="labour-productivity-",
        tag="10yr-ma",
    )


def industry_productivity(data: ModellersData) -> None:
    """Chart real GVA per hour worked, indexed and Henderson-smoothed, for each market-sector industry."""
    hours_data, hours_meta = ra.read_abs_cat(LABOUR_ACCOUNT, verbose=False)
    meta = data.meta
    productivity = {}
    for letter, (name, hours_table) in MARKET_INDUSTRIES.items():
        gva_rows = meta[  # the division total: its description ends "(<letter>) ;"
            (meta[mc.table] == INDUSTRY_GVA)
            & (meta[mc.stype] == SA)
            & meta[mc.did].str.contains(rf"\({letter}\) ;$", regex=True)
        ]
        hours_rows = hours_meta[
            (hours_meta[mc.table] == hours_table)
            & (hours_meta[mc.stype] == SA)
            & hours_meta[mc.did].str.contains(HOURS_DID, regex=False)
            & ~hours_meta[mc.did].str.contains("Percentage", regex=False)
        ]
        if len(gva_rows) != 1 or len(hours_rows) != 1:
            print(f"Skipping {name}: gva={len(gva_rows)} hours={len(hours_rows)} rows")
            continue
        gva = data.data[INDUSTRY_GVA][gva_rows[mc.id].iloc[0]].dropna()
        hours = hours_data[hours_table][hours_rows[mc.id].iloc[0]].dropna()
        smoothed = hma((gva / hours).dropna(), HENDERSON_TERMS)
        productivity[name] = smoothed / smoothed.iloc[0] * PERCENT
    if not productivity:
        raise ValueError("No industry productivity series built")

    frame = pd.DataFrame(productivity)
    base = frame.index[0]
    frame.columns = [f"{c} ({frame[c].iloc[-1]:.0f})" for c in frame.columns]  # latest value in the legend
    line_plot_finalise(
        frame,
        title="Market Sector Labour Productivity by Industry",
        ylabel=f"Index ({base} = 100)",
        figsize=(9.0, 9.0),
        color=list(INDUSTRY_COLOURS),
        style=list(INDUSTRY_STYLES),
        annotate=True,
        rounding=0,
        fontsize="x-small",
        axhline={"y": 100, "color": "black", "linewidth": 0.75, "alpha": 0.7},
        legend={"loc": "upper left", "fontsize": 8, "ncol": 2},
        rfooter=f"{data.source}, {LABOUR_ACCOUNT}",
        lfooter=f"{SA_CVM}Real GVA per hour worked, {HENDERSON_TERMS}-term Henderson MA. {data_to(frame)}",
        pre_tag="productivity-",
    )


# --- table of contents, in run order
CHARTS = (
    (labour_productivity, ()),
    (long_run_productivity, ()),
    (mfp, ()),
    (gdp_decomposition, ()),
    (productivity_decade_averages, ()),
    (productivity_moving_average, ()),
    (industry_productivity, ()),
)
