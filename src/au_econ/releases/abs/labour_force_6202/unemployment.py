"""Labour Force unemployment rate charts: long run, inflation regime, Sahm rule, conditions and the cash rate."""

# --- dependencies
from typing import TYPE_CHECKING, Any

import pandas as pd
from mgplot import finalise_plot, line_plot, line_plot_finalise, run_plot_finalise

from au_econ.charting.footers import SERIES_TYPE_NOTES
from au_econ.charting.inflation_backplane import (
    BACKPLANE_LHEADER,
    BACKPLANE_MONTHLY_LFOOTER,
    MONTHLY,
    inflation_backplane,
    quarterly_inflation,
)
from au_econ.charting.windows import MONTHS_PER_YEAR
from au_econ.releases.abs.labour_force_6202.common import (
    EMPLOYED,
    LABOUR_FORCE,
    MAIN,
    SEASONALLY_ADJUSTED,
    TREND,
    UNEMPLOYMENT_RATE,
    get_series,
    line_starts,
)
from au_econ.series.labour import get_unemployment_backcast_stats, get_unemployment_rate
from au_econ.series.rates import get_cash_rate

if TYPE_CHECKING:
    from au_econ.sources.abs import AbsRelease

# --- constants
PER_CENT_OF_LABOUR_FORCE = "Per cent of Labour Force"
SAHM_THRESHOLDS = (0.5, 0.6)  # percentage points above the prior 12-month minimum
SAHM_AVERAGE = 3  # months in the rolling average
SAHM_COLOUR, SAHM_ALPHA = "darkorange", 0.5
SAHM_LINE_COLOUR = "blue"
SAHM_LFOOTER = (
    "Australia. Seasonally adjusted. Monthly data. "
    "Current 3m MA compared with minimum over the prior 12 months (from current-12 to current-1)."
)
SAHM_RHEADER_VALUES = 3  # latest values shown in the header
CONDITIONS_THRESHOLD = 0.025  # turning-point threshold, percentage points
CONDITIONS_FROM = pd.Period("2001-08", freq="M")
HARDER, EASIER = "Getting harder to find a job", "Getting easier to find a job"
CONDITIONS = (("up", HARDER), ("down", EASIER), ("both", (HARDER, EASIER)))  # direction, highlight label
OCR_COMPARISON_FROM = "1993-01-01"


# --- helpers
def _runs(flags: pd.Series) -> list[tuple[pd.Period, pd.Period]]:
    """Return the (first, last) period of each run of True values."""
    index = flags.index
    if not isinstance(index, pd.PeriodIndex):
        raise TypeError(f"Expected a PeriodIndex, got {type(index).__name__}")
    runs: list[tuple[pd.Period, pd.Period]] = []
    start: pd.Period | None = None
    for position, (period, flag) in enumerate(zip(index, flags, strict=True)):
        if flag and start is None:
            start = period
        if start is not None and not flag:
            runs.append((start, index[position - 1]))
            start = None
    if start is not None:
        runs.append((start, index[-1]))
    return runs


def _sahm_chart(rate: pd.Series, threshold: float, source: str) -> tuple[pd.Series, pd.Series]:
    """Shade the months the 3-month average rose more than threshold above its prior 12-month minimum.

    Returns the 3-month average and the prior 12-month minimum.
    """
    average = rate.rolling(SAHM_AVERAGE).mean().rename("3 Month rolling average unemployment rate")
    minimum = average.rolling(MONTHS_PER_YEAR).min()
    prior_minimum = minimum.shift(1)  # the 12 months before the current one
    spans: list[dict[str, Any]] = [
        {"xmin": first, "xmax": last, "color": SAHM_COLOUR, "alpha": SAHM_ALPHA}
        for first, last in _runs(prior_minimum < average - threshold)
    ]
    if spans:
        spans[0]["label"] = f"Growth > {threshold} percentage points over minimum through the year"
    ax = line_plot(average, color=SAHM_LINE_COLOUR)

    def latest(series: pd.Series) -> str:
        return ", ".join(str(x) for x in series.iloc[-SAHM_RHEADER_VALUES:].round(2))

    finalise_plot(
        ax,
        title=f"Unemployment Rate: Rises over {threshold}pp Through the Year",
        ylabel=PER_CENT_OF_LABOUR_FORCE,
        y0=True,
        axvspan=spans,
        legend={"loc": "best", "fontsize": 8},
        rfooter=source,
        lfooter=SAHM_LFOOTER,
        rheader=f"Last 3 UER: {latest(rate)};  "
        f"Last 3m MA: {latest(average)};  "
        f"Last 3m minimum: {latest(minimum)};  "
        f"Forward headroom: {threshold - (average.iloc[-1] - minimum.iloc[-1]):.2f}",
    )
    return average, prior_minimum


# --- charts
def long_run_unemployment(release: AbsRelease) -> None:
    """Chart the unemployment rate spliced back to 1950, and print the backcast fit statistics."""
    rate, units, _stype = get_unemployment_rate()  # seasonally adjusted throughout
    fit = get_unemployment_backcast_stats()
    line_plot_finalise(
        rate,
        title="Australian Unemployment Rate: Long Run (1950 to current)",
        ylabel=units,
        annotate=True,
        rfooter=f"{release.source}, 1364.0.15.003; RBA: OP8",
        # abbreviated: the full wording runs into the rfooter
        lfooter="Australia. Seas adj. Monthly LFS over qtly Modellers' DB (pre-1978) "
        "over modelled CES rate (pre-1959). ",
        y0=True,
    )
    print(
        f"CES backcast fit: r2={fit['r2']:.3f}, resid_sd={fit['resid_sd']:.3f}, "
        f"n={fit['n']:.0f}; fitted over CES {fit['fitted_ces_min']:.1f}-"
        f"{fit['fitted_ces_max']:.1f}%, projected over CES "
        f"{fit['projected_ces_min']:.1f}-{fit['projected_ces_max']:.1f}%"
    )


def inflation_regime(release: AbsRelease) -> None:
    """Chart the unemployment rate over the inflation backplane, from the first trimmed mean month."""
    rate, units = get_series(release, MAIN, UNEMPLOYMENT_RATE, SEASONALLY_ADJUSTED)
    first_month = quarterly_inflation().index[0].asfreq(MONTHLY, how="start")
    rate = rate.dropna()
    rate = rate[rate.index >= first_month].rename("Unemployment rate")
    if rate.empty:
        raise ValueError(f"No unemployment rate data from {first_month}")
    for start in line_starts:
        data = rate.iloc[start:]
        if not isinstance(data.index, pd.PeriodIndex):
            raise TypeError(f"Expected a PeriodIndex, got {type(data.index)}")
        ax = line_plot(data, annotate=True, rounding=1)
        ax = inflation_backplane(data.index, ax)
        finalise_plot(
            ax,
            title="Unemployment Rate: Against the Inflation Regime",
            ylabel=units,
            lheader=BACKPLANE_LHEADER,
            legend={"loc": "best", "fontsize": "x-small", "ncol": 2},
            lfooter=f"Australia. {SERIES_TYPE_NOTES[SEASONALLY_ADJUSTED]} Monthly. {BACKPLANE_MONTHLY_LFOOTER}",
            rfooter=f"{release.source}, 6401.0",
            tag=f"start{start}",
        )


def sahm(release: AbsRelease) -> None:
    """Sahm rule: rises in the 3-month average unemployment rate over its prior 12-month minimum."""
    rate, _units = get_series(release, MAIN, UNEMPLOYMENT_RATE, SEASONALLY_ADJUSTED, exact_match=True)
    frame = pd.DataFrame()
    for threshold in SAHM_THRESHOLDS:
        average, prior_minimum = _sahm_chart(rate, threshold, release.source)
        frame["Unemployment Rate 3 month MA"] = average
        frame[f"Prior 12 month minimum + {threshold}pp"] = prior_minimum + threshold
    line_plot_finalise(
        frame,
        title=f"Unemployment Rate: Sahm Thresholds at {', '.join(f'+{x}pp' for x in SAHM_THRESHOLDS)}",
        ylabel=PER_CENT_OF_LABOUR_FORCE,
        y0=True,
        rfooter=release.source,
        lfooter=SAHM_LFOOTER,
        width=[2, 1.5, 1.5],
        style=["-", "-", "--"],
    )


def conditions(release: AbsRelease) -> None:
    """Highlight runs of rising and falling trend unemployment: a harder or easier market to find a job."""
    rate, _units = get_series(release, MAIN, UNEMPLOYMENT_RATE, TREND)
    rate = rate.rename("Unemployment rate")
    for direction, label in CONDITIONS:
        lfooter = (
            f"Australia. {SERIES_TYPE_NOTES[TREND]} Turning-point threshold = {CONDITIONS_THRESHOLD}pp. "
            + (
                "Blue=stronger (it is harder to find workers/easier to get a job). "
                if direction in ("down", "both")
                else ""
            )
            + ("Gold=weaker. " if direction in ("up", "both") else "")
        )
        run_plot_finalise(
            rate,
            direction=direction,
            threshold=CONDITIONS_THRESHOLD,
            plot_from=CONDITIONS_FROM,
            title="Unemployment Rate: Labour Market Conditions",
            ylabel=PER_CENT_OF_LABOUR_FORCE,
            lfooter=lfooter,
            rfooter=release.source,
            annotate=True,
            drawstyle=None,
            highlight_label=label,
            label_series=True,
            tag=direction,
        )


def unemployment_and_ocr(release: AbsRelease) -> None:
    """Compare the 12-month change in the unemployment rate with the 12-month change in the cash rate."""
    employed, _ = get_series(release, MAIN, EMPLOYED, SEASONALLY_ADJUSTED, exact_match=True)
    labour_force, _ = get_series(release, MAIN, LABOUR_FORCE, SEASONALLY_ADJUSTED, exact_match=True)
    rate = ((1 - employed / labour_force) * 100).dropna()
    rate_change = rate.diff(MONTHS_PER_YEAR)[OCR_COMPARISON_FROM:]
    cash_change = get_cash_rate().diff(MONTHS_PER_YEAR)[OCR_COMPARISON_FROM:]
    frame = pd.DataFrame(
        {
            "12 Month Change in Unemployment Rate": rate_change,
            "12 Month Change in RBA Cash Rate": cash_change,
        }
    )
    line_plot_finalise(
        frame,
        title="12 Month Change in Unemployment Rate & RBA OCR",
        ylabel="Percentage Points",
        annotate=True,
        rounding=2,
        y0=True,
        rfooter=f"{release.source}; RBA: A2",
        lfooter="Australia. Seasonally adjusted. UER and its 12 month difference "
        "calculated from the ABS LFS. RBA OCR on a monthly basis.",
        legend={"loc": "best", "fontsize": 9},
    )


# --- table of contents, in run order
CHARTS = (
    (long_run_unemployment, ()),
    (inflation_regime, ()),
    (sahm, ()),
    (conditions, ()),
    (unemployment_and_ocr, ()),
)
