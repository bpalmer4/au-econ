"""RBA exchange rates: each currency against the Australian dollar, recent and long-run.

Tables: F11.1 (daily, from 2023) and the daily history workbooks Z:F11.1-Daily* (from
December 1983), as listed in readabs' RBA catalogue. The history marks closed markets
with text ("Closed", "CLOSED", " --", ""), which become missing values.
"""

# --- dependencies
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import mgplot as mg
import numpy as np
import pandas as pd
import readabs as ra
from babel.numbers import get_currency_name

from au_econ.sources import rba

if TYPE_CHECKING:
    from collections.abc import Hashable

    from matplotlib.axes import Axes

# --- module contract
RELEASE = ("rba-fx",)
TOPICS = ("rba",)
TITLE = "Exchange Rates"

# --- constants
TABLE = "F11.1"
SOURCE = f"RBA: {TABLE}"  # the history workbooks are F11.1's own history
GEOGRAPHY = "Australia"
BASKET_NOTE = "Published only while in the TWI basket."
GAP_DAYS = 30  # a gap longer than this between quotes is a spell outside the basket, not a holiday
HISTORY_PREFIX = "Z:F11.1-Daily"
NOTES_SUFFIX = "; see notes for further detail."
CLOSED_MARKERS = {"Closed": np.nan, "": np.nan, " --": np.nan, "CLOSED": np.nan}
PLURAL_WORDS = ("Dollar", "Pound", "Euro", "Rupee", "Franc", "Peso")  # currency names taking an "s"
CURRENCY_LOCALE = "en_AU"
AUD_PREFIX = "AUD/"
CODE_LENGTH = 3
PRE_TAG = "f11.1-"
RECENT_WIDTH = 1.5

# local highs and lows
EXTREMES_WINDOW = 150  # days in each search window
SLIDE_DIVISOR = 2.9  # windows overlap: each starts window / 2.9 days after the last
CONFIRM_DAYS = 30  # a high or low must hold for this many days each side
SIGNIFICANT_DIGITS = 3

# the trade-weighted index over a longer span
TWI_NAME = "Trade-weighted Index"
TWI_YEARS = 10
TWI_EXTREMES_WINDOW = 250  # about a year of trading days
TWI_CONFIRM_DAYS = 60
TWI_TAG = "-ten-year"


@dataclass(frozen=True)
class FxData:
    """The current F11.1 table and the joined daily history, with each history series' title and unit."""

    current: pd.DataFrame
    current_meta: pd.DataFrame
    history: pd.DataFrame
    names: dict[str, str]
    units: dict[str, str]


# --- data
def _history_tables() -> list[str]:
    """Return the daily history workbooks' table names, in catalogue order."""
    catalogue = ra.rba_catalogue()
    tables = [str(name) for name in catalogue.index if str(name).startswith(HISTORY_PREFIX)]
    if not tables:
        raise ValueError(f"RBA catalogue lists no {HISTORY_PREFIX} tables")
    return tables


def fetch() -> FxData:
    """Fetch F11.1 and join the daily history workbooks into one frame of numbers."""
    current, current_meta = rba.get_table(TABLE)
    parts = []
    names: dict[str, str] = {}
    units: dict[str, str] = {}
    for table in _history_tables():
        data, meta = rba.get_table(table)
        data = data.loc[:, data.columns.notna()]
        data = data.replace(CLOSED_MARKERS).dropna(how="all", axis=0).astype(float)
        for series_id in meta.index:
            names.setdefault(series_id, str(meta.at[series_id, ra.rba_metacol.desc]).replace(NOTES_SUFFIX, ""))
            units.setdefault(series_id, str(meta.at[series_id, ra.rba_metacol.unit]))
        parts.append(data)
    history = pd.concat(parts, axis=0).sort_index()
    return FxData(current=current, current_meta=current_meta, history=history, names=names, units=units)


# --- helpers
def _currency(title: str) -> tuple[str, str]:
    """Return the currency named by an "AUD/XXX" title, singular and plural; empty for other titles."""
    title = title.strip()
    singular = ""
    if title.startswith(AUD_PREFIX):
        singular = get_currency_name(
            title[len(AUD_PREFIX) : len(AUD_PREFIX) + CODE_LENGTH], locale=CURRENCY_LOCALE
        )
    plural = singular + "s" if any(word in singular for word in PLURAL_WORDS) else singular
    return singular, plural


def _lfooter(title: str, last: pd.Period) -> str:
    """Return the left footer: geography (unless the title names it), last date, what one AUD buys."""
    lfooter = "" if GEOGRAPHY in title else f"{GEOGRAPHY}. "
    lfooter += f"Data to {last}. "
    if AUD_PREFIX in title:
        _, plural = _currency(title)
        lfooter += f"What one Australian Dollar buys in {plural}. "
    return lfooter


def _lheader(series: pd.Series, last: pd.Period, first: pd.Period | None = None) -> str:
    """Return the basket note when the rate stops before the table's last day or has a long gap.

    With first, a blank start longer than GAP_DAYS from that day also counts; without it,
    a late start (a new currency, or wider coverage) does not.
    """
    quotes = series.dropna().index
    if quotes.empty:
        return ""
    if first is not None:
        quotes = quotes.insert(0, first)
    gaps = (quotes[1:] - quotes[:-1]).map(lambda offset: offset.n)
    if quotes[-1] < last or (len(gaps) and max(gaps) > GAP_DAYS):
        return BASKET_NOTE
    return ""


def _holds(series: pd.Series, idx: Hashable, days: int, *, highest: bool) -> bool:
    """Return whether the value at idx is the highest (or lowest) within days each side."""
    pos = series.index.get_loc(idx)
    if not isinstance(pos, int):
        raise TypeError(f"{idx} is not a unique index label")
    around = series.iloc[max(pos - days, 0) : pos + days + 1]
    return bool(series.iloc[pos] == (around.max() if highest else around.min()))


def _local_extremes(series: pd.Series, window: int = EXTREMES_WINDOW, confirm: int = CONFIRM_DAYS) -> pd.DataFrame:
    """Local highs and lows of a daily series, alternating, plus its endpoint.

    Columns: "idx" (Period), "val" and "kind" ("min", "max" or "end"). Each overlapping
    window contributes its highest and lowest day, kept only if it holds for confirm
    days each side; a run of the same kind collapses to its most extreme member.
    """
    if not isinstance(series.index, pd.PeriodIndex):
        raise TypeError("series.index must be a PeriodIndex")
    if not series.index.is_unique or not series.index.is_monotonic_increasing:
        raise ValueError("series.index must be unique and increasing")

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


def _label_extremes(ax: Axes, annotations: pd.DataFrame) -> None:
    """Write each local high above, each low below, and the endpoint to the right."""
    rounding = max(SIGNIFICANT_DIGITS - math.floor(math.log10(annotations["val"].min())), 0)
    for idx, val, kind in zip(annotations["idx"], annotations["val"], annotations["kind"], strict=True):
        if not isinstance(idx, pd.Period):
            raise TypeError(f"annotation index {idx!r} is not a Period")
        va, ha = "center", "left"
        if kind in ("min", "max"):
            va, ha = ("top" if kind == "min" else "bottom"), "center"
        ax.text(idx.ordinal, val, f"{val:0.{rounding}f}", va=va, ha=ha, fontsize="x-small")


def _labelled_chart(
    series: pd.Series,
    title: str,
    ylabel: str,
    lheader: str,
    *,
    window: int = EXTREMES_WINDOW,
    confirm: int = CONFIRM_DAYS,
    tag: str = "",
) -> None:
    """Chart a daily exchange rate with its local highs and lows labelled."""
    ax = mg.line_plot(series, width=RECENT_WIDTH, dropna=False)
    _label_extremes(ax, _local_extremes(series, window, confirm))
    mg.finalise_plot(
        ax,
        title=title,
        ylabel=ylabel,
        lfooter=_lfooter(title, series.index[-1]),
        lheader=lheader,
        rfooter=SOURCE,
        pre_tag=PRE_TAG,
        tag=tag,
    )


# --- charts
def short_run_exchange_rates(data: FxData) -> None:
    """Chart each F11.1 exchange rate since 2023, and the trade-weighted index over ten years.

    Each chart labels its local highs and lows; the ten-year chart searches wider windows
    and confirms each over more days.
    """
    for series_id in data.current.columns:
        series = pd.to_numeric(data.current[series_id], errors="coerce").sort_index()
        series.name = None
        title = str(data.current_meta.loc[series_id, ra.rba_metacol.desc]).replace(NOTES_SUFFIX, "")
        singular, _ = _currency(title)
        ylabel = singular or str(data.current_meta.loc[series_id, ra.rba_metacol.unit])
        lheader = _lheader(series, data.current.index[-1], first=data.current.index[0])
        _labelled_chart(series, title, ylabel, lheader)

    twi_ids = [series_id for series_id, name in data.names.items() if TWI_NAME in name]
    if len(twi_ids) != 1:
        raise ValueError(f"expected one {TWI_NAME!r} series in the history, found {twi_ids}")
    twi_id = twi_ids[0]
    twi = data.history[twi_id].dropna()
    twi.name = None
    start = (twi.index[-1].to_timestamp() - pd.DateOffset(years=TWI_YEARS)).to_period("D")
    twi = twi[twi.index > start]
    title = data.names[twi_id]
    lheader = _lheader(twi, data.history.index[-1])
    _labelled_chart(
        twi,
        title,
        data.units[twi_id],
        lheader,
        window=TWI_EXTREMES_WINDOW,
        confirm=TWI_CONFIRM_DAYS,
        tag=TWI_TAG,
    )


def long_run_exchange_rates(data: FxData) -> None:
    """Chart each exchange rate daily since December 1983 (or its first quote)."""
    for series_id in data.history.columns:
        series = data.history[series_id]
        if series.isna().all():
            continue
        title = data.names[series_id]
        singular, _ = _currency(title)
        mg.line_plot_finalise(
            series,
            title=title,
            ylabel=singular or data.units[series_id],
            rfooter=SOURCE,
            lfooter=_lfooter(title, series.dropna().index[-1]),
            lheader=_lheader(series, data.history.index[-1]),
            tag="-long-term",
            pre_tag=PRE_TAG,
            dropna=False,
        )


CHARTS = (
    (short_run_exchange_rates, ()),
    (long_run_exchange_rates, ()),
)
