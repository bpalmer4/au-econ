"""Lending Indicators (5601.0): new loan commitments for housing and business.

Headline household housing and business finance, the number of new housing loans, lending
for new dwellings (by borrower and purpose, and as a share), existing against new dwellings,
average loan sizes, and the monthly repayment on an average new loan.
"""

# --- dependencies
import pandas as pd
import readabs as ra
from mgplot import line_plot_finalise, multi_start, seastrend_plot_finalise
from readabs import metacol as mc

from au_econ.charting.footers import SERIES_TYPE_NOTES
from au_econ.charting.windows import quarterly_plot_times
from au_econ.sources import rba
from au_econ.sources.abs import AbsRelease, fetch_release

# --- module contract
RELEASE = ("5601", "lending")
TOPICS = ("building", "business")
TITLE = "Lending Indicators"

# --- constants
CATALOGUE = "5601.0"
SA, TREND = "Seasonally Adjusted", "Trend"
TITLE_CHECKS = (
    "Total housing excluding refinancing",
    "Total purpose excluding refinancing",
    "New loan commitments",
    "Fixed term loans",
    "Value",
)
HEADLINE_DIDS = (
    "Households ;  Housing Finance ;  Total dwellings excluding refinancing ;  New loan commitments ;  Value ;",
    (
        "Businesses ;  Business Finance ;  Fixed term loans ;  Purchase of property ;  "
        "New loan commitments ;  Value ;"
    ),
    "Businesses ;  Business Finance ;  Fixed term loans ;  Construction ;  New loan commitments ;  Value ;",
)
HOUSING_DID = "Households ;  Housing Finance ;  Total dwellings excluding refinancing ;  New loan commitments ;"
NEW_DWELLING_PURPOSES = {
    "Construction of dwellings": "construction",
    "Purchase of newly erected dwellings": "new dwelling purchase",
}
NATIONAL_TABLES = {"Owner occupier": "560103", "Investor": "560113"}
TOTAL_TABLE = "560101"
MILLIONS = "$ Millions"
MILLION = 1_000_000
PERCENT = 100
LEGEND_UPPER_LEFT = {"loc": "upper left", "fontsize": "small"}
LEGEND_BEST = {"loc": "best", "fontsize": "small"}
TERM_YEARS = 30
MONTHS_PER_YEAR = 12
RATE_TABLE = "F5"
DISCOUNT_RATE_TITLE = "Lending rates; Housing loans; Banks; Variable; Discounted; Owner-occupier"


# --- data
def fetch() -> AbsRelease:
    """Fetch the release once; every chart function receives it."""
    return fetch_release(CATALOGUE)


# --- helpers
def fix_title(title: str, lfooter: str) -> tuple[str, str]:
    """Shorten an ABS data item description into a title, moving qualifiers into the lfooter."""
    for check in TITLE_CHECKS:
        text = f"{check} ;"
        if text in title:
            title = title.replace(text, "")
            lfooter = lfooter + f"{check}. "
    title = (
        title.replace("Businesses", "")
        .replace("Business Finance", "Business Finance:")
        .replace("Households", "Households:")
        .replace(";", "")
        .replace("    ", " ")
        .replace("   ", " ")
        .replace("  ", " ")
        .strip()
    )
    return title, lfooter


def _sa_and_trend(release: AbsRelease, did: str) -> tuple[pd.DataFrame, str, str]:
    """Return the seasonally adjusted and trend series for a description, with units and full description."""
    meta = release.meta
    frame = pd.DataFrame()
    units = found_did = ""
    for series_type in (SA, TREND):
        found = meta[meta[mc.stype].str.contains(series_type) & meta[mc.did].str.contains(did)]
        if len(found) != 1:
            print(f"Error: {len(found)} rows found for {series_type} {did}")
            continue
        row = found.iloc[0]
        units, found_did = row[mc.unit], row[mc.did]
        frame[series_type] = release.data[row[mc.table]][row[mc.id]]
    return frame, units, found_did


def _seastrend(release: AbsRelease, did: str, *, dropna: bool) -> None:
    """Chart a description's seasonally adjusted and trend series, full history and recent."""
    frame, units, found_did = _sa_and_trend(release, did)
    frame, units = ra.recalibrate(frame.dropna(how="all") if dropna else frame, units)
    title, lfooter = fix_title(found_did, "Australia. ")
    multi_start(
        pd.DataFrame(frame),
        function=seastrend_plot_finalise,
        starts=quarterly_plot_times,
        title=title,
        ylabel=f"{units} / {_freq_letter(frame.index)}",
        lfooter=lfooter,
        rfooter=release.source,
    )


def _sa_series(release: AbsRelease, table: str, did: str, measure: str = "Value") -> pd.Series:
    """Return a national SA lending series, selected by description."""
    selector = {table: mc.table, f"{did} ;  New loan commitments ;  {measure} ;": mc.did, SA: mc.stype}
    _, series_id, _ = ra.find_abs_id(release.meta, selector)
    return release.data[table][series_id]


def _new_dwellings(release: AbsRelease, borrower: str, table: str) -> pd.Series:
    """Return lending for new dwellings (construction plus newly erected) for one borrower type."""
    first, *rest = (_sa_series(release, table, f"{borrower} ;  {purpose}") for purpose in NEW_DWELLING_PURPOSES)
    for series in rest:
        first = first + series
    return first


def _freq_letter(index: pd.Index) -> str:
    """Return the frequency letter of a PeriodIndex ("Q", "M"), for per-period y-labels."""
    if not isinstance(index, pd.PeriodIndex):
        raise TypeError("Expected a PeriodIndex")
    return index.freqstr[0]


def _average_housing_loan(release: AbsRelease) -> pd.Series:
    """Return the average new housing loan, $ per loan (value / number), from 2019Q3."""
    selector = {TOTAL_TABLE: mc.table, SA: mc.stype}
    _, value_id, _ = ra.find_abs_id(release.meta, selector | {HOUSING_DID + "  Value ;": mc.did})
    _, number_id, _ = ra.find_abs_id(release.meta, selector | {HOUSING_DID + "  Number ;": mc.did})
    data = release.data[TOTAL_TABLE]
    return (data[value_id].dropna() * MILLION / data[number_id].dropna()).dropna()


# --- charts
def headline_charts(release: AbsRelease) -> None:
    """Chart headline housing and business finance commitments: seasonally adjusted against trend."""
    for did in HEADLINE_DIDS:
        _seastrend(release, did, dropna=False)


def household_loan_numbers(release: AbsRelease) -> None:
    """Chart the number of new household housing loan commitments (excluding refinancing)."""
    _seastrend(release, HOUSING_DID + "  Number ;", dropna=True)


def new_dwelling_value(release: AbsRelease) -> None:
    """Chart new loan commitments for new dwellings, by borrower and purpose."""
    frame = pd.DataFrame()
    for borrower, table in NATIONAL_TABLES.items():
        for purpose, label in NEW_DWELLING_PURPOSES.items():
            frame[f"{borrower}: {label}"] = _sa_series(release, table, f"{borrower} ;  {purpose}")
    frame, units = ra.recalibrate(frame.dropna(how="all"), MILLIONS)
    multi_start(
        pd.DataFrame(frame),
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title="Household Lending for New Dwellings",
        ylabel=f"{units} / {_freq_letter(frame.index)}",
        annotate=True,
        legend=LEGEND_UPPER_LEFT,
        lfooter="Australia. Seasonally adjusted. New loan commitments. Investor split published from 2019Q3. ",
        rfooter=release.source,
    )


def new_dwelling_share(release: AbsRelease) -> None:
    """Chart new-dwelling lending as a share of household housing lending.

    The owner occupier basis runs from 2002Q3; the all-households basis needs the investor
    split, so it starts in 2019Q3.
    """
    owner_new = _new_dwellings(release, "Owner occupier", NATIONAL_TABLES["Owner occupier"])
    investor_new = _new_dwellings(release, "Investor", NATIONAL_TABLES["Investor"])
    owner_total = _sa_series(release, TOTAL_TABLE, "Owner occupier ;  Total dwellings excluding refinancing")
    all_total = _sa_series(release, TOTAL_TABLE, "Housing Finance ;  Total dwellings excluding refinancing")
    frame = pd.DataFrame(
        {
            "Owner occupier": owner_new / owner_total * PERCENT,
            "All households": (owner_new + investor_new) / all_total * PERCENT,
        }
    ).dropna(how="all")
    multi_start(
        frame,
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title="New Dwelling Share of Household Housing Lending",
        ylabel="Per cent of new loan commitments",
        annotate=True,
        legend=LEGEND_BEST,
        lfooter="Australia. Seasonally adjusted. Excluding refinancing. "
        "New dwellings = construction plus newly erected. ",
        rfooter=release.source,
    )


def dwelling_type(release: AbsRelease) -> None:
    """Chart new loan commitments for existing against new dwellings, by borrower.

    New dwellings are construction plus purchase of newly erected dwellings. With existing
    dwellings these sum to total dwellings excluding refinancing (land and alterations sit outside).
    """
    frame = pd.DataFrame()
    for borrower, table in NATIONAL_TABLES.items():
        frame[f"{borrower}: existing"] = _sa_series(
            release, table, f"{borrower} ;  Purchase of existing dwellings"
        )
        frame[f"{borrower}: new"] = _new_dwellings(release, borrower, table)
    frame, units = ra.recalibrate(frame.dropna(how="all"), MILLIONS)
    multi_start(
        pd.DataFrame(frame),
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title="Household Lending by Dwelling Type",
        ylabel=f"{units} / {_freq_letter(frame.index)}",
        annotate=True,
        legend=LEGEND_UPPER_LEFT,
        lfooter="Australia. Seasonally adjusted. Excluding refinancing. "
        "New = construction plus newly erected. Investor from 2019Q3. ",
        rfooter=release.source,
    )


def average_construction_loan(release: AbsRelease) -> None:
    """Chart the average owner occupier construction loan (value / number), from 2002Q3."""
    table = NATIONAL_TABLES["Owner occupier"]
    did = "Owner occupier ;  Construction of dwellings"
    value = _sa_series(release, table, did, "Value")  # $ million
    number = _sa_series(release, table, did, "Number")
    average, units = ra.recalibrate((value * MILLION / number).dropna(), "$")
    line_plot_finalise(
        average,
        title="Average New Construction Loan Size",
        ylabel=units,
        annotate=True,
        lfooter="Australia. Seasonally adjusted. Owner occupier construction of "
        "dwellings. New loan commitments value / number. ",
        rfooter=release.source,
    )


def business_charts(release: AbsRelease) -> None:
    """Chart each business finance total-purpose loan series."""
    meta = release.meta
    rows = meta[
        meta[mc.did].str.contains("Business")
        & meta[mc.did].str.contains("loans")
        & meta[mc.did].str.contains("Total purpose")
    ]
    for _, row in rows.iterrows():
        series, units = ra.recalibrate(release.data[row[mc.table]][row[mc.id]], row[mc.unit])
        title, lfooter = fix_title(row[mc.did], f"Australia. {SERIES_TYPE_NOTES[row[mc.stype]]} ")
        line_plot_finalise(
            series,
            title=title.replace("Businesses", "").strip(),
            ylabel=f"{units} / {_freq_letter(series.index)}",
            lfooter=lfooter,
            rfooter=release.source,
        )


def average_housing_loan(release: AbsRelease) -> None:
    """Chart the average new housing loan (value / number), households, excluding refinancing."""
    average, units = ra.recalibrate(_average_housing_loan(release), "$")
    line_plot_finalise(
        average,
        title="Average New Housing Loan Size",
        ylabel=units,
        annotate=True,
        rfooter=release.source,
        lfooter="Australia. Seasonally adjusted. Households: total dwellings "
        "excluding refinancing. New loan commitments value / number. ",
    )


def average_monthly_repayment(release: AbsRelease) -> None:
    """Chart the repayment on a 30-year loan of the average new size, at the discounted variable rate."""
    data, meta = rba.get_table(RATE_TABLE)
    column = meta[meta.Title == DISCOUNT_RATE_TITLE]["Series ID"].to_numpy()[0]
    rate = data[column].dropna().resample("Q").mean()
    frame = pd.concat({"loan": _average_housing_loan(release), "rate_pc": rate}, axis=1).dropna()
    months = TERM_YEARS * MONTHS_PER_YEAR
    monthly_rate = frame["rate_pc"] / PERCENT / MONTHS_PER_YEAR
    factor = (1 + monthly_rate) ** months
    payment, units = ra.recalibrate(frame["loan"] * monthly_rate * factor / (factor - 1), "$")
    line_plot_finalise(
        payment,
        title=f"Average Monthly Repayment: {TERM_YEARS}-year Loan at Discount Rate",
        ylabel=f"{units} per month",
        annotate=True,
        rounding=0,
        rfooter=f"{release.source}; RBA: {RATE_TABLE}",
        lfooter=f"Australia. Seasonally adjusted average new housing loan size. "
        f"{TERM_YEARS}-yr P&I; RBA discount variable owner-occupier rate. ",
    )


# --- table of contents, in run order
CHARTS = (
    (headline_charts, ()),
    (household_loan_numbers, ()),
    (new_dwelling_value, ()),
    (new_dwelling_share, ()),
    (dwelling_type, ()),
    (average_construction_loan, ()),
    (business_charts, ()),
    (average_housing_loan, ()),
    (average_monthly_repayment, ()),
)
