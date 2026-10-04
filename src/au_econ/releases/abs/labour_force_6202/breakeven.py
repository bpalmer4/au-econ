"""Labour Force charts on the jobs needed to keep up: the participation counterfactual and breakeven growth."""

# --- dependencies
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import pandas as pd
from mgplot import bar_plot, bar_plot_finalise, finalise_plot, line_plot, line_plot_finalise

from au_econ.releases.abs.labour_force_6202.common import (
    CIVILIAN_POPULATION,
    EMPLOYED,
    LABOUR_FORCE,
    MAIN,
    ORIGINAL,
    PARTICIPATION_RATE,
    SEASONALLY_ADJUSTED,
    TREND,
    UNEMPLOYMENT_RATE,
    get_series,
    line_starts,
)
from au_econ.series.population import smoothed_monthly_pop_growth

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.typing import RcKeyType

    from au_econ.sources.abs import AbsRelease

# --- constants: the participation counterfactual
DOT_ROWS = (1, -1)  # number-line dots: first colour above the line, second below
DOT_SIZE, LABEL_OFFSET = 40, 5  # marker area; label gap in points
LINE_GAP = 2  # gap in points between the reference line and its label
X_PAD = 0.5  # padding each side of the dots, as a share of their span
MIN_SPAN = 0.2  # narrowest x-range, percentage points: flat months stay flat
LABEL_ROOM = 2.0  # dot panel y-limits as a multiple of the dot rows
RULE_WIDTH = 0.75  # number-line and reference-line width
ACTUAL, HELD = "Actual", "Counterfactual"
PAIR_COLOURS = ("darkblue", "darkorange")  # mgplot's two-series default, shared by bars and dots
COMPARED = 2  # last month and this month
PANEL_TEXT: dict[RcKeyType, str] = {  # the style's text sizes suit a single-panel chart; shrink them for panels
    "axes.titlesize": "small",
    "axes.labelsize": "small",
    "xtick.labelsize": "x-small",
    "ytick.labelsize": "small",
}

# --- constants: breakeven jobs growth
BE_PRE_TAG = "be-"
BE_DEFINITION = "Breakeven: jobs needed to keep UER and PR unchanged as the population grows."
BE_FORMULA = "Breakeven = PR x (1-UER) x growth in smoothed (quarterly-decomposed) civilian population 15+. "
PERIOD_TAGS = ("complete", "recent")
THOUSANDS_PER_MONTH = "Thousands per month"
BE_LEGEND = {"loc": "best", "fontsize": "small"}
BAR_COLOUR, BREAKEVEN_COLOUR = "darkorange", "navy"
BREAKEVEN_WIDTH = 2.5
GAP_COLOURS = ["seagreen", "darkred"]
RECENT_AVERAGE = 3  # months in the jobs growth average shown in the header


# --- helpers
def _latest_pair(release: AbsRelease, did: str, stype: str) -> pd.Series:
    """One LFS series by exact description, checked for a usable latest two months."""
    series, _units = get_series(release, MAIN, did, stype, exact_match=True)
    if len(series) < COMPARED or series.iloc[-COMPARED:].isna().any():
        raise ValueError(f"No usable latest two months for {did} ({stype})")
    return series


def _draw_dots(
    ax: Axes,
    above: tuple[str, float],
    below: tuple[str, float],
    *,
    reference: tuple[str, float] | None = None,
) -> tuple[float, float]:
    """Two labelled dots on a zoomed number line, one above and one below it.

    Dots rather than bars: a bar on an axis that does not start at zero misstates size. An
    optional reference (label, value) is labelled at the top of the panel; the caller draws
    its line (finalise_plot axvline). Returns an x-range spanning the dots and the reference,
    padded so the centred labels stay inside the panel, and never narrower than MIN_SPAN so a
    tiny change is not zoomed into a large-looking gap.
    """
    for (text, value), row, colour in zip((above, below), DOT_ROWS, PAIR_COLOURS, strict=True):
        ax.scatter([value], [row], color=colour, s=DOT_SIZE, zorder=3)
        ax.annotate(
            f"{text} {value:.2f}",
            (value, row),
            textcoords="offset points",
            xytext=(0, LABEL_OFFSET * row),
            ha="center",
            va="bottom" if row > 0 else "top",
            fontsize="x-small",
        )
    span = [above[1], below[1]]
    if reference is not None:
        ref_text, ref_value = reference
        ax.annotate(
            ref_text,
            (ref_value, 1),
            xycoords=("data", "axes fraction"),
            textcoords="offset points",
            xytext=(LINE_GAP, -LABEL_OFFSET),
            ha="left",
            va="top",
            rotation=90,
            fontsize="x-small",
            color="grey",
        )
        span.append(ref_value)
    low, high = min(span), max(span)
    pad = (high - low) * X_PAD
    low, high = low - pad, high + pad
    if high - low < MIN_SPAN:
        centre = (low + high) / 2
        low, high = centre - MIN_SPAN / 2, centre + MIN_SPAN / 2
    return low, high


def _bars_against_breakeven(frame: pd.DataFrame, *, title: str, lfooter: str, rheader: str, source: str) -> None:
    """Monthly jobs growth as bars, under the breakeven line, for each window."""
    for start, tag in zip(line_starts, PERIOD_TAGS, strict=True):
        subset = frame.iloc[start:]
        ax = bar_plot(subset.iloc[:, 0], color=BAR_COLOUR, annotate=False, label_series=True)
        line_plot(
            subset.iloc[:, 1], ax=ax, color=[BREAKEVEN_COLOUR], width=BREAKEVEN_WIDTH, annotate=True, rounding=0
        )
        finalise_plot(
            ax,
            title=title,
            ylabel=THOUSANDS_PER_MONTH,
            rfooter=source,
            lfooter=lfooter,
            lheader=BE_DEFINITION,
            rheader=rheader,
            legend=BE_LEGEND,
            y0=True,
            pre_tag=BE_PRE_TAG,
            tag=tag,
        )


# --- charts
def participation_counterfactual(release: AbsRelease) -> None:
    """Latest monthly change: actual against the participation rate held at last month.

    One figure: changes in labour force, employed and unemployed ('000) as bars across the
    top; below, the participation rate last month against this month, and this month's
    unemployment rate actual against counterfactual, as dots on zoomed number lines. The
    counterfactual labour force is last month's participation rate times this month's
    civilian population 15+, so actual less counterfactual labour force is exactly the
    participation rate change times the population. The actual population, not its smoothed
    trend: the published participation rate is taken on the same stepped population, so
    smoothing would leak into the counterfactual. Employment is held at actual, so every
    extra participant shows up as unemployed. Unemployed and the unemployment rate are derived
    from labour force less employed, so both panels add up.
    """
    employed = _latest_pair(release, EMPLOYED, SEASONALLY_ADJUSTED)
    labour_force = _latest_pair(release, LABOUR_FORCE, SEASONALLY_ADJUSTED)
    participation = _latest_pair(release, PARTICIPATION_RATE, SEASONALLY_ADJUSTED)
    population = _latest_pair(release, CIVILIAN_POPULATION, ORIGINAL)

    last_m, this_m = labour_force.index[-COMPARED:]
    lf_held = participation[last_m] / 100 * population[this_m]
    unemployed = labour_force - employed
    rate = unemployed / labour_force * 100
    rate_held = (lf_held - employed[this_m]) / lf_held * 100

    counts = pd.DataFrame(
        {
            ACTUAL: [
                labour_force[this_m] - labour_force[last_m],
                employed[this_m] - employed[last_m],
                unemployed[this_m] - unemployed[last_m],
            ],
            HELD: [
                lf_held - labour_force[last_m],
                employed[this_m] - employed[last_m],
                lf_held - employed[this_m] - unemployed[last_m],
            ],
        },
        index=["Labour force", "Employed", "Unemployed"],
    )
    base, month = last_m.strftime("%b"), this_m.strftime("%b")
    dot_ylim = (min(DOT_ROWS) * LABEL_ROOM, max(DOT_ROWS) * LABEL_ROOM)
    line = {"y": 0, "color": "grey", "linewidth": RULE_WIDTH}

    with plt.rc_context(PANEL_TEXT):
        _fig, axes = plt.subplot_mosaic([["counts", "counts"], ["pr", "ur"]])

        bar_plot(
            counts,
            ax=axes["counts"],
            horizontal=True,
            color=PAIR_COLOURS,
            annotate=True,
            above=False,
            rounding=1,
            fontsize="x-small",
        )
        axes["counts"].invert_yaxis()  # first row, and "Actual", on top
        finalise_plot(
            axes["counts"],
            axes_only=True,
            xlabel=f"Change from {base}, thousands",
            legend={"loc": "best", "fontsize": "x-small"},
            x0=True,
        )

        pr_xlim = _draw_dots(axes["pr"], (month, participation[this_m]), (base, participation[last_m]))
        finalise_plot(
            axes["pr"],
            axes_only=True,
            title=f"Participation rate: {base} vs {month}",
            xlabel="Per cent",
            xlim=pr_xlim,
            ylim=dot_ylim,
            yticks=[],
            axhline=line,
        )

        ur_xlim = _draw_dots(axes["ur"], (ACTUAL, rate[this_m]), (HELD, rate_held), reference=(base, rate[last_m]))
        finalise_plot(
            axes["ur"],
            title=f"Unemployment rate, {month}: {ACTUAL.lower()} vs {HELD.lower()}",
            xlabel="Per cent",
            xlim=ur_xlim,
            ylim=dot_ylim,
            yticks=[],
            axhline=line,
            axvline={"x": rate[last_m], "color": "grey", "linestyle": ":", "linewidth": RULE_WIDTH},
            suptitle=f"Labour market, {this_m.strftime('%b %Y')}: "
            "actual vs no change in participation rate counterfactual",
            rfooter=release.source,
            lfooter="Australia. Seasonally adjusted. Counterfactual: participation "
            f"rate held at {base}; employment held at actual. ",
        )


def breakeven(release: AbsRelease) -> None:
    """Monthly employment growth needed to hold the unemployment and participation rates.

    Breakeven(t) = PR(t) x (1 - UR(t)) x smoothed monthly civilian population growth (see
    series.population.smoothed_monthly_pop_growth). Five charts, each for two windows: SA
    and trend employment growth as bars against the breakeven line; trend jobs growth as a
    line against it; trend jobs growth above and below it; and smoothed population growth
    (with the raw monthly growth as a fine line) against it.
    """
    employed, _ = get_series(release, MAIN, EMPLOYED, SEASONALLY_ADJUSTED)
    trend_employed, _ = get_series(release, MAIN, EMPLOYED, TREND)
    population, _ = get_series(release, MAIN, CIVILIAN_POPULATION, ORIGINAL)
    rate = get_series(release, MAIN, UNEMPLOYMENT_RATE, SEASONALLY_ADJUSTED)[0] / 100
    participation = get_series(release, MAIN, PARTICIPATION_RATE, SEASONALLY_ADJUSTED)[0] / 100

    pop_growth = smoothed_monthly_pop_growth(population)
    breakeven_growth = (participation * (1 - rate) * pop_growth).dropna()

    # SA employment growth bars against the breakeven line
    frame = pd.DataFrame(
        {"Monthly change in employment (SA)": employed.diff(1), "Breakeven jobs growth": breakeven_growth}
    ).dropna()
    _bars_against_breakeven(
        frame,
        title="Employment growth vs breakeven jobs growth",
        lfooter="Australia. Jobs: seas adj. " + BE_FORMULA,
        rheader=f"Breakeven: {frame.iloc[-1, 1]:.0f}k/mth;  "
        f"{RECENT_AVERAGE}m avg jobs growth: {frame.iloc[-RECENT_AVERAGE:, 0].mean():.0f}k/mth",
        source=release.source,
    )

    # trend employment growth bars against the breakeven line
    frame = pd.DataFrame(
        {"Monthly change in employment (trend)": trend_employed.diff(1), "Breakeven jobs growth": breakeven_growth}
    ).dropna()
    _bars_against_breakeven(
        frame,
        title="Trend employment growth vs breakeven jobs growth",
        lfooter="Australia. Jobs: trend. " + BE_FORMULA,
        rheader=f"Breakeven: {frame.iloc[-1, 1]:.0f}k/mth;  trend jobs growth: {frame.iloc[-1, 0]:.0f}k/mth",
        source=release.source,
    )

    # trend jobs growth against the breakeven line
    trend_frame = pd.DataFrame(
        {"Trend jobs growth": trend_employed.diff(1), "Breakeven jobs growth": breakeven_growth}
    ).dropna()
    for start, tag in zip(line_starts, PERIOD_TAGS, strict=True):
        line_plot_finalise(
            trend_frame,
            plot_from=start,
            title="Trend jobs growth vs breakeven jobs growth",
            ylabel=THOUSANDS_PER_MONTH,
            color=[BAR_COLOUR, BREAKEVEN_COLOUR],
            annotate=True,
            rounding=0,
            rfooter=release.source,
            lfooter="Australia. Jobs: trend. " + BE_FORMULA,
            lheader=BE_DEFINITION,
            rheader=f"Trend jobs growth: {trend_frame.iloc[-1, 0]:.0f}k/mth;  "
            f"breakeven: {trend_frame.iloc[-1, 1]:.0f}k/mth",
            legend=BE_LEGEND,
            y0=True,
            pre_tag=BE_PRE_TAG,
            tag=tag,
        )

    # trend jobs growth above and below the breakeven rate
    gap = (trend_employed.diff(1) - breakeven_growth).dropna()
    gap_frame = pd.DataFrame({"Above breakeven": gap.clip(lower=0), "Below breakeven": gap.clip(upper=0)})
    for start, tag in zip(line_starts, PERIOD_TAGS, strict=True):
        bar_plot_finalise(
            gap_frame.iloc[start:],
            stacked=True,
            color=GAP_COLOURS,
            annotate=False,
            title="Trend jobs growth: above/below breakeven",
            ylabel=THOUSANDS_PER_MONTH,
            rfooter=release.source,
            lfooter="Australia. Jobs: trend. " + BE_FORMULA,
            lheader=BE_DEFINITION,
            rheader=f"Latest gap: {gap.iloc[-1]:+.0f}k/mth",
            legend=BE_LEGEND,
            y0=True,
            pre_tag=BE_PRE_TAG,
            tag=tag,
        )

    # smoothed population growth against the breakeven line, raw growth as a fine line
    pop_frame = pd.DataFrame(
        {
            "Smoothed civ. pop. 15+ growth": pop_growth,
            "Breakeven jobs growth": breakeven_growth,
            "Civ pop 15+ growth (raw)": population.diff(1),
        }
    ).dropna()
    for start, tag in zip(line_starts, PERIOD_TAGS, strict=True):
        line_plot_finalise(
            pop_frame,
            plot_from=start,
            title="Population growth vs breakeven jobs growth",
            ylabel=THOUSANDS_PER_MONTH,
            color=[BAR_COLOUR, BREAKEVEN_COLOUR, BAR_COLOUR],
            width=[2, 2, 0.75],
            annotate=[True, True, False],
            rounding=0,
            rfooter=release.source,
            lfooter="Australia. " + BE_FORMULA,
            lheader=BE_DEFINITION,
            rheader=f"Civ pop 15+ growth: {pop_frame.iloc[-1, 0]:.0f}k/mth;  "
            f"breakeven: {pop_frame.iloc[-1, 1]:.0f}k/mth",
            legend=BE_LEGEND,
            y0=True,
            pre_tag=BE_PRE_TAG,
            tag=tag,
        )


# --- table of contents, in run order
CHARTS = (
    (participation_counterfactual, ()),
    (breakeven, ()),
)
