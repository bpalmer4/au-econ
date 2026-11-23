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
from au_econ.series.rates import INTERBANK_TABLE, get_cash_rate, get_interbank_rate

if TYPE_CHECKING:
    from au_econ.sources.abs import AbsRelease

# --- constants
PER_CENT_OF_LABOUR_FORCE = "Per cent of Labour Force"
SAHM_THRESHOLDS = (0.5, 0.75)  # percentage points above the prior 12-month minimum
SAHM_AVERAGE = 3  # months in the rolling average
SAHM_COLOUR, SAHM_ALPHA = "darkorange", 0.5
SAHM_LINE_COLOUR = "blue"
SAHM_LFOOTER = (
    "Australia. Seasonally adjusted. Monthly data. Current 3m MA vs prior 12-month minimum (months -12 to -1)."
)
SAHM_RHEADER_VALUES = 3  # latest values shown in the header
POLICY_MONTHS = 6  # the backplane shades the change in the interbank rate over this many months
POLICY_DEADBAND = 0.1  # percentage points: smaller changes are left unshaded
POLICY_STEPS = (1.0, 2.0)  # percentage points where the shading steps darker
POLICY_ALPHAS = (0.08, 0.16, 0.25)  # one alpha per step, smallest change first
POLICY_DIRECTIONS = {"Tightening": "tab:red", "Easing": "tab:green"}
POLICY_LHEADER = f"Shaded by the {POLICY_MONTHS}-month change in the interbank overnight rate"
CONDITIONS_THRESHOLD = 0.025  # turning-point threshold, percentage points
CONDITIONS_FROM = pd.Period("2001-08", freq="M")
HARDER, EASIER = "Getting harder to find a job", "Getting easier to find a job"
CONDITIONS = (("up", HARDER), ("down", EASIER), ("both", (HARDER, EASIER)))  # direction, highlight label
OCR_COMPARISON_FROM = "1993-01-01"


# --- helpers
def _policy_spans(index: pd.PeriodIndex) -> list[dict[str, Any]]:
    """Return finalise_plot axvspan dicts shading the months in index by monetary policy direction.

    Each month is shaded by the change in the interbank overnight rate over the POLICY_MONTHS
    to it: red for tightening, green for easing, darker at each of POLICY_STEPS, and unshaded
    within POLICY_DEADBAND of no change. Zero-width labelled key spans lead, for the legend;
    then one span per run of consecutive months at the same direction and step.
    """
    rate = get_interbank_rate()
    change = (rate - rate.shift(POLICY_MONTHS)).reindex(index)
    edges = (POLICY_DEADBAND, *POLICY_STEPS)
    spans: list[dict[str, Any]] = []
    for direction, colour in POLICY_DIRECTIONS.items():
        for step, alpha in enumerate(POLICY_ALPHAS):
            label = (
                f"{direction} {edges[step]:g}pp+"
                if step + 1 == len(edges)
                else f"{direction} {edges[step]:g}-{edges[step + 1]:g}pp"
            )
            spans.append(
                {
                    "xmin": index[0],
                    "xmax": index[0],
                    "color": colour,
                    "alpha": alpha,
                    "linewidth": 0,
                    "label": label,
                }
            )

    # (direction, step) for each month; None where unshaded
    shades = [
        None
        if pd.isna(value) or abs(value) <= POLICY_DEADBAND
        else ("Tightening" if value > 0 else "Easing", sum(abs(value) >= edge for edge in POLICY_STEPS))
        for value in change.to_numpy(dtype=float)
    ]
    run_start = 0
    for position in range(1, len(shades) + 1):
        if position < len(shades) and shades[position] == shades[run_start]:
            continue
        shade = shades[run_start]
        if shade is not None:
            direction, step = shade
            spans.append(
                {
                    "xmin": index[run_start],
                    "xmax": index[position - 1] + 1,
                    "color": POLICY_DIRECTIONS[direction],
                    "alpha": POLICY_ALPHAS[step],
                    "linewidth": 0,
                    "zorder": 0,
                }
            )
        run_start = position
    return spans


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
    distances = pd.DataFrame()  # how far the 3-month average sits above each trigger level
    for threshold in SAHM_THRESHOLDS:
        # shade the months the 3-month average rose more than threshold above its prior 12-month minimum
        average = rate.rolling(SAHM_AVERAGE).mean().rename("3 Month rolling average unemployment rate")
        minimum = average.rolling(MONTHS_PER_YEAR).min()
        prior_minimum = minimum.shift(1)  # the 12 months before the current one
        flags = prior_minimum < average - threshold
        index = flags.index
        if not isinstance(index, pd.PeriodIndex):
            raise TypeError(f"Expected a PeriodIndex, got {type(index).__name__}")
        runs: list[tuple[pd.Period, pd.Period]] = []  # (first, last) of each run of flagged months
        start: pd.Period | None = None
        for position, (period, flag) in enumerate(zip(index, flags, strict=True)):
            if flag and start is None:
                start = period
            if start is not None and not flag:
                runs.append((start, index[position - 1]))
                start = None
        if start is not None:
            runs.append((start, index[-1]))
        spans: list[dict[str, Any]] = [
            {"xmin": first, "xmax": last + 1, "color": SAHM_COLOUR, "alpha": SAHM_ALPHA} for first, last in runs
        ]
        if spans:
            spans[0]["label"] = f"Growth > {threshold} percentage points over minimum through the year"
        ax = line_plot(average, color=SAHM_LINE_COLOUR)
        recent = {
            name: ", ".join(str(x) for x in series.iloc[-SAHM_RHEADER_VALUES:].round(2))
            for name, series in (("rate", rate), ("average", average), ("minimum", minimum))
        }
        finalise_plot(
            ax,
            title=f"Unemployment Rate: Rises over {threshold}pp Through the Year",
            ylabel=PER_CENT_OF_LABOUR_FORCE,
            y0=True,
            axvspan=spans,
            legend={"loc": "best", "fontsize": 8},
            rfooter=release.source,
            lfooter=SAHM_LFOOTER,
            rheader=f"Last 3 UER: {recent['rate']};  "
            f"Last 3m MA: {recent['average']};  "
            f"Last 3m minimum: {recent['minimum']};  "
            f"Forward headroom: {threshold - (average.iloc[-1] - minimum.iloc[-1]):.3f}",
        )
        frame["Unemployment Rate 3 month MA"] = average
        frame[f"Prior 12 month minimum + {threshold}pp"] = prior_minimum + threshold
        distances[f"Sahm rule at +{threshold}pp"] = average - (prior_minimum + threshold)
    line_plot_finalise(
        frame,
        title=f"Unemployment Rate: Sahm Thresholds at {', '.join(f'+{x}pp' for x in SAHM_THRESHOLDS)}",
        ylabel=PER_CENT_OF_LABOUR_FORCE,
        y0=True,
        rfooter=release.source,
        lfooter=SAHM_LFOOTER,
        width=[2, 1.5, 1.5, 1.5],
        style=["-", "-", "--", ":"],
    )
    line_plot_finalise(
        distances,
        title="Unemployment Rate: Sahm Rule Distance Above Thresholds",
        ylabel="Percentage points",
        y0=True,
        annotate=True,
        rounding=3,
        rfooter=release.source,
        lfooter=SAHM_LFOOTER,
    )
    distances = distances.dropna(how="all")  # the first 3 + 12 months have no indicator
    distance_index = distances.index
    if not isinstance(distance_index, pd.PeriodIndex):
        raise TypeError(f"Expected a PeriodIndex, got {type(distance_index).__name__}")
    ax = line_plot(distances, annotate=True, rounding=3)
    finalise_plot(
        ax,
        title="Unemployment Rate: Sahm Rule Distance Above Thresholds",
        ylabel="Percentage points",
        y0=True,
        axvspan=_policy_spans(distance_index),
        legend={"loc": "upper right", "fontsize": "x-small", "ncol": 2},
        lheader=POLICY_LHEADER,
        rfooter=f"{release.source}; RBA: {INTERBANK_TABLE}",
        lfooter=SAHM_LFOOTER,
        tag="monetary-policy",
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
