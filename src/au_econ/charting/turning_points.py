"""Line charts of a daily series with its local highs and lows (and endpoint) labelled."""

import math
from typing import TYPE_CHECKING, Any

import mgplot as mg
import pandas as pd

from au_econ.analysis.turning_points import local_extremes

if TYPE_CHECKING:
    from matplotlib.axes import Axes

SIGNIFICANT_DIGITS = 3


def label_extremes(ax: Axes, annotations: pd.DataFrame) -> None:
    """Write each local high above, each low below, and the endpoint to the right."""
    rounding = max(SIGNIFICANT_DIGITS - math.floor(math.log10(annotations["val"].min())), 0)
    for idx, val, kind in zip(annotations["idx"], annotations["val"], annotations["kind"], strict=True):
        if not isinstance(idx, pd.Period):
            raise TypeError(f"annotation index {idx!r} is not a Period")
        va, ha = "center", "left"
        if kind in ("min", "max"):
            va, ha = ("top" if kind == "min" else "bottom"), "center"
        ax.text(idx.ordinal, val, f"{val:0.{rounding}f}", va=va, ha=ha, fontsize="x-small")


def turning_points_plot(
    series: pd.Series,
    *,
    plot_from: pd.Period | int | None = None,
    window: int | None = None,
    confirm: int | None = None,
    **kwargs: Any,
) -> None:
    """Chart a daily series from plot_from with its turning points labelled; kwargs go to finalise_plot.

    Takes plot_from as mgplot's multi_start passes it (a Period, or an int offset), so it
    can serve as multi_start's function. The turning points are those of the part shown;
    window and confirm (in observations) default to spans scaled to its length.
    """
    if isinstance(plot_from, pd.Period):
        shown = series[series.index >= plot_from]
    elif isinstance(plot_from, int):
        shown = series.iloc[plot_from:]
    else:
        shown = series
    ax = mg.line_plot(shown)
    label_extremes(ax, local_extremes(shown, window, confirm))
    mg.finalise_plot(ax, **kwargs)
