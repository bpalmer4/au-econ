"""Australian recessions: six contraction indicators, and the periods when enough of them fire together.

The indicators are technical recessions (two or more consecutive quarters of negative growth)
in GDP, GDP per capita and employment, negative annual GDP and employment growth, and a
rapid rise in unemployment (akin to the Sahm rule). A recession is a quarter where at least
three fire, plus a shoulder quarter either side where at least one does.
"""

# --- dependencies
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pandas as pd
import readabs as ra
from mgplot import finalise_plot, line_plot
from readabs import metacol as mc

from au_econ.series.gdp import get_table

if TYPE_CHECKING:
    from matplotlib.axes import Axes

# --- module contract
RELEASE = ("recessions",)
TOPICS = ("economy",)
TITLE = "Recessions"

# --- constants
CAT_MDB, CAT_GDP = "1364.0.15.003", "5206.0"
MDB_TABLE = "1364015003"
AGGREGATES = "5206001_Key_Aggregates"
SA, ORIG = "Seasonally Adjusted", "Original"
MILL, DOLLARS, THOU = "$ Millions", "$", "000"
MDB_WANTED = {  # all seasonally adjusted; GDP also chain volume measures
    "Labour force": {MDB_TABLE: mc.table, "Total labour force ;": mc.did, SA: mc.stype, THOU: mc.unit},
    "Unemployed": {MDB_TABLE: mc.table, "Total unemployed ;": mc.did, SA: mc.stype, THOU: mc.unit},
    "GDP (SA/CVM/MDB)": {
        MDB_TABLE: mc.table,
        "Gross domestic product (Chain volume measures) ;": mc.did,
        SA: mc.stype,
        MILL: mc.unit,
    },
}
GDP_WANTED = {  # Original, to derive the population back to 1959 (GDP per capita SA/CVM starts 1973)
    "GDP per capita (O/CVM/KA)": {
        AGGREGATES: mc.table,
        "GDP per capita: Chain volume measures ;": mc.did,
        ORIG: mc.stype,
        DOLLARS: mc.unit,
    },
    "GDP (O/CVM/KA)": {
        AGGREGATES: mc.table,
        "Gross domestic product: Chain volume measures ;": mc.did,
        ORIG: mc.stype,
        MILL: mc.unit,
    },
}
PERCENT = 100
QUARTERS_PER_YEAR = 4
THRESHOLD = 0.75  # percentage points - akin to the Sahm Rule
EVENTS = (  # (line, the event shaded behind it)
    ("GDP Growth Q/Q", "GDP Technical Recession"),
    ("GDP Growth Y/Y", "Negative Annual GDP Growth"),
    ("Employment Growth Q/Q", "Employment Technical Recession"),
    ("Employment Growth Y/Y", "Negative Annual Employment Growth"),
    ("GDP per Capita Growth", "GDP per Capita Technical Recession"),
    ("Unemployment Rate", "Rapid Unemployment Growth"),
)
INDICATORS = (
    "GDP Technical Recession",
    "Negative Annual GDP Growth",
    "GDP per Capita Technical Recession",
    "Rapid Unemployment Growth",
    "Employment Technical Recession",
    "Negative Annual Employment Growth",
)
RECESSION_THRESHOLD, SHOULDER_THRESHOLD = 3, 1
R_COLOUR, ALPHA = "darkorange", 0.5
LFOOTER = "Australia. Seasonally adjusted. "
COMMON: dict[str, Any] = {"y0": True, "legend": True}
TECHNICAL_NOTE = "Technical recession is 2+ quarters of negative growth. "
GDP_NOTE = "Chain volume measures. "


@dataclass(frozen=True)
class RecessionData:
    """The indicator dataset (levels, growth rates and Boolean events), and each column's catalogues."""

    data: pd.DataFrame
    sources: dict[str, set[str]]


# --- data
def _select(data: dict[str, pd.DataFrame], meta: pd.DataFrame, selector: dict[str, str]) -> pd.Series:
    table, series_id, _units = ra.find_abs_id(meta, selector, exact_match=True, verbose=False)
    return data[table][series_id]


def _two_negative_quarters(series: pd.Series) -> pd.Series:
    """Flag quarters in a run of two or more consecutive negative quarters."""
    return (series < 0) & ((series.shift(-1) < 0) | (series.shift(1) < 0))


def fetch() -> RecessionData:
    """Fetch the Modellers' Database and Key Aggregates series, and derive the indicators."""
    mdb_data, mdb_meta = ra.read_abs_cat(CAT_MDB, single_excel_only=MDB_TABLE, verbose=False)
    gdp_data, gdp_meta = get_table(AGGREGATES)
    data = pd.DataFrame(
        {title: _select(mdb_data, mdb_meta, selector) for title, selector in MDB_WANTED.items()}
        | {title: _select(gdp_data, gdp_meta, selector) for title, selector in GDP_WANTED.items()}
    )
    if data.empty:
        raise ValueError("ABS: no recession indicator data returned")
    sources: dict[str, set[str]] = {}

    data["population"] = data["GDP (O/CVM/KA)"] / data["GDP per capita (O/CVM/KA)"]
    sources["population"] = {CAT_GDP}
    data["Employed"] = data["Labour force"] - data["Unemployed"]
    sources["Employed"] = {CAT_MDB}
    data["Employment Growth Q/Q"] = data["Employed"].pct_change(1) * PERCENT
    sources["Employment Growth Q/Q"] = sources["Employed"]
    data["Employment Growth Y/Y"] = data["Employed"].pct_change(QUARTERS_PER_YEAR) * PERCENT
    sources["Employment Growth Y/Y"] = sources["Employed"]
    data["Employment Technical Recession"] = _two_negative_quarters(data["Employment Growth Q/Q"])
    data["Negative Annual Employment Growth"] = data["Employment Growth Y/Y"] < 0
    data["Unemployment Rate"] = data["Unemployed"] / data["Labour force"] * PERCENT
    sources["Unemployment Rate"] = {CAT_MDB}
    data["GDP Growth Q/Q"] = data["GDP (SA/CVM/MDB)"].pct_change(1) * PERCENT
    sources["GDP Growth Q/Q"] = {CAT_MDB}
    data["GDP Growth Y/Y"] = data["GDP (SA/CVM/MDB)"].pct_change(QUARTERS_PER_YEAR) * PERCENT
    sources["GDP Growth Y/Y"] = {CAT_MDB}
    data["Negative Annual GDP Growth"] = data["GDP Growth Y/Y"] < 0
    data["GDP Technical Recession"] = _two_negative_quarters(data["GDP Growth Q/Q"])
    data["GDP Per Capita"] = data["GDP (SA/CVM/MDB)"] / data["population"]
    data["GDP per Capita Growth"] = data["GDP Per Capita"].pct_change(1) * PERCENT
    sources["GDP per Capita Growth"] = sources["population"] | sources["GDP Growth Q/Q"]
    data["GDP per Capita Technical Recession"] = _two_negative_quarters(data["GDP per Capita Growth"])
    data["Rapid Unemployment Growth"] = (
        data["Unemployment Rate"].rolling(QUARTERS_PER_YEAR).min().shift(1) < data["Unemployment Rate"] - THRESHOLD
    )
    return RecessionData(data=data, sources=sources)


# --- helpers
def _highlight(ax: Axes, series: pd.Series, color: str, alpha: float = 0.5, label: str | None = None) -> None:
    """Shade each run of True in a Boolean series (labelling only the first run, for the legend)."""
    if not isinstance(series.index, pd.PeriodIndex):
        raise TypeError("Expected a PeriodIndex")
    shading, start, previous = False, 0, 0
    for index, item in zip([p.ordinal for p in series.index], series.tolist(), strict=True):
        if item and not shading:
            shading, start = True, index
        if shading and not item:
            ax.axvspan(start, previous, color=color, alpha=alpha, label=label)
            shading = False
            label = None
        previous = index
    if shading:
        ax.axvspan(start, previous, color=color, alpha=alpha, label=label)


def _rfooter(recessions: RecessionData, label: str) -> str:
    return f"ABS: {', '.join(sorted(recessions.sources[label]))}"


def _recession(points: pd.Series) -> pd.Series:
    """Flag quarters with RECESSION_THRESHOLD+ indicators, and a shoulder quarter either side with one or more."""
    shoulder = points >= SHOULDER_THRESHOLD
    return (
        (points >= RECESSION_THRESHOLD)
        | (shoulder & (points.shift(1) >= RECESSION_THRESHOLD))
        | (shoulder & (points.shift(-1) >= RECESSION_THRESHOLD))
    )


# --- charts
def events(recessions: RecessionData) -> None:
    """Chart each growth measure, and the unemployment rate, with its contraction event shaded."""
    data = recessions.data
    for series, event in EVENTS:
        ax = line_plot(data[series], label_series=True)
        _highlight(ax, data[event], color=R_COLOUR, alpha=ALPHA, label=event)
        finalise_plot(
            ax,
            title=f"{series}: {event}",
            ylabel="Per cent",
            xlabel=None,
            rfooter=_rfooter(recessions, series),
            lfooter=LFOOTER
            + (GDP_NOTE if "GDP" in event else "")
            + (TECHNICAL_NOTE if "Recession" in event else ""),
            **COMMON,
        )


def recession_periods(recessions: RecessionData) -> None:
    """Chart recessions by indicator intensity, and against GDP and employment growth."""
    data = recessions.data
    points = data[list(INDICATORS)].sum(axis=1)
    recession = _recession(points)
    print(f"Naive recession probability: {recession.sum() / len(recession) * PERCENT:0.0f}%")
    threshold_note = f"Indicator threshold is {RECESSION_THRESHOLD} of {len(INDICATORS)}. "

    points.name = "Indicator intensity"
    ax = line_plot(points, label_series=True)
    _highlight(ax, recession, color=R_COLOUR, alpha=ALPHA, label="Recessions")
    finalise_plot(
        ax,
        title="Australian Recessions (by indicator intensity)",
        ylabel="Indicator count",
        rfooter=_rfooter(recessions, "GDP per Capita Growth"),
        lfooter=f"{LFOOTER}{threshold_note}",
        **COMMON,
    )

    ax = line_plot(
        data[["Employment Growth Y/Y", "GDP Growth Y/Y"]],
        style=["-", "--"],
        label_series=True,
    )
    _highlight(ax, recession, color=R_COLOUR, alpha=ALPHA, label="Recessions")
    finalise_plot(
        ax,
        title="Australian Recessions",
        ylabel="Per cent",
        rfooter=_rfooter(recessions, "GDP per Capita Growth"),
        lfooter=f"{LFOOTER}{GDP_NOTE}{threshold_note}",
        **COMMON,
    )


# --- table of contents, in run order
CHARTS = (
    (events, ()),
    (recession_periods, ()),
)
