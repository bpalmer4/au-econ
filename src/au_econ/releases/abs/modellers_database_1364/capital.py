"""Capital: the Modellers' Database capital stock, capital deepening, and capital productivity."""

# --- dependencies
from typing import TYPE_CHECKING, Any

import pandas as pd
import readabs as ra
from mgplot import line_plot_finalise, multi_start
from readabs import metacol as mc

from au_econ.analysis.henderson import hma
from au_econ.charting.windows import quarterly_plot_times
from au_econ.releases.abs.modellers_database_1364.common import (
    AUSTRALIA,
    BOTH_SOURCE,
    HENDERSON_TERMS,
    LEGEND,
    MODELLERS_SOURCE,
    PERCENT,
    QUARTERS_PER_YEAR,
    SA,
    SA_CVM,
    SA_NOTE,
    VOLUME_MEASURES,
    data_to,
    decade_average_plot,
)

if TYPE_CHECKING:
    from au_econ.releases.abs.modellers_database_1364.common import ModellersData

# --- constants
ANNUAL_DEPRECIATION = 0.025
OPENING_STOCK_MULTIPLE = 40  # the opening capital stock, in quarters of the first GFCF
GFCF_DID = "All sectors ;  Gross fixed capital formation ;"
RECENT_QUARTERS = 60


# --- helpers
def _deepening(data: ModellersData) -> pd.Series:
    """Return capital per hour worked, both indexed to their first quarter."""
    capital, _ = data.used["capital"]
    hours, _ = data.used["hours"]
    deepening = ((capital / capital.iloc[0] * PERCENT) / (hours / hours.iloc[0] * PERCENT) * PERCENT).dropna()
    deepening.name = "Capital Deepening (K/L)"
    return deepening


def _growth_with_trend(series: pd.Series) -> pd.DataFrame:
    """Return year-on-year growth and its Henderson trend."""
    growth = (series.pct_change(periods=QUARTERS_PER_YEAR) * PERCENT).dropna()
    return pd.DataFrame({"Annual growth": growth, f"{HENDERSON_TERMS}-term HMA": hma(growth, HENDERSON_TERMS)})


# --- charts
def capital_stock_comparison(data: ModellersData) -> None:
    """Chart a perpetual-inventory capital stock built from GFCF against the Modellers' Database stock."""
    _table, gfcf_id, _units = ra.find_abs_id(
        data.meta, {VOLUME_MEASURES: mc.table, SA: mc.stype, GFCF_DID: mc.did}, verbose=False
    )
    gfcf = data.data[VOLUME_MEASURES][gfcf_id].dropna()
    depreciation = ANNUAL_DEPRECIATION / QUARTERS_PER_YEAR
    capital_pi = pd.Series(index=gfcf.index, dtype=float)
    capital_pi.iloc[0] = gfcf.iloc[0] * OPENING_STOCK_MULTIPLE
    for i in range(1, len(gfcf)):
        capital_pi.iloc[i] = (1 - depreciation) * capital_pi.iloc[i - 1] + gfcf.iloc[i]
    capital_abs, capital_meta = data.used["capital"]

    common: dict[str, Any] = {
        "rfooter": BOTH_SOURCE,
        "lfooter": f"{SA_CVM}PI = perpetual inventory (2.5% p.a. depreciation). "
        f"{data_to(pd.DataFrame({'pi': capital_pi, 'abs': capital_abs}).dropna())}",
        "pre_tag": "capital-comparison-",
    }
    levels, units = ra.recalibrate(
        pd.DataFrame(
            {"Perpetual Inventory (from GFCF)": capital_pi, "ABS Modellers Database": capital_abs}
        ).dropna(),
        capital_meta[mc.unit],
    )
    line_plot_finalise(
        levels,
        title="Capital Stock: Perpetual Inventory vs ABS Official",
        ylabel=units,
        annotate=True,
        legend=LEGEND,
        **common,
    )
    line_plot_finalise(
        pd.DataFrame(
            {
                "Perpetual Inventory": capital_pi.pct_change(periods=QUARTERS_PER_YEAR) * PERCENT,
                "ABS Modellers Database": capital_abs.pct_change(periods=QUARTERS_PER_YEAR) * PERCENT,
            }
        ).dropna(),
        title="Capital Stock Growth (YoY): PI vs ABS Official",
        ylabel="Per cent",
        annotate=True,
        y0=True,
        legend=LEGEND,
        tag="growth",
        **common,
    )
    line_plot_finalise(
        pd.DataFrame(
            {
                "Perpetual Inventory": capital_pi / capital_pi.iloc[0] * PERCENT,
                "ABS Modellers Database": capital_abs / capital_abs.iloc[0] * PERCENT,
            }
        ).dropna(),
        title="Capital Stock Index: PI vs ABS Official",
        ylabel="Index (start = 100)",
        annotate=True,
        legend=LEGEND,
        tag="index",
        **common,
    )


def capital_deepening(data: ModellersData) -> None:
    """Chart capital stock growth, capital per hour worked, hours worked, and deepening against productivity."""
    capital, _ = data.used["capital"]
    hours, _ = data.used["hours"]
    capital_growth = _growth_with_trend(capital)
    for frame, tag in ((capital_growth, "growth"), (capital_growth.iloc[-RECENT_QUARTERS:], "growth-recent")):
        line_plot_finalise(
            frame,
            title="Capital Stock Growth (Net, Chain Volume Measures)",
            ylabel="Per cent (YoY)",
            width=[1, 3],
            annotate=[False, True],
            y0=True,
            legend=LEGEND,
            tag=tag,
            rfooter=MODELLERS_SOURCE,
            lfooter=f"{SA_CVM}{data_to(capital_growth)}",
            pre_tag="capital-",
        )

    deepening = _deepening(data)
    common: dict[str, Any] = {
        "rfooter": BOTH_SOURCE,
        "lfooter": f"{SA_CVM}Capital per hour worked (indexed). {data_to(deepening)}",
        "pre_tag": "capital-deepening-",
    }
    multi_start(
        deepening,
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title="Capital Deepening (Capital per Hour Worked)",
        ylabel=f"Index ({deepening.index[0]} = 100)",
        annotate=True,
        **common,
    )
    deepening_growth = _growth_with_trend(deepening)
    line_plot_finalise(
        deepening_growth,
        title="Capital Deepening Growth",
        ylabel="Per cent (YoY)",
        width=[1, 3],
        annotate=[False, True],
        y0=True,
        legend=LEGEND,
        tag="growth",
        **common,
    )

    hours_aligned = hours.loc[deepening.index[0] :].copy()
    hours_index = (hours_aligned / hours_aligned.iloc[0] * PERCENT).rename("Hours Worked")
    line_plot_finalise(
        hours_index,
        title="Hours Worked",
        ylabel=f"Index ({hours_index.index[0]} = 100)",
        annotate=True,
        rfooter=f"{data.source}",
        lfooter=f"{AUSTRALIA}{SA_NOTE}Total hours worked in the economy. {data_to(hours_index)}",
        pre_tag="hours-worked-",
    )

    labour_prod, _ = data.used["gdp_per_hour"]
    labour_prod_norm = labour_prod / labour_prod.iloc[0] * PERCENT
    line_plot_finalise(
        pd.DataFrame(
            {"Capital Deepening (K/L)": deepening, "Labour Productivity (Y/L)": labour_prod_norm}
        ).dropna(),
        title="Capital Deepening vs Labour Productivity",
        ylabel="Index (start = 100)",
        annotate=True,
        legend=LEGEND,
        tag="vs-productivity",
        **common,
    )
    line_plot_finalise(
        pd.DataFrame(
            {
                "Capital Deepening": deepening_growth["Annual growth"],
                "Labour Productivity": labour_prod_norm.pct_change(periods=QUARTERS_PER_YEAR) * PERCENT,
            }
        ).dropna(),
        title="Capital Deepening vs Labour Productivity Growth",
        ylabel="Per cent (YoY)",
        annotate=True,
        y0=True,
        legend=LEGEND,
        tag="growth-vs-productivity",
        **common,
    )


def deepening_decade_averages(data: ModellersData) -> None:
    """Chart capital deepening growth with decade averages: calendar decades and years ending 6 to 5."""
    growth = (_deepening(data).pct_change(periods=QUARTERS_PER_YEAR) * PERCENT).dropna()
    rfooter = BOTH_SOURCE
    decade_average_plot(
        growth,
        title="Capital Deepening Growth with Decade Averages",
        rfooter=rfooter,
        lfooter=f"{SA_CVM}Capital per hour worked, YoY growth.",
        pre_tag="capital-deepening-",
        tag="decade-averages",
    )
    decade_average_plot(
        growth,
        title="Capital Deepening Growth with Decade Averages (6-to-5)",
        rfooter=rfooter,
        lfooter=f"{SA_CVM}Capital per hour worked, YoY growth.",
        pre_tag="capital-deepening-",
        tag="decade-averages-6to5",
        six_to_five=True,
    )


def capital_productivity(data: ModellersData) -> None:
    """Chart output per unit of capital, the capital-output ratio, and the three productivity measures."""
    gdp, _ = data.used["gdp_cvm"]
    capital, _ = data.used["capital"]
    hours, _ = data.used["hours"]
    y_norm = gdp / gdp.iloc[0] * PERCENT
    k_norm = capital / capital.iloc[0] * PERCENT
    l_norm = hours / hours.iloc[0] * PERCENT
    rfooter = BOTH_SOURCE

    productivity = (y_norm / k_norm * PERCENT).dropna()
    productivity.name = "Capital Productivity (Y/K)"
    common: dict[str, Any] = {
        "rfooter": rfooter,
        "lfooter": f"{SA_CVM}Output per unit of capital (indexed). {data_to(productivity)}",
        "pre_tag": "capital-productivity-",
    }
    multi_start(
        productivity,
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title="Capital Productivity (Output per Unit of Capital)",
        ylabel=f"Index ({productivity.index[0]} = 100)",
        annotate=True,
        **common,
    )
    productivity_growth = _growth_with_trend(productivity)
    line_plot_finalise(
        productivity_growth,
        title="Capital Productivity Growth",
        ylabel="Per cent (YoY)",
        width=[1, 3],
        annotate=[False, True],
        y0=True,
        legend=LEGEND,
        tag="growth",
        **common,
    )

    ratio = (k_norm / y_norm * PERCENT).dropna()
    ratio.name = "Capital-Output Ratio (K/Y)"
    multi_start(
        ratio,
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title="Capital-Output Ratio (Capital per Unit of Output)",
        ylabel=f"Index ({ratio.index[0]} = 100)",
        annotate=True,
        rfooter=rfooter,
        lfooter=f"{SA_CVM}Real K / Real Y. {data_to(ratio)}",
        pre_tag="capital-output-ratio-",
    )

    labour = (y_norm / l_norm * PERCENT).dropna()
    deepening = (k_norm / l_norm * PERCENT).dropna()
    comparison = pd.DataFrame(
        {
            "Labour Productivity (Y/L)": labour,
            "Capital Deepening (K/L)": deepening,
            "Capital Productivity (Y/K)": productivity,
        }
    ).dropna()
    comparison = comparison / comparison.iloc[0] * PERCENT
    line_plot_finalise(
        comparison,
        title="Productivity Measures Comparison",
        ylabel=f"Index ({comparison.index[0]} = 100)",
        annotate=True,
        legend=LEGEND,
        tag="comparison",
        lfooter=f"{SA_CVM}L = hours worked. Y/L = (K/L) × (Y/K). {data_to(comparison)}",
        rfooter=rfooter,
        pre_tag="capital-productivity-",
    )
    line_plot_finalise(
        pd.DataFrame(
            {
                "Labour Productivity (Y/L)": labour.pct_change(periods=QUARTERS_PER_YEAR) * PERCENT,
                "Capital Deepening (K/L)": deepening.pct_change(periods=QUARTERS_PER_YEAR) * PERCENT,
                "Capital Productivity (Y/K)": productivity_growth["Annual growth"],
            }
        ).dropna(),
        title="Productivity Growth Comparison",
        ylabel="Per cent (YoY)",
        annotate=True,
        y0=True,
        legend=LEGEND,
        tag="growth-comparison",
        lfooter=f"{SA_CVM}L = hours worked. {data_to(comparison)}",
        rfooter=rfooter,
        pre_tag="capital-productivity-",
    )


# --- table of contents, in run order
CHARTS = (
    (capital_stock_comparison, ()),
    (capital_deepening, ()),
    (deepening_decade_averages, ()),
    (capital_productivity, ()),
)
