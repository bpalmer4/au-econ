"""Counts of Australian Businesses, including Entries and Exits (8165.0): business entry and exit rates.

Quarterly entries, exits and the stock of actively trading businesses (time series
spreadsheet TS13), turned into rates against the opening stock.
"""

# --- dependencies
import mgplot as mg
import pandas as pd
import readabs as ra

# --- module contract
RELEASE = ("8165", "business-counts")
TOPICS = ("business",)
TITLE = "Business Entries and Exits"

# --- constants
# The quarterly TS13 series is published only on this release's page, and kept current there
# (the latest-release page carries just the annual data cube), so the page is pinned.
TS13_PAGE = (
    "https://www.abs.gov.au/statistics/economy/business-indicators/"
    "counts-australian-businesses-including-entries-and-exits/jul2020-jun2024"
)
WORKBOOK, SHEET = "8165TS13", "8165TS13---Data1"
FIRST_DATA_ROW = 9
COLUMNS = ("exits_orig", "entries_orig", "total_orig", "exits_sa", "entries_sa", "total_sa")
SOURCE = "ABS: 8165.0"
LFOOTER = "Australia. Seasonally adjusted. Actively trading businesses on the ATO ABN/GST register. "
PERCENT = 100
THOUSAND = 1_000.0
QUARTERS_PER_YEAR = 4
LEGEND = {"loc": "best", "fontsize": "small"}


# --- data
def fetch() -> pd.DataFrame:
    """Fetch TS13 as a quarterly frame of entries, exits and the business count, original and SA."""
    raw = ra.grab_abs_url(url=TS13_PAGE, single_excel_only=WORKBOOK, get_zip=False)
    if SHEET not in raw:
        raise ValueError(f"ABS 8165.0: no {SHEET} at {TS13_PAGE}")
    body = raw[SHEET].iloc[FIRST_DATA_ROW:].copy()
    body.index = pd.PeriodIndex(pd.to_datetime(body.iloc[:, 0]), freq="Q-DEC")
    body = body.iloc[:, 1:].apply(pd.to_numeric, errors="coerce")
    body.columns = list(COLUMNS)
    if body.dropna(how="all").empty:
        raise ValueError("ABS 8165.0: TS13 parsed empty")
    return body


def _rates(counts: pd.DataFrame, suffix: str = "sa") -> pd.DataFrame:
    """Quarterly entry and exit rates, as a percentage of the opening stock."""
    opening = counts[f"total_{suffix}"].shift(1)
    return pd.DataFrame(
        {
            "Entry rate": counts[f"entries_{suffix}"] / opening * PERCENT,
            "Exit rate": counts[f"exits_{suffix}"] / opening * PERCENT,
        }
    ).dropna()


# --- charts
def annualised_rates(counts: pd.DataFrame) -> None:
    """Chart entry and exit rates over the trailing four quarters."""
    annual = _rates(counts).rolling(QUARTERS_PER_YEAR).sum().dropna()
    print("latest annualised rates:")
    print(annual.tail(QUARTERS_PER_YEAR).round(2))
    mg.line_plot_finalise(
        annual,
        title="Australia: business entry and exit rates (annualised)",
        ylabel="Per cent of opening stock\n(4-quarter trailing sum)",
        rfooter=SOURCE,
        lfooter=LFOOTER,
        annotate=True,
        rounding=1,
        legend=LEGEND,
    )


def quarterly_rates(counts: pd.DataFrame) -> None:
    """Chart quarterly entry and exit rates."""
    mg.line_plot_finalise(
        _rates(counts),
        title="Australia: business entry and exit rates, quarterly",
        ylabel="Per cent of opening stock",
        rfooter=SOURCE,
        lfooter=LFOOTER,
        annotate=True,
        rounding=2,
        legend=LEGEND,
    )


def net_entry(counts: pd.DataFrame) -> None:
    """Chart the net entry rate: entries less exits, as a percentage of the opening stock."""
    rates = _rates(counts)
    mg.line_plot_finalise(
        (rates["Entry rate"] - rates["Exit rate"]).rename(f"Net entry rate (entries {chr(0x2212)} exits)"),
        title="Australia: net business entry rate (entries minus exits)",
        ylabel="Per cent of opening stock, quarterly",
        rfooter=SOURCE,
        lfooter=LFOOTER,
        annotate=True,
        rounding=2,
        y0=True,
    )


def entry_exit_counts(counts: pd.DataFrame) -> None:
    """Chart quarterly business entries and exits, in thousands."""
    mg.line_plot_finalise(
        counts[["entries_sa", "exits_sa"]].rename(columns={"entries_sa": "Entries", "exits_sa": "Exits"})
        / THOUSAND,
        title="Australia: quarterly business entries and exits, counts",
        ylabel="Thousands of businesses per quarter",
        rfooter=SOURCE,
        lfooter=LFOOTER,
        annotate=True,
        rounding=0,
        legend=LEGEND,
    )


# --- table of contents, in run order
CHARTS = (
    (annualised_rates, ()),
    (quarterly_rates, ()),
    (net_entry, ()),
    (entry_exit_counts, ()),
)
