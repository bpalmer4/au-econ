"""Taxation Revenue, Australia (5506.0): taxation revenue by level of government and category.

An Excel-only release (not in the ABS Time Series Directory), fetched from its landing page.
Only the summary workbook is used: Table 1, taxation revenue by level of government and
category. Financial years end 30 June.
"""

# --- dependencies
from dataclasses import dataclass

import mgplot as mg
import pandas as pd
import readabs as ra

from au_econ.sources.abs_workbook import clean, financial_years, find_workbook, header_row, long_units, row_values

# --- module contract
RELEASE = ("5506", "tax")
TOPICS = ("government",)
TITLE = "Taxation Revenue"

# --- constants
CATALOGUE = "5506.0"
LATEST = "https://www.abs.gov.au/statistics/economy/government/taxation-revenue-australia/latest-release"
RFOOTER = "ABS: 5506.0"
FINANCIAL_YEAR = "Financial Year ending 30 June"
SUMMARY_CONTENTS = "level of government and category"  # how the summary workbook (DO002) describes itself
SUMMARY_TABLE = "Table_1"
CW, ALL = "Commonwealth", "All Levels of Govt"
LEVEL_HEADERS = {
    "Commonwealth government": CW,
    "Total state government": "State",
    "Total local government": "Local",
    "All levels of government": ALL,
}
TOTAL = "Total taxation revenue"
TAX_CATEGORIES = (
    "Taxes on income",
    "Employers payroll taxes",
    "Taxes on property",
    "Taxes on provision of goods and services",
    "Taxes on use of goods and performance of activities",
    TOTAL,
)
PERCENT = 100
LFOOTER_START = "Australia. Original series. "
LEVELS_LFOOTER = f'{LFOOTER_START}"All Levels" = CW + State + Local, consolidated. '
LEVELS_LEGEND = {"loc": "best"}
CATEGORY_LEGEND = {"loc": "best", "fontsize": "x-small"}


# --- data
@dataclass(frozen=True)
class TaxData:
    """Taxation revenue by category (columns) and financial year, for each level of government."""

    levels: dict[str, pd.DataFrame]
    units: str


def fetch() -> TaxData:
    """Fetch the latest release and parse the summary table, block by level of government."""
    tables = ra.grab_abs_url(url=LATEST, verbose=False)
    if not tables:
        raise ValueError(f"ABS {CATALOGUE}: nothing at {LATEST}")
    prefix = find_workbook(tables, lambda cell: SUMMARY_CONTENTS in cell.lower())
    raw = clean(tables[f"{prefix}---{SUMMARY_TABLE}"])
    header = header_row(raw)
    years = financial_years(row_values(raw, header))
    units = long_units(str(row_values(raw, header + 1)[0]))
    per_level: dict[str, dict[str, list[float]]] = {level: {} for level in LEVEL_HEADERS.values()}
    headers = {header.lower(): level for header, level in LEVEL_HEADERS.items()}
    current = None
    for _, row in raw.iloc[header + 2 :].iterrows():
        label = row.iloc[0]
        if not isinstance(label, str):
            continue
        stripped = label.strip()
        if stripped.lower() in headers:
            current = headers[stripped.lower()]
            continue
        if current is not None and stripped in TAX_CATEGORIES:
            per_level[current][stripped] = pd.to_numeric(row.iloc[1:], errors="coerce").tolist()
    levels = {level: pd.DataFrame(rows, index=years).astype(float) for level, rows in per_level.items() if rows}
    if CW not in levels or ALL not in levels:
        raise ValueError(f"ABS {CATALOGUE}: the summary table parsed without the Commonwealth or all levels")
    return TaxData(levels=levels, units=units)


# --- charts
def totals(data: TaxData) -> None:
    """Chart total taxation revenue: the Commonwealth against all levels of government."""
    frame, units = ra.recalibrate(
        pd.DataFrame({level: data.levels[level][TOTAL] for level in (CW, ALL)}), data.units
    )
    mg.line_plot_finalise(
        frame,
        title="Total Taxation Revenue: Commonwealth vs All Levels",
        ylabel=units,
        xlabel=FINANCIAL_YEAR,
        annotate=True,
        rounding=1,
        rfooter=RFOOTER,
        lfooter=LEVELS_LFOOTER,
        legend=LEVELS_LEGEND,
    )


def growth(data: TaxData) -> None:
    """Chart annual growth in total taxation revenue: the Commonwealth against all levels of government."""
    frame = pd.DataFrame({level: data.levels[level][TOTAL].pct_change() * PERCENT for level in (CW, ALL)})
    mg.line_plot_finalise(
        frame.dropna(how="all"),
        title="Total Taxation Revenue: Annual Growth",
        ylabel="Per cent change year on year",
        xlabel=FINANCIAL_YEAR,
        y0=True,
        annotate=True,
        rounding=1,
        rfooter=RFOOTER,
        lfooter=LEVELS_LFOOTER,
        legend=LEVELS_LEGEND,
    )


def _by_category(data: TaxData, level: str, title: str, scope: str) -> None:
    """Chart one level of government's taxation revenue by category, leaving out categories it never levies."""
    frame = data.levels[level][[c for c in TAX_CATEGORIES if c != TOTAL]].copy()
    frame = frame.loc[:, (frame != 0).any(axis=0)]  # e.g. the Commonwealth has no property taxes
    frame, units = ra.recalibrate(frame, data.units)
    mg.line_plot_finalise(
        frame,
        title=title,
        ylabel=units,
        xlabel=FINANCIAL_YEAR,
        annotate=True,
        rounding=1,
        rfooter=RFOOTER,
        lfooter=f"{LFOOTER_START}{scope}",
        legend=CATEGORY_LEGEND,
    )


def cw_by_category(data: TaxData) -> None:
    """Chart Commonwealth taxation revenue by category."""
    _by_category(data, CW, "Commonwealth Taxation Revenue by Category", "Commonwealth Government. ")


def all_by_category(data: TaxData) -> None:
    """Chart taxation revenue by category, all levels of government."""
    _by_category(
        data,
        ALL,
        "All Levels of Government: Taxation Revenue by Category",
        "All Levels of Government. ",
    )


# --- table of contents, in run order
CHARTS = (
    (totals, ()),
    (growth, ()),
    (cw_by_category, ()),
    (all_by_category, ()),
)
