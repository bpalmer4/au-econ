"""Employee Earnings (6337.0): median weekly earnings by highest non-school qualification.

Annual, for August, from data cube Table 6. The cube is a pivot table whose qualification
headers span several banner rows, so its columns are named here.
"""

# --- dependencies
import pandas as pd
import readabs as ra
from mgplot import bar_plot_finalise, line_plot_finalise

from au_econ.charting.footers import SERIES_TYPE_NOTES

# --- module contract
RELEASE = ("6337", "earnings-education")
TOPICS = ("wages",)
TITLE = "Earnings by Education"

# --- constants
CATALOGUE = "6337.0"
LATEST = (
    "https://www.abs.gov.au/statistics/labour/earnings-and-working-conditions/employee-earnings/latest-release"
)
CUBE, SHEET = "63370_Table06", "Data 6"
FIRST_DATA_ROW = 8  # below the banner and the three header rows
DIM_COLS = ["Survey month", "Parameter", "State", "Leave", "Sex", "Classification", "Category"]
QUAL_COLS = [
    "Postgraduate Degree",
    "Graduate Diploma or Certificate",
    "Bachelor Degree",
    "Bachelor Degree or Higher Total",
    "Advanced Diploma or Diploma",
    "Certificate III or IV",
    "Other non-school qualification",
    "With non-school qualification Total",
    "Without non-school qualification",
    "Total",
]
# qualification column: chart label
CHARTED = {
    "Postgraduate Degree": "Postgraduate",
    "Bachelor Degree": "Bachelor",
    "Advanced Diploma or Diploma": "Diploma",
    "Certificate III or IV": "Certificate III/IV",
    "Without non-school qualification": "No post-school qual.",
}
NATIONAL = {  # the one row per survey month for all employees in Australia
    "State": "Australia",
    "Sex": "Persons",
    "Parameter": "Median weekly earnings",
    "Classification": "Total",
    "Leave": "Total employees",
}
BASE_YEAR = 2014  # index base: the first survey in the cube
SOURCE = f"ABS: {CATALOGUE}"
LFOOTER = f"Australia. {SERIES_TYPE_NOTES['Original']} All employees. Median weekly earnings in main job. "


# --- data
def fetch() -> pd.DataFrame:
    """Median weekly earnings by qualification, all employees, one row per August (annual PeriodIndex)."""
    sheets = ra.grab_abs_url(url=LATEST, single_excel_only=CUBE, verbose=False)
    key = f"{CUBE}---{SHEET}"
    if key not in sheets:
        raise ValueError(f"ABS {CATALOGUE} {CUBE}: no sheet {SHEET!r}")
    frame = sheets[key].iloc[FIRST_DATA_ROW:].copy()
    frame.columns = pd.Index(DIM_COLS + [c for q in QUAL_COLS for c in (q, f"{q} RSE")])
    for column, value in NATIONAL.items():
        frame = frame[frame[column] == value]
    years = frame["Survey month"].astype(str).str.removeprefix("Aug-")
    medians = frame[QUAL_COLS].astype(float)
    medians.index = pd.PeriodIndex("20" + years, freq="Y")
    if medians.empty or not medians.index.is_unique:
        raise ValueError(f"ABS {CATALOGUE} {CUBE}: expected one national row per survey month")
    return medians.sort_index()


# --- helpers
def _charted(medians: pd.DataFrame) -> pd.DataFrame:
    return medians[list(CHARTED)].rename(columns=CHARTED)


# --- charts
def by_qualification(medians: pd.DataFrame) -> None:
    """Median weekly earnings by highest qualification, latest August."""
    latest = medians.index[-1]
    bar_plot_finalise(
        _charted(medians).iloc[-1].rename("Median weekly earnings ($)").to_frame(),
        title=f"Median Weekly Earnings by Highest Qualification: August {latest}",
        ylabel="$ per week",
        annotate=True,
        rounding=0,
        legend=False,
        rfooter=SOURCE,
        lfooter=LFOOTER,
    )


def indexed_growth(medians: pd.DataFrame) -> None:
    """Median weekly earnings by qualification, indexed to August 2014 = 100."""
    charted = _charted(medians)
    index = charted.index
    if not isinstance(index, pd.PeriodIndex):
        raise TypeError(f"Expected a PeriodIndex, got {type(index).__name__}")
    base = charted.loc[index.year == BASE_YEAR]
    if len(base) != 1:
        raise ValueError(f"No single {BASE_YEAR} survey to index to")
    line_plot_finalise(
        charted.div(base.iloc[0]) * 100,
        title=f"Median Weekly Earnings by Qualification: Indexed to August {BASE_YEAR}",
        ylabel=f"Index (August {BASE_YEAR} = 100)",
        annotate=True,
        rounding=0,
        rfooter=SOURCE,
        lfooter=LFOOTER,
    )


def nominal(medians: pd.DataFrame) -> None:
    """Median weekly earnings by qualification, dollars per week."""
    line_plot_finalise(
        _charted(medians),
        title="Median Weekly Earnings by Qualification",
        ylabel="$ per week",
        annotate=True,
        rounding=0,
        rfooter=SOURCE,
        lfooter=LFOOTER,
    )


# --- table of contents, in run order
CHARTS = (
    (by_qualification, ()),
    (indexed_growth, ()),
    (nominal, ()),
)
