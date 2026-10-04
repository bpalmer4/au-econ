"""Labour Force Status of Families (6224.0.55.001): dual-income couple families, family types, household types.

Annual, for June. A data-cube publication (it is not in the ABS time-series directory), so
the three workbooks are read from the latest-release page and parsed by column position:
several columns share the header "'000".
"""

# --- dependencies
from dataclasses import dataclass

import pandas as pd
import readabs as ra
from mgplot import line_plot_finalise

from au_econ.charting.footers import SERIES_TYPE_NOTES

# --- module contract
RELEASE = ("6224", "lfs-families")  # not "families": that is the topic
TOPICS = ("jobs", "families")
TITLE = "Labour Force Status of Families"

# --- constants
CATALOGUE = "6224.0.55.001"
LATEST = "https://www.abs.gov.au/statistics/labour/employment-and-unemployment/labour-force-status-families/latest-release"
# cube: its data sheet
LABOUR_FORCE, FAMILY_TYPES, HOUSEHOLDS = "62240_Table03", "62240_Table01", "62240_TableH1"
SHEETS = {LABOUR_FORCE: "Data 3.1", FAMILY_TYPES: "Data 1.1", HOUSEHOLDS: "Data H.1"}
HEADER_MARKER = "Month"  # first cell of each data sheet's header row
AUSTRALIA = "Australia"
COUPLE_SUMMARY = "Couple families - Summary"
ORIGINAL_NOTE = SERIES_TYPE_NOTES["Original"]
LFOOTER = f"Australia. {ORIGINAL_NOTE} Couple families, with and without children. "
FULL_COMPOSITION = (99, 101)  # per cent: years where every family type is reported (1994 on)


# --- data
@dataclass(frozen=True)
class FamilyData:
    """The three 6224 data cubes' data sheets (raw, columns by position), and the source label."""

    sheets: dict[str, pd.DataFrame]
    source: str


def _data_sheet(table: str) -> pd.DataFrame:
    """Fetch one cube and return its data sheet below the header row, months parsed, columns by position."""
    sheets = ra.grab_abs_url(url=LATEST, single_excel_only=table, verbose=False)
    key = f"{table}---{SHEETS[table]}"
    if key not in sheets:
        raise ValueError(f"ABS {CATALOGUE} {table}: no sheet {SHEETS[table]!r}")
    raw = sheets[key]
    header = raw.index[raw.iloc[:, 0].astype(str) == HEADER_MARKER]
    if len(header) == 0:
        raise ValueError(f"ABS {CATALOGUE} {table}: no header row starting {HEADER_MARKER!r}")
    body = raw.loc[header[0] + 1 :].reset_index(drop=True)
    body.columns = pd.RangeIndex(body.shape[1])
    body[0] = pd.to_datetime(body[0], errors="coerce")
    body = body.dropna(subset=[0])
    if body.empty:
        raise ValueError(f"ABS {CATALOGUE} {table}: no data rows")
    return body


def fetch() -> FamilyData:
    """Fetch the three cubes."""
    return FamilyData(sheets={table: _data_sheet(table) for table in SHEETS}, source=f"ABS: {CATALOGUE}")


# --- helpers
def _strip(column: pd.Series) -> pd.Series:
    """Labels carry leading spaces for nesting; strip them before filtering."""
    return column.astype(str).str.strip()


def _annual(frame: pd.DataFrame, value: int, *, keys: dict[int, str]) -> pd.Series:
    """Select rows matching keys (column position: label), take one value column, average to years.

    2019-2022 carry extra quarters, so each year is the mean of its observations.
    """
    rows = frame
    for position, label in keys.items():
        rows = rows[_strip(rows[position]) == label]
    series = pd.to_numeric(rows.set_index(0)[value], errors="coerce")
    months = series.index
    if not isinstance(months, pd.DatetimeIndex):
        raise TypeError(f"Expected a DatetimeIndex, got {type(months).__name__}")
    series = series.groupby(months.year).mean()
    series.index = pd.PeriodIndex(series.index, freq="Y")
    return series


def _couple_metrics(data: FamilyData) -> pd.DataFrame:
    """Dual-income indicators for couple families, from Table 3."""
    frame = data.sheets[LABOUR_FORCE]
    keys = {1: AUSTRALIA, 2: COUPLE_SUMMARY}

    def status(label: str) -> pd.Series:
        return _annual(frame, 4, keys={**keys, 3: label})

    total = status("Couple families")
    both = status("Both partners employed")
    at_least_one = status("At least one partner employed")
    metrics = pd.DataFrame(index=total.index)
    metrics["Both employed (%)"] = both / total * 100
    metrics["Earners per couple family"] = (both + at_least_one) / total
    metrics["One only (%)"] = (at_least_one - both) / total * 100
    metrics["Neither (%)"] = (total - at_least_one) / total * 100
    return metrics


# --- charts
def both_employed(data: FamilyData) -> None:
    """Share of couple families with both partners employed."""
    line_plot_finalise(
        _couple_metrics(data)["Both employed (%)"],
        title="Dual income: couple families with both partners employed",
        ylabel="Per cent of couple families",
        rfooter=data.source,
        lfooter=LFOOTER,
        annotate=True,
        rounding=1,
    )


def earners(data: FamilyData) -> None:
    """Employed partners per couple family: the individual to household earner multiple."""
    line_plot_finalise(
        _couple_metrics(data)["Earners per couple family"],
        title="Earners per couple family: the individual to household multiple",
        ylabel="Average employed partners per couple family",
        rfooter=data.source,
        lfooter=LFOOTER,
        annotate=True,
        rounding=2,
    )


def employment_composition(data: FamilyData) -> None:
    """How couple families split across both, one only and neither partner employed."""
    line_plot_finalise(
        _couple_metrics(data)[["Both employed (%)", "One only (%)", "Neither (%)"]],
        title="Couple families by employment composition",
        ylabel="Per cent of couple families",
        rfooter=data.source,
        lfooter=LFOOTER,
        style=["-", "--", ":"],
        annotate=True,
        rounding=1,
        legend={"loc": "best", "fontsize": "small"},
    )


def family_types(data: FamilyData) -> None:
    """Share of all families by type, from 1994 when every type is reported (Table 1)."""
    frame = data.sheets[FAMILY_TYPES]

    def family(label: str, value: int = 3) -> pd.Series:  # 3: total families; 5: with dependants 0-24
        return _annual(frame, value, keys={1: AUSTRALIA, 2: label})

    couple_dependants = family("Couple families", 5)
    composition = (
        pd.DataFrame(
            {
                "One parent (single)": family("One parent families"),
                "Couple, dependent children": couple_dependants,
                "Couple, no dependent children": family("Couple families") - couple_dependants,
                "Other families": family("Other families"),
            }
        ).div(family("Total families"), axis=0)
        * 100
    )
    composition = composition[composition.sum(axis=1).round(0).between(*FULL_COMPOSITION)]
    line_plot_finalise(
        composition,
        title="Australian families by type",
        ylabel="Per cent of all families",
        rfooter=data.source,
        lfooter=f"Australia. {ORIGINAL_NOTE} Dependent children aged 0-24. ",
        rheader="Excludes group households (share houses), lone-person households, "
        "and other non-family arrangements.",
        style=["-", "-", "--", ":"],
        annotate=True,
        rounding=1,
        legend={"loc": "best", "fontsize": "small"},
    )


def household_types(data: FamilyData) -> None:
    """Share of all households by top-level type, from 2005 (Table H1, experimental)."""
    frame = data.sheets[HOUSEHOLDS]

    def household(label: str) -> pd.Series:
        return _annual(frame, 4, keys={1: AUSTRALIA, 2: "All households", 3: label})

    composition = (
        pd.DataFrame(
            {
                "One-family households": household("One family households"),
                "Lone-person households": household("Lone person households"),
                "Group (share) households": household("Group households"),
                "Multiple-family households": household("Multiple family households"),
            }
        ).div(household("Total households"), axis=0)
        * 100
    )
    line_plot_finalise(
        composition,
        title="Australian households by type",
        ylabel="Per cent of all households",
        rfooter=data.source,
        lfooter=f"Australia. {ORIGINAL_NOTE} Experimental household estimates. ",
        style=["-", "-", "--", ":"],
        annotate=True,
        rounding=1,
        legend={"loc": "best", "fontsize": "small"},
    )


# --- table of contents, in run order
CHARTS = (
    (both_employed, ()),
    (earners, ()),
    (employment_composition, ()),
    (family_types, ()),
    (household_types, ()),
)
