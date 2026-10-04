"""Okun's law: the stall speed, the GDP growth needed to hold the unemployment rate steady."""

# --- dependencies
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd
from mgplot import finalise_plot, line_plot, scatter_plot

from au_econ.releases.abs.modellers_database_1364.common import (
    BOTH_SOURCE,
    COVID_YEARS,
    PERCENT,
    QUARTERS_PER_YEAR,
    SA_CVM,
    data_to,
)

if TYPE_CHECKING:
    from au_econ.releases.abs.modellers_database_1364.common import ModellersData

# --- constants
GFC = 2008  # first year of the post-GFC era
ROLLING_YEARS = (15, 10)
MIN_SLOPE = -0.02  # flatter fits are skipped: the slope is unidentified
FAILURE_THRESHOLD = 1.5  # a stall speed below this marks the fit as unreliable
FAILURE_MERGE_GAP = 8  # quarters between unreliable runs that are merged into one span
EXPLANATION = (
    "Stall speed: the year-ended real GDP growth\n"
    "needed to hold the unemployment rate steady;\n"
    "an empirical proxy for potential output growth.\n"
    "Estimated from trailing {years}-year Okun fits.\n"
    "\n"
    "Note: the fit fails when a window contains\n"
    "insufficient variation in GDP growth: the slope\n"
    "is unidentified and the intercept meaningless."
)


# --- helpers
def _okun_data(data: ModellersData) -> pd.DataFrame:
    """Return year-ended real GDP growth ("g") and the year-ended change in the unemployment rate ("dur")."""
    gdp, _ = data.used["gdp_cvm"]
    unemployed, _ = data.used["unemployed"]
    labour_force, _ = data.used["labour_force"]
    rate = (unemployed / labour_force * PERCENT).dropna()
    return pd.DataFrame(
        {"g": gdp.pct_change(QUARTERS_PER_YEAR) * PERCENT, "dur": rate - rate.shift(QUARTERS_PER_YEAR)}
    ).dropna()


def _covid(frame: pd.DataFrame | pd.Series) -> np.ndarray:
    """Return a mask of the COVID quarters, which are left out of every fit."""
    if not isinstance(frame.index, pd.PeriodIndex):
        raise TypeError("Expected a PeriodIndex")
    first, last = COVID_YEARS
    return np.asarray((frame.index.year >= first) & (frame.index.year <= last))


def _failure_spans(stall: pd.Series) -> list[tuple[Any, Any]]:
    """Return spans (merging nearby runs) where the rolling estimate has collapsed or was skipped."""
    bad = ((stall < FAILURE_THRESHOLD) | stall.isna()) & ~_covid(stall)
    spans: list[tuple[Any, Any]] = []
    run_start = prev = None
    for q in stall.index[bad]:
        if run_start is None or prev is None:
            run_start = prev = q
            continue
        if q.ordinal - prev.ordinal <= FAILURE_MERGE_GAP:
            prev = q
        else:
            spans.append((run_start, prev))
            run_start = prev = q
    if run_start is not None:
        spans.append((run_start, prev))
    return spans


def _rolling_stall_speed(frame: pd.DataFrame, years: int, source: str) -> None:
    """Draw the stall speed re-estimated over trailing windows, unreliable periods shaded."""
    window = years * QUARTERS_PER_YEAR
    clean = frame[~_covid(frame)]
    dates, values = [], []
    for i in range(window, len(clean) + 1):
        sub = clean.iloc[i - window : i]
        slope, intercept = np.polyfit(sub["g"], sub["dur"], 1)
        dates.append(sub.index[-1])
        values.append(-intercept / slope if slope < MIN_SLOPE else np.nan)
    stall = pd.Series(values, index=pd.PeriodIndex(dates, freq="Q-DEC"), name="Stall speed")
    stall = stall.reindex(pd.period_range(stall.index[0], stall.index[-1], freq="Q-DEC"))

    spans: list[dict[str, Any]] = [
        {
            "xmin": pd.Period("2020Q1", freq="Q-DEC"),
            "xmax": pd.Period("2021Q4", freq="Q-DEC"),
            "color": "gold",
            "alpha": 0.25,
            "zorder": 0,
            "label": "COVID-19 (excluded from fits)",
        }
    ]
    for n, (start, end) in enumerate(_failure_spans(stall)):
        spans.append(
            {
                "xmin": start,
                "xmax": end,
                "color": "lightcoral",
                "alpha": 0.25,
                "zorder": 0,
                "label": "Fit unreliable (see note)" if n == 0 else "_nolegend_",
            }
        )
    ax = line_plot(stall, annotate=True, rounding=1)
    ax.text(
        0.02,
        0.97,
        EXPLANATION.format(years=years),
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize="x-small",
        fontstyle="italic",
        color="#333333",
    )
    finalise_plot(
        ax,
        title=f"Okun Stall Speed: {years}-Year Rolling Estimate",
        ylabel="Per cent per year",
        ylim=(-0.3, float(stall.max()) + 2.6),
        axvspan=spans,
        legend={"loc": "lower left", "fontsize": "x-small"},
        lfooter=f"{SA_CVM}{window}-quarter rolling OLS windows. {data_to(stall)}",
        rfooter=source,
    )


# --- charts
def okun_stall_speed(data: ModellersData) -> None:
    """Chart Okun's law by era with each era's stall speed, then the stall speed on rolling windows."""
    frame = _okun_data(data)
    source = BOTH_SOURCE
    covid_first, covid_last = COVID_YEARS
    covid = _covid(frame)
    if not isinstance(frame.index, pd.PeriodIndex):
        raise TypeError("Expected a PeriodIndex")
    years = frame.index.year
    eras = {
        f"{years[0]}-{GFC - 1}": (years < GFC, "darkorange"),
        f"{GFC}-{covid_first - 1}": ((years >= GFC) & (years < covid_first), "mediumseagreen"),
        f"{covid_last + 1}-present": (years > covid_last, "darkblue"),
    }
    present = list(eras)[-1]  # the open-ended era holds the latest quarter

    ax = scatter_plot(frame[covid], color="lightgrey", label=f"{covid_first}-{covid_last} (excluded from fits)")
    for era, (mask, color) in eras.items():
        sub = frame[mask & ~covid]
        slope, intercept = np.polyfit(sub["g"], sub["dur"], 1)
        scatter_plot(
            sub,
            ax=ax,
            color=color,
            fit=True,
            highlight_latest=era == present,
            label=f"{era}: stall speed {-intercept / slope:.1f}%",
        )
    finalise_plot(
        ax,
        title="Okun Stall Speed: GDP Growth Needed to\nHold the Unemployment Rate Steady",
        xlabel="Year-ended real GDP growth (per cent)",
        ylabel="Year-ended change in\nunemployment rate (ppt)",
        y0=True,
        legend={"loc": "upper right", "fontsize": "x-small"},
        lfooter=f"{SA_CVM}Quarterly observations. COVID excluded from fits. {data_to(frame)}",
        rfooter=source,
    )
    for rolling_years in ROLLING_YEARS:
        _rolling_stall_speed(frame, rolling_years, source)


# --- table of contents, in run order
CHARTS = ((okun_stall_speed, ()),)
