"""ABS data: catalogues through readabs, and the CPI expenditure hierarchy through sdmxabs.

sdmxabs is used for the CPI hierarchy only, and only here. Data cubes (workbooks that are
not time-series tables, so readabs does not read them) are found on their release pages
and downloaded through http_cache.
"""

import re
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING, Unpack
from urllib.parse import unquote, urljoin

import pandas as pd
import readabs as ra
import requests
import sdmxabs as sa
from readabs.get_abs_links import get_abs_links

from au_econ.sources.http_cache import get_file

if TYPE_CHECKING:
    from collections.abc import Callable

    from pandas import DataFrame
    from readabs import ReadArgs

RECENT = "2020-12-01"  # default start for recent-period charts

ABS_SITE = "https://www.abs.gov.au"
HEADERS = {"User-Agent": "Mozilla/5.0"}
TIMEOUT = 30  # seconds

# CPI expenditure hierarchy: the SDMX INDEX codelist of the CPI data structure
CPI_STRUCTURE, CPI_DIMENSION = "CPI", "INDEX"
CPI_LEVELS = {0: "aggregate", 1: "group", 2: "sub-group", 3: "class"}
CPI_ROOT = "All groups CPI"

# pivot-table data cubes (e.g. 6202.0 LMS1-5): long-form workbooks, not time-series tables
PIVOT_DATA_SHEET = "Data 1"  # suffix of the data sheet's name
PIVOT_PERIOD = "month"  # the header row's first cell names the period: "Month", "Mid-quarter month"
PIVOT_MEASURE = "('000)"  # measure columns end with their unit


@dataclass(frozen=True)
class AbsRelease:
    """One ABS catalogue: its tables, metadata, source label and a recent start date."""

    data: dict[str, DataFrame]
    meta: DataFrame
    source: str
    recent: str


def fetch_release(cat: str, **kwargs: Unpack[ReadArgs]) -> AbsRelease:
    """Fetch an ABS catalogue (e.g. "6302.0"); raise if nothing comes back.

    Keyword arguments go to readabs.read_abs_cat, e.g. get_zip=False, get_excel=True
    for a catalogue the ABS publishes without a complete zip file.
    """
    data, meta = ra.read_abs_cat(cat, **kwargs)
    if not data or meta.empty:
        raise ValueError(f"ABS {cat}: no data returned")
    return AbsRelease(data=data, meta=meta, source=f"ABS: {cat}", recent=RECENT)


def latest_data_cube_url(release_page: str, cube: str) -> str:
    """Return the URL of a data cube workbook (e.g. "34070DO004") linked from an ABS latest-release page."""
    response = requests.get(release_page, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    links = sorted(set(re.findall(rf'href="([^"]*/{cube}_[^"/]*\.xlsx)"', response.text)))
    if len(links) != 1:
        raise ValueError(f"ABS {cube}: expected one workbook link at {release_page}, found {links}")
    return urljoin(ABS_SITE, links[0])


def get_data_cube(url: str) -> bytes:
    """Return an ABS data cube workbook (not a time-series table, so not readabs), cached on disk."""
    return get_file(url, prefix="abs")


def landing_page_workbook(page: str, matches: Callable[[str], bool]) -> bytes:
    """Return the first .xlsx linked from an ABS page whose file name (URL-decoded) matches, cached on disk.

    Finding the file from the page keeps working as the ABS moves files into new dated folders.
    """
    links = get_abs_links(page).get(".xlsx", [])
    url = next((link for link in links if matches(unquote(link.rsplit("/", 1)[-1]))), None)
    if url is None:
        raise ValueError(f"ABS: no matching workbook at {page}")
    return get_data_cube(url)


@cache
def _pivot_cube(cat: str, cube: str) -> pd.DataFrame:
    """Read a pivot-table data cube's data sheet into long form (cached; not for mutation)."""
    sheets = ra.grab_abs_url(cat=cat, single_excel_only=cube, verbose=False)
    sheet = next((frame for name, frame in sheets.items() if name.endswith(PIVOT_DATA_SHEET)), None)
    if sheet is None:
        raise ValueError(f"ABS {cat} {cube}: no '{PIVOT_DATA_SHEET}' sheet")
    header_rows = [
        row for row, cell in enumerate(sheet.iloc[:, 0]) if isinstance(cell, str) and PIVOT_PERIOD in cell.lower()
    ]
    if not header_rows:
        raise ValueError(f"ABS {cat} {cube}: no header row naming the period")
    header = header_rows[0]
    frame = sheet.iloc[header + 1 :].copy()
    frame.columns = pd.Index(sheet.iloc[header])
    frame = frame.dropna(axis="columns", how="all")
    period = frame.columns[0]
    dates = pd.to_datetime(frame[period], errors="coerce")
    frame = frame[dates.notna()]  # drops blank and footnote rows below the data
    frame[period] = pd.PeriodIndex(dates[dates.notna()], freq="M")
    for column in frame.columns:
        if isinstance(column, str) and column.endswith(PIVOT_MEASURE):
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if frame.empty:
        raise ValueError(f"ABS {cat} {cube}: no data rows")
    return frame.reset_index(drop=True)


def get_pivot_cube(cat: str, cube: str) -> pd.DataFrame:
    """Return an ABS pivot-table data cube (e.g. 6202.0 "LMS2") as a long table, one row per cell.

    Pivot cubes are not time-series spreadsheets, so read_abs_cat cannot read them. The
    columns are the cube's own: the period first (monthly Periods), then its dimensions
    (e.g. "Sex", "Age"), then its measures, numeric (e.g. "Employed full-time ('000)").
    A copy, so the caller may change it.
    """
    return _pivot_cube(cat, cube).copy()


@dataclass(frozen=True)
class CpiItem:
    """One item in the CPI expenditure hierarchy."""

    name: str
    level: str  # "aggregate", "group", "sub-group" or "class"
    parent: str | None  # the parent's code


@cache
def _cpi_hierarchy() -> dict[str, CpiItem]:
    """Return the CPI expenditure hierarchy keyed by SDMX code (cached for the run).

    Keyed by code, not name: the ABS reuses a name for a sub-group and its only class
    (e.g. "Tobacco", "Rents").
    """
    codelist = sa.code_list_for(CPI_STRUCTURE, CPI_DIMENSION)
    if not codelist:
        raise ValueError("CPI hierarchy: empty SDMX codelist")

    def depth(code: str) -> int:
        level, current = 0, code
        while "parent" in codelist.get(current, {}):
            level += 1
            current = codelist[current]["parent"]
        return level

    hierarchy: dict[str, CpiItem] = {}
    for code, info in codelist.items():
        level = depth(code)
        parent = info.get("parent")
        hierarchy[str(code)] = CpiItem(
            name=info["name"],
            level=CPI_LEVELS.get(level, f"level-{level}"),
            parent=str(parent) if parent else None,
        )
    return hierarchy


def cpi_names(level: str, root: str = CPI_ROOT) -> list[str]:
    """Return the names at one level of the CPI hierarchy (e.g. "class") that sit under root."""
    hierarchy = _cpi_hierarchy()

    def under_root(code: str) -> bool:
        current = hierarchy[code].parent
        while current is not None and current in hierarchy:
            if hierarchy[current].name == root:
                return True
            current = hierarchy[current].parent
        return False

    return [item.name for code, item in hierarchy.items() if item.level == level and under_root(code)]
