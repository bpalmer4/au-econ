"""National Accounts productivity: labour productivity, a Solow residual, growth accounting and capital deepening.

The capital stock is built from GFCF by the perpetual inventory method, so these charts do not
wait on the Modellers' Database. A single 2.5 per cent depreciation rate understates the faster
depreciation of the IT, software and IP assets investment has shifted toward, which overstates
recent capital and so makes the recent fall in MFP look worse than it probably is.
"""

# --- dependencies
from typing import TYPE_CHECKING, Any

import pandas as pd
import readabs as ra
from mgplot import chart_subdir, line_plot_finalise, multi_start, series_growth_plot_finalise
from readabs import metacol as mc
from statsmodels.tsa.filters.hp_filter import hpfilter

from au_econ.analysis.henderson import hma
from au_econ.charting.windows import quarterly_plot_times
from au_econ.releases.abs.national_accounts_5206.common import (
    AUSTRALIA,
    CVM_NOTE,
    EXPENDITURE_VOLUME,
    INCOME_FROM_GDP,
    KEY_AGGS,
    QUARTERS_PER_YEAR,
    SA_NOTE,
    SEASONALLY_ADJUSTED,
    data_to,
)

if TYPE_CHECKING:
    from au_econ.sources.abs import AbsRelease

# --- constants
SUBDIR = "Productivity"
SA = SEASONALLY_ADJUSTED
PERCENT = 100
GROWTH_FROM = quarterly_plot_times[1]
HENDERSON_TERMS = 13
HP_LAMBDA = 1600  # quarterly data
ANNUAL_DEPRECIATION = 0.025
OPENING_STOCK_MULTIPLE = 40  # the opening capital stock, in quarters of the first GFCF
GDP_CVM_DID = "Gross domestic product: Chain volume measures ;"
HOURS_DID = "Hours worked: Index ;"
GDP_PER_HOUR_DID = "GDP per hour worked: Index ;"
GFCF_DID = "All sectors ;  Gross fixed capital formation ;"
COE_DID = "Compensation of employees ;"
PRODUCTIVITY_DIDS = {
    "GDP per hour worked": GDP_PER_HOUR_DID,
    "GVA per hour worked (Market sector)": "Gross value added per hour worked market sector: Index ;",
}
LEGEND = {"loc": "best", "fontsize": 9}
GVA_NOTE = "GVA = gross value added. "
MFP_NOTE = "MFP = multifactor productivity. "


# --- helpers
def _sa(release: AbsRelease, table: str, did: str, *, exact: bool = False, dollars: bool = False) -> pd.Series:
    """Return one seasonally adjusted series by description, without gaps."""
    selector = {table: mc.table, SA: mc.stype, did: mc.did} | ({"$": mc.unit} if dollars else {})
    _table, series_id, _units = ra.find_abs_id(release.meta, selector, exact_match=exact, verbose=False)
    return release.data[table][series_id].dropna()


def _pim_capital(release: AbsRelease) -> pd.Series:
    """Build a capital stock from all-sector GFCF by the perpetual inventory method."""
    gfcf = _sa(release, EXPENDITURE_VOLUME, GFCF_DID)
    depreciation = ANNUAL_DEPRECIATION / QUARTERS_PER_YEAR
    capital = pd.Series(index=gfcf.index, dtype=float)
    capital.iloc[0] = gfcf.iloc[0] * OPENING_STOCK_MULTIPLE
    for i in range(1, len(gfcf)):
        capital.iloc[i] = (1 - depreciation) * capital.iloc[i - 1] + gfcf.iloc[i]
    return capital


def _gdp_and_hours(release: AbsRelease) -> tuple[pd.Series, pd.Series]:
    """Return chain volume GDP and the hours worked index."""
    return _sa(release, KEY_AGGS, GDP_CVM_DID, dollars=True), _sa(release, KEY_AGGS, HOURS_DID)


def _hp_trend(series: pd.Series) -> pd.Series:
    """Return the Hodrick-Prescott trend of a quarterly series."""
    return pd.Series(hpfilter(series, lamb=HP_LAMBDA)[1], index=series.index)


# --- charts
def labour_productivity(release: AbsRelease) -> None:
    """GDP and market sector GVA per hour worked: levels, growth, compared, and long-run growth trends."""
    footers: dict[str, Any] = {"rfooter": release.source, "pre_tag": "productivity-"}

    def common(title: str, data: pd.Series | pd.DataFrame) -> dict[str, Any]:
        gva = GVA_NOTE if "GVA" in title else ""
        return footers | {"lfooter": f"{AUSTRALIA}{SA_NOTE}{CVM_NOTE}{gva}{data_to(data)}"}

    productivity = {}
    with chart_subdir(SUBDIR):
        for label, did in PRODUCTIVITY_DIDS.items():
            _table, series_id, units = ra.find_abs_id(
                release.meta, {KEY_AGGS: mc.table, SA: mc.stype, did: mc.did}, verbose=False
            )
            series = release.data[KEY_AGGS][series_id].dropna()
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
        for label, series in productivity.items():
            growth = (series.pct_change(periods=QUARTERS_PER_YEAR) * PERCENT).dropna()
            line_plot_finalise(
                pd.DataFrame(
                    {"Annual growth": growth, f"{HENDERSON_TERMS}-term HMA": hma(growth, HENDERSON_TERMS)}
                ),
                title=f"Long-run Growth Trends: {label}",
                ylabel="Per cent growth (YoY)",
                width=[1, 3],
                annotate=[False, True],
                y0=True,
                legend=LEGEND,
                tag="long-run",
                **common(label, growth),
            )


def mfp(release: AbsRelease) -> None:
    """Chart MFP as a Solow residual: level and growth with trends, and against labour productivity."""
    gdp, hours = _gdp_and_hours(release)
    coe = _sa(release, INCOME_FROM_GDP, COE_DID, exact=True)
    tfi = _sa(release, INCOME_FROM_GDP, "Total factor income ;", exact=True)
    alpha = (coe / tfi).dropna().mean()  # the long-run labour share
    capital = _pim_capital(release)

    l_norm, k_norm, y_norm = hours / hours.iloc[0], capital / capital.iloc[0], gdp / gdp.iloc[0]
    level = (y_norm / (l_norm**alpha * k_norm ** (1 - alpha)) * PERCENT).dropna()
    growth = (level.pct_change(periods=QUARTERS_PER_YEAR) * PERCENT).dropna()
    growth_hp, growth_hma = _hp_trend(growth), hma(growth, HENDERSON_TERMS)

    lfooter = f"{AUSTRALIA}{SA_NOTE}{CVM_NOTE}Solow residual. Capital stock via PIM (2.5% p.a. depreciation). "
    common: dict[str, Any] = {
        "rfooter": f"{release.source}",
        "lfooter": f"{lfooter}{data_to(level)}",
        "pre_tag": "mfp-",
    }
    trends: dict[str, Any] = {"width": [1, 2, 2], "annotate": [False, False, True], "legend": LEGEND}
    with chart_subdir(SUBDIR):
        line_plot_finalise(
            pd.DataFrame(
                {
                    "MFP (Solow Residual)": level,
                    "HP Filter Trend": _hp_trend(level),
                    f"{HENDERSON_TERMS}-term Henderson MA": hma(level, HENDERSON_TERMS),
                }
            ).dropna(),
            title="Multifactor Productivity (Solow Residual)",
            ylabel="Index",
            **trends,
            **common,
        )
        line_plot_finalise(
            pd.DataFrame(
                {
                    "MFP Growth (YoY)": growth,
                    "HP Filter Trend": growth_hp,
                    f"{HENDERSON_TERMS}-term Henderson MA": growth_hma,
                }
            ).dropna(),
            title="MFP Growth with Smoothed Trends",
            ylabel="Per cent (YoY)",
            y0=True,
            tag="growth",
            **trends,
            **(
                common
                | {
                    "lfooter": f"{AUSTRALIA}{SA_NOTE}{CVM_NOTE}Solow residual, PIM capital. "
                    f"{MFP_NOTE}{data_to(growth)}"
                }
            ),
        )
        comparison = pd.DataFrame(
            {"Labour Productivity": _sa(release, KEY_AGGS, GDP_PER_HOUR_DID), "MFP (Solow Residual)": level}
        ).dropna()
        line_plot_finalise(
            comparison / comparison.iloc[0] * PERCENT,
            title="Labour Productivity vs Multifactor Productivity",
            ylabel="Index (start = 100)",
            annotate=True,
            legend=LEGEND,
            tag="vs-lp",
            **common,
        )

    print(f"Labour share (α): {alpha:.3f}")
    print(f"MFP level (latest): {level.iloc[-1]:.1f}")
    print(f"MFP growth (latest YoY): {growth.iloc[-1]:.2f}%")
    print(f"MFP trend growth (HP, latest): {growth_hp.iloc[-1]:.2f}%")
    print(f"MFP trend growth (HMA, latest): {growth_hma.iloc[-1]:.2f}%")


def gdp_decomposition(release: AbsRelease) -> None:
    """Solow growth accounting: GDP growth split into labour, capital and MFP contributions."""
    gdp, hours = _gdp_and_hours(release)
    coe = _sa(release, INCOME_FROM_GDP, COE_DID, exact=True)
    gos = _sa(release, INCOME_FROM_GDP, "Total corporations ;  Gross operating surplus ;", exact=True)
    alpha = (gos / (gos + coe)).dropna().mean()  # the capital share
    capital = _pim_capital(release)

    contributions = pd.DataFrame(
        {
            "GDP Growth": gdp.pct_change(periods=QUARTERS_PER_YEAR) * PERCENT,
            "Labour": ((1 - alpha) * (hours.pct_change(periods=QUARTERS_PER_YEAR) * PERCENT)).dropna(),
            "Capital": (alpha * (capital.pct_change(periods=QUARTERS_PER_YEAR) * PERCENT)).dropna(),
        }
    ).dropna()
    contributions["MFP"] = contributions["GDP Growth"] - contributions["Labour"] - contributions["Capital"]
    parts = ["Labour", "Capital", "MFP"]

    common: dict[str, Any] = {
        "rfooter": f"{release.source}",
        "lfooter": f"{AUSTRALIA}{SA_NOTE}{CVM_NOTE}ΔY = (1-α)ΔL + αΔK + ΔMFP, "
        f"α = {alpha:.2f} (capital share). PIM capital. {data_to(contributions)}",
        "pre_tag": "gdp-decomp-",
        "ylabel": "Percentage points",
        "annotate": True,
        "y0": True,
        "legend": LEGEND,
    }
    with chart_subdir(SUBDIR):
        line_plot_finalise(
            contributions[parts], title="GDP Growth Contributions (YoY)", tag="contributions", **common
        )
        line_plot_finalise(
            pd.DataFrame({col: hma(contributions[col], HENDERSON_TERMS) for col in parts}),
            title=f"GDP Growth Contributions ({HENDERSON_TERMS}-term Henderson MA)",
            tag="contributions-hma",
            **common,
        )

    print(f"\nCapital share (α): {alpha:.3f}")
    print(f"Labour share (1-α): {1 - alpha:.3f}")
    print("\nLatest contributions (YoY):")
    for column in ("GDP Growth", *parts):
        print(f"  {column}: {contributions[column].iloc[-1]:.2f}")


def capital_deepening(release: AbsRelease) -> None:
    """Capital per hour worked and output per unit of capital, and both against labour productivity."""
    gdp, hours = _gdp_and_hours(release)
    capital = _pim_capital(release)
    y_norm = gdp / gdp.iloc[0] * PERCENT
    k_norm = capital / capital.iloc[0] * PERCENT
    l_norm = hours / hours.iloc[0] * PERCENT

    deepening = (k_norm / l_norm * PERCENT).dropna()
    deepening.name = "Capital Deepening (K/L)"
    capital_productivity = (y_norm / k_norm * PERCENT).dropna()
    capital_productivity.name = "Capital Productivity (Y/K)"
    deepening_growth = (deepening.pct_change(periods=QUARTERS_PER_YEAR) * PERCENT).dropna()
    comparison = pd.DataFrame(
        {
            "Labour Productivity (Y/L)": (y_norm / l_norm * PERCENT).dropna(),
            "Capital Deepening (K/L)": deepening,
            "Capital Productivity (Y/K)": capital_productivity,
        }
    ).dropna()
    comparison = comparison / comparison.iloc[0] * PERCENT  # each series starts at 100

    kl: dict[str, Any] = {
        "rfooter": f"{release.source}",
        "lfooter": f"{AUSTRALIA}{SA_NOTE}{CVM_NOTE}PIM capital per hour worked (indexed). {data_to(deepening)}",
        "pre_tag": "capital-deepening-",
    }
    with chart_subdir(SUBDIR):
        multi_start(
            deepening,
            function=line_plot_finalise,
            starts=quarterly_plot_times,
            title="Capital Deepening (Capital per Hour Worked)",
            ylabel=f"Index ({deepening.index[0]} = 100)",
            annotate=True,
            **kl,
        )
        line_plot_finalise(
            pd.DataFrame(
                {
                    "Annual growth": deepening_growth,
                    f"{HENDERSON_TERMS}-term HMA": hma(deepening_growth, HENDERSON_TERMS),
                }
            ),
            title="Capital Deepening Growth",
            ylabel="Per cent (YoY)",
            width=[1, 3],
            annotate=[False, True],
            y0=True,
            legend=LEGEND,
            tag="growth",
            **kl,
        )
        multi_start(
            capital_productivity,
            function=line_plot_finalise,
            starts=quarterly_plot_times,
            title="Capital Productivity (Output per Unit of Capital)",
            ylabel=f"Index ({capital_productivity.index[0]} = 100)",
            annotate=True,
            rfooter=f"{release.source}",
            lfooter=f"{AUSTRALIA}{SA_NOTE}{CVM_NOTE}PIM output per unit of capital (indexed). "
            f"{data_to(capital_productivity)}",
            pre_tag="capital-productivity-",
        )
        line_plot_finalise(
            comparison,
            title="Productivity Measures Comparison",
            ylabel=f"Index ({comparison.index[0]} = 100)",
            annotate=True,
            legend=LEGEND,
            tag="comparison",
            lfooter=f"{AUSTRALIA}{SA_NOTE}{CVM_NOTE}PIM capital. L = hours worked. Y/L = (K/L) × (Y/K). "
            f"{data_to(comparison)}",
            rfooter=f"{release.source}",
            pre_tag="capital-productivity-",
        )

    print(f"Capital deepening (latest): {deepening.iloc[-1]:.1f}")
    print(f"Capital productivity (latest): {capital_productivity.iloc[-1]:.1f}")


# --- table of contents, in run order
CHARTS = (
    (labour_productivity, ()),
    (mfp, ()),
    (gdp_decomposition, ()),
    (capital_deepening, ()),
)
