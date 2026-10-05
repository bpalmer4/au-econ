"""House-price drawdowns: every peak-to-trough fall of the long-run house-price level since 1970, nominal and real.

The level is the ABS splice extended back with BIS/REIA (series.housing), seasonally
adjusted; each episode is aligned at its peak, so the declines can be overlaid.
"""

# --- dependencies
from dataclasses import dataclass

import mgplot as mg
import pandas as pd

from au_econ.series.housing import get_house_price_index

# --- module contract
RELEASE = ("house-drawdowns",)
TOPICS = ("building",)
TITLE = "House Price Drawdowns"

# --- constants
SOURCE = "ABS: 6401.0, 6416.0, 6432.0; BIS: WS_SPP"
LFOOTER = "Australia. Seasonally adjusted. Mean dwelling price. "
MIN_DECLINE = 2.0  # per cent, peak to trough: shallower dips are quarterly noise, not episodes
ONGOING_STYLE, COMPLETE_STYLE = ":", "-"  # an episode not yet back to its peak may fall further
PERCENT = 100
YEAR_DIGITS = 100
LEGEND = {"loc": "lower left", "fontsize": "small", "ncol": 2}
ZERO_LINE = {"y": 0, "color": "darkgrey", "linewidth": 0.75}


@dataclass(frozen=True)
class HousePrices:
    """The seasonally adjusted long-run level, nominal and real, and the real level's units."""

    nominal: pd.Series
    real: pd.Series
    real_units: str


# --- data
def fetch() -> HousePrices:
    """Fetch the nominal and real seasonally adjusted levels, extended back with BIS/REIA."""
    nominal, _units, _stype = get_house_price_index(extend_bis=True, seasonally_adjusted=True)
    real, real_units, _stype = get_house_price_index(extend_bis=True, real=True, seasonally_adjusted=True)
    return HousePrices(nominal=nominal, real=real, real_units=real_units)


# --- helpers
def _next_recovery(series: pd.Series, start: int) -> int:
    """Return the first position after start where the series regains its level there (len(series) if never)."""
    peak = series.iloc[start]
    position = start + 1
    while position < len(series) and series.iloc[position] < peak:
        position += 1
    return position


def _episode_label(peak: pd.Period, trough: pd.Period) -> str:
    """Label an episode by the years it spans, e.g. 1989-96."""
    return f"{peak.year}-{trough.year % YEAR_DIGITS:02d}"


def drawdown_episodes(series: pd.Series, min_decline: float = MIN_DECLINE) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (paths, summary) for every peak-to-trough decline of at least min_decline per cent.

    An episode runs from a peak (a new high) to the lowest point before that peak is regained.
    The paths are per cent from the peak, indexed by quarters since it; the summary gives each
    episode's peak, trough, depth, length and whether it is still running.
    """
    index = series.index
    if not isinstance(index, pd.PeriodIndex):
        raise TypeError(f"Expected a PeriodIndex, got {type(index).__name__}")
    paths: dict[str, pd.Series] = {}
    rows: list[dict[str, object]] = []
    position = 0
    while position < len(series):
        recovery = _next_recovery(series, position)
        leg = series.iloc[position:recovery]
        trough_offset = int(leg.to_numpy().argmin())
        decline = (leg.iloc[trough_offset] / series.iloc[position] - 1) * PERCENT
        if -decline >= min_decline:
            path = (leg.iloc[: trough_offset + 1] / series.iloc[position] - 1) * PERCENT
            trough = leg.index[trough_offset]
            if not isinstance(trough, pd.Period):
                raise TypeError("Expected a Period")
            label = _episode_label(index[position], trough)
            paths[label] = pd.Series(path.to_numpy(), index=range(len(path)))
            rows.append(
                {
                    "Episode": label,
                    "Peak": index[position],
                    "Trough": trough,
                    "Decline %": round(decline, 2),
                    "Quarters": trough_offset,
                    "Ongoing": recovery == len(series),
                }
            )
        position = max(recovery, position + 1)
    return pd.DataFrame(paths), pd.DataFrame(rows).set_index("Episode")


def _plot_drawdowns(paths: pd.DataFrame, summary: pd.DataFrame, *, title: str, lfooter: str) -> None:
    """Overlay every decline episode, aligned at its peak; an ongoing episode is dotted."""
    styles = [ONGOING_STYLE if summary.loc[episode, "Ongoing"] else COMPLETE_STYLE for episode in paths.columns]
    mg.line_plot_finalise(
        paths,
        title=title,
        xlabel="Quarters since peak",
        ylabel="Per cent from peak",
        style=styles,
        annotate=False,
        dropna=True,
        legend=LEGEND,
        axhline=ZERO_LINE,
        rfooter=SOURCE,
        lfooter=lfooter,
    )


# --- charts
def nominal_drawdowns(data: HousePrices) -> None:
    """Chart nominal house-price drawdowns from each previous peak."""
    paths, summary = drawdown_episodes(data.nominal)
    print(summary)
    _plot_drawdowns(
        paths, summary, title="House Prices: Drawdowns from Previous Peak", lfooter=f"{LFOOTER}Nominal. "
    )


def real_drawdowns(data: HousePrices) -> None:
    """Chart real (CPI-deflated) house-price drawdowns from each previous peak."""
    paths, summary = drawdown_episodes(data.real)
    print(summary)
    _plot_drawdowns(
        paths,
        summary,
        title="Real House Prices: Drawdowns from Previous Peak",
        lfooter=f"{LFOOTER}CPI deflated, {data.real_units}. ",
    )


# --- table of contents, in run order
CHARTS = (
    (nominal_drawdowns, ()),
    (real_drawdowns, ()),
)
