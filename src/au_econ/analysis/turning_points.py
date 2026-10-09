"""Turning points: the local highs and lows of a daily series, alternating, plus its endpoint.

The search span is in observations. Left unset, it scales with the series length, so a
long history and a short window each get a similar number of turning points.
"""

from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from collections.abc import Hashable

SLIDE_DIVISOR = 2.9  # windows overlap: each starts window / 2.9 observations after the last
WINDOWS_PER_SERIES = 8  # a derived window is this fraction of the series length
CONFIRM_DIVISOR = 5  # a derived confirm span is window / 5
MIN_WINDOW = 15  # keeps a derived window's slide at least a few observations


def _holds(series: pd.Series, idx: Hashable, days: int, *, highest: bool) -> bool:
    """Return whether the value at idx is the highest (or lowest) within days each side."""
    pos = series.index.get_loc(idx)
    if not isinstance(pos, int):
        raise TypeError(f"{idx} is not a unique index label")
    around = series.iloc[max(pos - days, 0) : pos + days + 1]
    return bool(series.iloc[pos] == (around.max() if highest else around.min()))


def local_extremes(series: pd.Series, window: int | None = None, confirm: int | None = None) -> pd.DataFrame:
    """Local highs and lows of a daily series, alternating, plus its endpoint.

    Columns: "idx" (Period), "val" and "kind" ("min", "max" or "end"). Each overlapping
    window contributes its highest and lowest day, kept only if it holds for confirm
    days each side; a run of the same kind collapses to its most extreme member.
    Without window, it is the series length / WINDOWS_PER_SERIES (at least MIN_WINDOW);
    without confirm, it is window / CONFIRM_DIVISOR.
    """
    if not isinstance(series.index, pd.PeriodIndex):
        raise TypeError("series.index must be a PeriodIndex")
    if not series.index.is_unique or not series.index.is_monotonic_increasing:
        raise ValueError("series.index must be unique and increasing")
    if window is None:
        window = max(len(series) // WINDOWS_PER_SERIES, MIN_WINDOW)
    if confirm is None:
        confirm = window // CONFIRM_DIVISOR

    max_idx, min_idx = set(), set()
    slide = int(window / SLIDE_DIVISOR)
    minimum_window = int(window / 2)
    for i in range(0, len(series), slide):
        selection = series.iloc[i : i + window]
        if selection.isna().all():
            continue
        if len(selection) < minimum_window:
            break
        max_idx.add(selection.idxmax(skipna=True))
        min_idx.add(selection.idxmin())
    maximums = pd.PeriodIndex(sorted(idx for idx in max_idx if _holds(series, idx, confirm, highest=True)))
    minimums = pd.PeriodIndex(sorted(idx for idx in min_idx if _holds(series, idx, confirm, highest=False)))
    peaks = pd.DataFrame({"idx": maximums, "val": series[maximums], "kind": "max"}, index=maximums)
    troughs = pd.DataFrame({"idx": minimums, "val": series[minimums], "kind": "min"}, index=minimums)
    extremes = pd.concat([peaks, troughs]).sort_index(ascending=True)
    extremes = extremes[~extremes.index.duplicated(keep="last")]

    extremes["group"] = (extremes["kind"] != extremes["kind"].shift(1)).cumsum()
    reduced = extremes.groupby(["group", "kind"])["val"].agg(["min", "max", "idxmin", "idxmax"]).reset_index()
    annotations = pd.concat(
        [
            reduced[reduced["kind"] == "min"][["idxmin", "min", "kind"]].rename(
                columns={"idxmin": "idx", "min": "val"}
            ),
            reduced[reduced["kind"] == "max"][["idxmax", "max", "kind"]].rename(
                columns={"idxmax": "idx", "max": "val"}
            ),
        ]
    ).sort_values(by="idx")
    annotations.index = pd.Index(annotations["idx"])

    end = series.index[-1]
    if annotations.index[-1] == end:
        kinds = annotations["kind"].tolist()
        kinds[-1] = "end"
        return annotations.assign(kind=kinds)
    last = pd.DataFrame({"idx": [end], "val": [series.iloc[-1]], "kind": ["end"]}, index=pd.Index([end]))
    return pd.concat([annotations, last])
