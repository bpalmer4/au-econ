"""Personal Income in Australia (6524.0.55.002): mean employee income by Remoteness Area.

Employee income by SA2 (Table 5.4) is mapped to Remoteness Areas through the ASGS
allocation file: each SA2 takes the Remoteness Area most of its SA1s fall in, and the
mean is weighted by earners.
"""

# --- dependencies
from dataclasses import dataclass
from io import BytesIO

import pandas as pd
from mgplot import bar_plot_finalise, line_plot_finalise

from au_econ.sources.abs import landing_page_workbook

# --- module contract
RELEASE = ("6524", "income-remoteness")
TOPICS = ("wages",)
TITLE = "Income by Remoteness"

# --- constants
INCOME_URL = (
    "https://www.abs.gov.au/statistics/labour/earnings-and-working-conditions/"
    "personal-income-australia/latest-release"
)
ASGS_RA_URL = (
    "https://www.abs.gov.au/statistics/standards/"
    "australian-statistical-geography-standard-asgs-edition-3/"
    "jul2021-jun2026/access-and-downloads/allocation-files"
)
RA_WORKBOOK, RA_SHEET = "RA_2021_AUST.xlsx", "SA1_RA_2021_AUST"
INCOME_WORKBOOK_PREFIX, INCOME_SHEET = "Table 5 - Employee income", "Table 5.4"
INCOME_HEADER_ROWS = [5, 6]
SA2_DIGITS = 9
SUM_PREFIX, EARNERS_PREFIX = "Sum ($)_", "Earners (persons)_"
RA_ORDER = [
    "Major Cities of Australia",
    "Inner Regional Australia",
    "Outer Regional Australia",
    "Remote Australia",
    "Very Remote Australia",
]
RA_LABELS = {
    "Major Cities of Australia": "Major Cities",
    "Inner Regional Australia": "Inner Regional",
    "Outer Regional Australia": "Outer Regional",
    "Remote Australia": "Remote",
    "Very Remote Australia": "Very Remote",
}
INDEX_BASE = 100
RFOOTER = "ABS: 6524.0.55.002, ASGS Edition 3"
LFOOTER = "Australia. Original series. Earner-weighted mean across SA2s. SA2 assigned to modal Remoteness Area. "
FINANCIAL_YEAR = "Financial year ending June"


@dataclass(frozen=True)
class IncomeData:
    """Employee income by SA2 (earners and income sums, by year), each SA2's Remoteness Area, and the years."""

    income: pd.DataFrame
    sa2_ra: pd.Series
    years: list[str]


# --- data
def _sa2_to_ra() -> pd.Series:
    """Return the modal Remoteness Area name, indexed by SA2 code."""
    raw = landing_page_workbook(ASGS_RA_URL, lambda name: name == RA_WORKBOOK)
    frame = pd.read_excel(BytesIO(raw), sheet_name=RA_SHEET)
    frame["SA2"] = frame["SA1_CODE_2021"].astype(str).str[:SA2_DIGITS]
    return frame.groupby("SA2")["RA_NAME_2021"].agg(lambda x: x.mode().iloc[0])


def _sa2_income() -> pd.DataFrame:
    """Load Table 5.4, employee income by SA2, one column pair (earners, sum) per year."""
    raw = landing_page_workbook(INCOME_URL, lambda name: name.startswith(INCOME_WORKBOOK_PREFIX))
    frame = pd.read_excel(BytesIO(raw), sheet_name=INCOME_SHEET, header=INCOME_HEADER_ROWS)
    names: list[str] = []
    for column in frame.columns:
        if not isinstance(column, tuple):
            raise TypeError("Expected a two-row header")
        top, bottom = column
        names.append(str(bottom) if "Unnamed" in str(top) else f"{top}_{bottom}")
    frame.columns = pd.Index(names)
    frame = frame.rename(columns={"SA2": "SA2_CODE", "SA2 NAME": "SA2_NAME"})
    # keep only 9-digit SA2 codes (drop the state and national rows)
    frame = frame[frame["SA2_CODE"].astype(str).str.match(rf"^\d{{{SA2_DIGITS}}}$", na=False)].copy()
    frame["SA2_CODE"] = frame["SA2_CODE"].astype(str)
    for year in _years(frame):
        for column in (f"{EARNERS_PREFIX}{year}", f"{SUM_PREFIX}{year}"):
            frame[column] = pd.to_numeric(frame[column], errors="coerce")  # 'np' = not published
    return frame


def _years(income: pd.DataFrame) -> list[str]:
    """Return the financial years in the income table ('2018-19', ...), in column order."""
    return [str(c).removeprefix(SUM_PREFIX) for c in income.columns if str(c).startswith(SUM_PREFIX)]


def fetch() -> IncomeData:
    """Fetch the SA2 income table and the SA2-to-Remoteness-Area mapping."""
    income = _sa2_income()
    data = IncomeData(income=income, sa2_ra=_sa2_to_ra(), years=_years(income))
    if data.income.empty or data.sa2_ra.empty or not data.years:
        raise ValueError("ABS 6524.0.55.002: the income table, its years or the remoteness mapping is empty")
    return data


def _mean_by_ra(data: IncomeData, year: str) -> pd.Series:
    """Earner-weighted mean employee income by Remoteness Area, for one financial year."""
    merged = data.income.merge(data.sa2_ra.rename("RA"), left_on="SA2_CODE", right_index=True, how="left")
    merged = merged[merged["RA"].isin(RA_ORDER)]
    sums = merged.groupby("RA")[f"{SUM_PREFIX}{year}"].sum()
    earners = merged.groupby("RA")[f"{EARNERS_PREFIX}{year}"].sum()
    mean = (sums / earners).reindex(RA_ORDER)
    mean.index = pd.Index([RA_LABELS[r] for r in mean.index])
    return mean.rename("Mean income ($)")


def _by_year(data: IncomeData) -> pd.DataFrame:
    """Return mean income by Remoteness Area (columns), one row per financial year ending June."""
    frame = pd.DataFrame({year: _mean_by_ra(data, year) for year in data.years}).T
    end_years = [int(f"20{year.split('-')[1]}") for year in frame.index]
    frame.index = pd.PeriodIndex([pd.Period(year=y, freq="Y-JUN") for y in end_years], name="year")
    return frame


# --- charts
def latest_year(data: IncomeData) -> None:
    """Chart mean employee income by Remoteness Area in the latest year."""
    bar_plot_finalise(
        _mean_by_ra(data, data.years[-1]).to_frame(),
        title=f"Mean Employee Income by Remoteness Area: {data.years[-1]}",
        ylabel="Mean income ($ per earner per year)",
        annotate=True,
        rounding=0,
        legend=False,
        rfooter=RFOOTER,
        lfooter=LFOOTER,
    )


def by_year(data: IncomeData) -> None:
    """Chart mean employee income by Remoteness Area over time."""
    frame = _by_year(data)
    print(frame.round(0))
    line_plot_finalise(
        frame,
        title="Mean Employee Income by Remoteness Area",
        ylabel="$ per earner per year",
        xlabel=FINANCIAL_YEAR,
        annotate=True,
        rounding=0,
        xlim=(frame.index[0], frame.index[-1]),
        rfooter=RFOOTER,
        lfooter=LFOOTER,
    )


def by_year_indexed(data: IncomeData) -> None:
    """Chart mean employee income by Remoteness Area, indexed to the first year."""
    frame = _by_year(data)
    indexed = frame.div(frame.iloc[0]) * INDEX_BASE
    line_plot_finalise(
        indexed,
        title="Mean Employee Income by Remoteness Area: Indexed",
        ylabel=f"Index ({data.years[0]} = 100)",
        xlabel=FINANCIAL_YEAR,
        annotate=True,
        rounding=1,
        xticks=list(indexed.index),
        xlim=(indexed.index[0], indexed.index[-1]),
        rfooter=RFOOTER,
        lfooter=LFOOTER,
    )


# --- table of contents, in run order
CHARTS = (
    (latest_year, ()),
    (by_year, ()),
    (by_year_indexed, ()),
)
