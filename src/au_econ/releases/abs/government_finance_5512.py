"""Government Finance Statistics, Annual (5512.0): revenue, expenses, balances and net debt by level of government.

An Excel-only release (not in the ABS Time Series Directory), fetched from its landing page.
Each jurisdiction and sector has its own workbook, whose identifier changes every release, so
workbooks are found by the sector named on their Contents sheet. Financial years end 30 June.
"""

# --- dependencies
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Any

import mgplot as mg
import pandas as pd
import readabs as ra

from au_econ.series.population import get_erp, get_state_erp
from au_econ.sources.abs_workbook import clean, financial_years, find_workbook, header_row, long_units, row_values

if TYPE_CHECKING:
    from collections.abc import Callable

# --- module contract
RELEASE = ("5512", "gfs")
TOPICS = ("government",)
TITLE = "Government Finance Statistics"

# --- constants
CATALOGUE = "5512.0"
LATEST = "https://www.abs.gov.au/statistics/economy/government/government-finance-statistics-annual/latest-release"
RFOOTER = "ABS: 5512.0"
SOURCE_WITH_ERP = "ABS: 3101.0, 5512.0"  # per-head charts divide by 3101.0 ERP
FINANCIAL_YEAR = "Financial Year ending 30 June"
OPERATING_TABLE, BALANCE_TABLE = "Table_1", "Table_3"
CW, ALL = "CW", "All"
SECTOR_NEEDLES = {
    CW: "Commonwealth Total Public Sector",
    ALL: "All Levels of Government, Total Public Sector",
}
STATE_NEEDLES = {
    "NSW": "New South Wales State Total Public Sector",
    "Vic.": "Victoria State Total Public Sector",
    "Qld": "Queensland State Total Public Sector",
    "SA": "South Australia State Total Public Sector",
    "WA": "Western Australia State Total Public Sector",
    "Tas.": "Tasmania State Total Public Sector",
    "NT": "Northern Territory State Total Public Sector",
    "ACT": "Australian Capital Territory State Total Public Sector",
}
ABBR_TO_FULL = dict(zip(STATE_NEEDLES, mg.state_names, strict=True))
REVENUE, EXPENSES = "Total GFS revenue", "Total GFS expenses"
NET_OPERATING_BALANCE = "GFS Net operating balance"
HEADLINE = (REVENUE, EXPENSES, NET_OPERATING_BALANCE, "GFS NET LENDING(+)/BORROWING(-)")
DEBT_LIAB_ROWS = {"Currency and deposits", "Advances", "Other loans and placements", "Debt securities"}
DEBT_ASSET_ROWS = {"Currency and deposits", "Advances", "Other loans and placements"}
MILLION, PERCENT = 1_000_000, 100
JUNE_QUARTER = 2
CW_COLOR = "black"
CW_WIDTH, STATE_WIDTH = 2, 1.5
LFOOTER_START = "Australia. Original series. "
GFS_NOTE = "GFS = Government Finance Statistics. "
HEADLINE_LFOOTER = (
    f'{LFOOTER_START}Total Public Sector. "All Levels" = CW + State + Local, consolidated. {GFS_NOTE}'
)
NET_DEBT_LFOOTER = (
    f"{LFOOTER_START}Total Public Sector. Net debt = debt liabilities less matching assets. {GFS_NOTE}"
)
STATES_LEGEND = {"loc": "best", "ncol": 2, "fontsize": "x-small"}


# --- data
@dataclass(frozen=True)
class GfsData:
    """Operating statements (CW, All and each state) and net debt (CW and each state), in $m."""

    operating: dict[str, pd.DataFrame]
    net_debt: dict[str, pd.Series]
    units: str


def _find_prefix(tables: dict[str, pd.DataFrame], needle: str) -> str:
    """Return the workbook prefix whose Contents sheet names this sector's Operating Statement."""
    return find_workbook(tables, lambda cell: needle.lower() in cell.lower() and "Operating Statement" in cell)


def _operating_statement(raw: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    """Return the operating statement indexed by financial year (columns are line items), and its units."""
    raw = clean(raw)
    header = header_row(raw)
    years = row_values(raw, header)
    units = str(row_values(raw, header + 1)[0])
    data_rows = {}
    for _, row in raw.iloc[header + 2 :].iterrows():
        label = row.iloc[0]
        if not isinstance(label, str):
            continue
        values = pd.to_numeric(row.iloc[1:], errors="coerce")
        if values.notna().any():
            data_rows[label.strip()] = values.tolist()
    out = pd.DataFrame(data_rows, index=years)
    out.index = pd.PeriodIndex(financial_years(years))
    return out.astype(float), long_units(units)


def _net_debt(raw: pd.DataFrame) -> pd.Series:
    """Return net debt from the balance sheet: interest-bearing liabilities less interest-bearing assets ($m)."""
    raw = clean(raw)
    header = header_row(raw)
    years = financial_years(row_values(raw, header))
    section = None
    liabilities = pd.Series(0.0, index=years)
    assets = pd.Series(0.0, index=years)
    for _, row in raw.iloc[header + 1 :].iterrows():
        label = row.iloc[0]
        if not isinstance(label, str):
            continue
        stripped = label.strip()
        if stripped == "Assets":
            section = "asset"
            continue
        if stripped == "Liabilities":
            section = "liability"
            continue
        if stripped in {"less", "equals"}:
            continue
        values = pd.to_numeric(row.iloc[1:], errors="coerce")
        if not values.notna().any():
            continue
        line = pd.Series(values.tolist(), index=years).astype(float)
        if section == "asset" and stripped in DEBT_ASSET_ROWS:
            assets = assets.add(line, fill_value=0)
        elif section == "liability" and stripped in DEBT_LIAB_ROWS:
            liabilities = liabilities.add(line, fill_value=0)
    return liabilities - assets


def fetch() -> GfsData:
    """Fetch the latest release and parse each jurisdiction's operating statement and balance sheet."""
    tables = ra.grab_abs_url(url=LATEST, verbose=False)
    if not tables:
        raise ValueError(f"ABS {CATALOGUE}: nothing at {LATEST}")
    prefixes = {key: _find_prefix(tables, needle) for key, needle in (SECTOR_NEEDLES | STATE_NEEDLES).items()}
    operating, units = {}, ""
    for key, prefix in prefixes.items():
        operating[key], key_units = _operating_statement(tables[f"{prefix}---{OPERATING_TABLE}"])
        units = units or key_units  # the Commonwealth's, which comes first
    net_debt = {
        key: _net_debt(tables[f"{prefix}---{BALANCE_TABLE}"]) for key, prefix in prefixes.items() if key != ALL
    }
    return GfsData(operating=operating, net_debt=net_debt, units=units)


# --- helpers
def _by_jurisdiction(data: GfsData, item: str) -> pd.DataFrame:
    """One operating-statement line item for the Commonwealth and each state."""
    return pd.DataFrame({key: data.operating[key][item] for key in (CW, *STATE_NEEDLES)})


def _annual_pop(get: Callable[[], tuple[pd.Series, str]]) -> pd.Series:
    """Return population at end-June each year, indexed by year ending June."""
    pop, _units = get()
    if not isinstance(pop.index, pd.PeriodIndex):
        raise TypeError("Expected a quarterly PeriodIndex")
    june = pop[pop.index.quarter == JUNE_QUARTER]
    if not isinstance(june.index, pd.PeriodIndex):
        raise TypeError("Expected a quarterly PeriodIndex")
    june.index = june.index.asfreq("Y-JUN")
    return june


def _populations() -> pd.DataFrame:
    """June-quarter ERP for the Commonwealth (all Australia) and each state."""
    return pd.DataFrame(
        {CW: _annual_pop(get_erp)}
        | {abbr: _annual_pop(partial(get_state_erp, full)) for abbr, full in ABBR_TO_FULL.items()}
    )


def _states_plot_kwargs() -> dict[str, Any]:
    """Return the shared style of the Commonwealth-and-states charts: the Commonwealth in black."""
    return {
        "color": [CW_COLOR] + [mg.get_color(ABBR_TO_FULL[a]) for a in STATE_NEEDLES],
        "style": "-",
        "width": [CW_WIDTH] + [STATE_WIDTH] * len(STATE_NEEDLES),
        "annotate": True,
        "fontsize": "x-small",
    }


# --- charts
def headlines(data: GfsData) -> None:
    """Chart each headline GFS series: the Commonwealth against all levels of government."""
    for item in HEADLINE:
        for key in (CW, ALL):
            if item not in data.operating[key].columns:
                raise KeyError(f"Missing in {key}: {item}")
        frame = pd.DataFrame(
            {"Commonwealth": data.operating[CW][item], "All Levels of Govt": data.operating[ALL][item]}
        ).dropna(how="all")
        frame, units = ra.recalibrate(frame, data.units)
        mg.line_plot_finalise(
            frame,
            title=f"GFS: {item}",
            ylabel=units,
            xlabel=FINANCIAL_YEAR,
            y0=True,
            annotate=True,
            rounding=1,
            rfooter=RFOOTER,
            lfooter=HEADLINE_LFOOTER,
            legend={"loc": "best"},
        )


def cw_growth(data: GfsData) -> None:
    """Chart year-on-year growth in Commonwealth revenue and expenses."""
    for item in (REVENUE, EXPENSES):
        growth = (data.operating[CW][item].pct_change() * PERCENT).dropna().to_frame(name="YoY growth")
        mg.bar_plot_finalise(
            growth,
            title=f"Commonwealth GFS: {item}, Year-on-Year Growth",
            ylabel="Per cent change",
            xlabel=FINANCIAL_YEAR,
            annotate=True,
            rounding=1,
            y0=True,
            rfooter=RFOOTER,
            lfooter=f"{LFOOTER_START}Commonwealth Total Public Sector. {GFS_NOTE}",
            legend=False,
        )


def nob_per_capita(data: GfsData) -> None:
    """Chart the net operating balance per head, Commonwealth and states."""
    nob = _by_jurisdiction(data, NET_OPERATING_BALANCE)
    per_capita, units = ra.recalibrate((nob * MILLION) / _populations().reindex(nob.index), "$")
    mg.line_plot_finalise(
        per_capita,
        title="GFS Net Operating Balance per Capita: Commonwealth and States",
        ylabel=f"{units} per person",
        xlabel=FINANCIAL_YEAR,
        y0=True,
        rounding=0,
        rfooter=SOURCE_WITH_ERP,
        lfooter=f"{LFOOTER_START}Total Public Sector. Per-capita using ERP at 30 June. {GFS_NOTE}",
        legend=STATES_LEGEND,
        **_states_plot_kwargs(),
    )


def net_debt_per_capita(data: GfsData) -> None:
    """Chart net debt per head, Commonwealth and states."""
    net_debt = pd.DataFrame(data.net_debt)
    per_capita, units = ra.recalibrate((net_debt * MILLION) / _populations().reindex(net_debt.index), "$")
    mg.line_plot_finalise(
        per_capita,
        title="GFS Net Debt per Capita: Commonwealth and States",
        ylabel=f"{units} per person",
        xlabel=FINANCIAL_YEAR,
        y0=True,
        rounding=0,
        rfooter=SOURCE_WITH_ERP,
        lfooter=NET_DEBT_LFOOTER,
        legend=STATES_LEGEND,
        **_states_plot_kwargs(),
    )


def net_debt_total(data: GfsData) -> None:
    """Chart net debt on a log scale, Commonwealth and states."""
    frame, units = ra.recalibrate(pd.DataFrame(data.net_debt), "Dollars (Millions)")
    ax = mg.line_plot(frame, rounding=3, **_states_plot_kwargs())
    ax.set_yscale("log")
    mg.finalise_plot(
        ax,
        title="GFS Net Debt: Commonwealth and States",
        ylabel=f"{units} (log scale)",
        xlabel=FINANCIAL_YEAR,
        rfooter=RFOOTER,
        lfooter=NET_DEBT_LFOOTER,
        legend=STATES_LEGEND,
    )


def debt_to_revenue(data: GfsData) -> None:
    """Chart net debt as a percentage of annual revenue, Commonwealth and states."""
    revenue = _by_jurisdiction(data, REVENUE)
    mg.line_plot_finalise(
        pd.DataFrame(data.net_debt).reindex(revenue.index) / revenue * PERCENT,
        title="GFS Net Debt to Annual Revenue: Commonwealth and States",
        ylabel="Net Debt / Annual Revenue (%)",
        xlabel=FINANCIAL_YEAR,
        y0=True,
        rounding=0,
        rfooter=RFOOTER,
        lfooter=f"{LFOOTER_START}Total Public Sector. "
        f"State revenue includes grants from the Commonwealth. {GFS_NOTE}",
        legend=STATES_LEGEND,
        **_states_plot_kwargs(),
    )


# --- table of contents, in run order
CHARTS = (
    (headlines, ()),
    (cw_growth, ()),
    (nob_per_capita, ()),
    (net_debt_per_capita, ()),
    (net_debt_total, ()),
    (debt_to_revenue, ()),
)
