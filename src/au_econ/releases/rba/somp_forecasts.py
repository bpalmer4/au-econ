"""RBA Statement on Monetary Policy (SOMP) forecasts against what happened.

The forecast table of every SOMP since February 2019 (RBA web pages, via sources.rba),
set against ABS outcomes (5206.0, 6401.0, 6150.0.55.003, 6345.0, 6202.0, 3101.0), the
cash rate (RBA A2), the trade-weighted index (RBA F11.1 history) and Brent futures
(Yahoo Finance). Each chart is drawn three times: with every forecast vintage, with the
two latest, and with the latest alone.
"""

# --- dependencies
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import mgplot as mg
import numpy as np
import pandas as pd
import readabs as ra
from matplotlib import colormaps
from matplotlib.colors import to_hex
from readabs import metacol as mc

from au_econ.series.rates import get_cash_rate
from au_econ.sources import rba, yahoo
from au_econ.sources.abs import fetch_release

if TYPE_CHECKING:
    from matplotlib.axes import Axes

# --- module contract
RELEASE = ("somp",)
TOPICS = ("rba",)
TITLE = "SOMP Forecasts"

# --- constants
FIRST_YEAR = 2019  # the first SOMP read
LOCAL_TIME = "Australia/Sydney"  # the RBA's clock, for which reports should be out
QUARTERS = (1, 2, 3, 4)
ALL_VINTAGES = 0
VINTAGE_COUNTS = (ALL_VINTAGES, 2, 1)  # forecast vintages per chart: every one, the two latest, the latest
REPORT_FREQ = "Q-NOV"  # SOMP reports come out in Feb, May, Aug and Nov
FORECAST_FREQ = "Q-DEC"
PERCENT = 100.0
YEAR_QUARTERS = 4
UNEMPLOYMENT = "Unemployment Rate"

# all charts start at the last period of 2019 (partial-string slices, whatever the frequency alias)
PLOT_START_Q = "2019Q4"
PLOT_START_M = "2019-12"

HISTORY_COLOR = ["darkorange"]
HISTORY_WIDTH = 2
FORECAST_COLORS = ("royalblue", "indianred")
LATEST_COLOR = "darkred"
FORECAST_WIDTH = 1
FORECAST_MARKERSIZE = 2
STYLES = ("-", "--", "-.", ":")
MARKERS = ("o", "s", "D", "x", "P", "H", "v", "^", "<", ">", "1", "2", "3", "4", "8", "p", "*", "h", "+", "X", "D")
CROWDED_LEGEND = 5  # more vintages than this get the smaller legend font
SHADE_MAP = "viridis"  # earlier vintages, dark (oldest) to light
NO_LEGEND = "_nolegend_"  # matplotlib leaves a line with this label out of the legend

MINUS_SIGN = chr(0x2212)  # the SOMP pages write negatives with the Unicode minus sign
FRACTIONS = {"¼": ".25", "½": ".5", "¾": ".75", MINUS_SIGN: "-"}  # SOMP text: fractions and the minus sign
FOOTNOTE_MARKER = r"\([a-z]\)$"  # e.g. "Employment(a)", from Feb 2024

# ABS series, chosen by data item description: handle -> (catalogue, table, selector)
GDP_CAT = "5206.0"
GDP_KAGS = "5206001_Key_Aggregates"
GDP_HHC = "5206008_Household_Final_Consumption_Expenditure"
GDP_EXP = "5206002_Expenditure_Volume_Measures"
GDP_TAX = "5206022_Taxes"
GDP_IPD = "5206005_Expenditure_Implicit_Price_Deflators"
GDP_HHI = "5206020_Household_Income"
GDP_SAS = "5206024_Selected_Analytical_Series"
GDP_PAY = "5206023_Social_Assistance_Benefits"
CPI_CAT, CPI_APPENDIX = "6401.0", "64010Appendix1a"
LA_CAT = "6150.0.55.003"
LA_TOTAL = "6150055003DO001"  # total, all industries
LA_SUMMARY = "Industry summary table"  # total and per-industry hours
WPI_CAT, WPI_TABLE = "6345.0", "634501"
LFS_CAT, LFS_TABLE = "6202.0", "62020001"
ERP_CAT, ERP_TABLE = "3101.0", "310101"
SA, ORIG = "Seasonally Adjusted", "Original"
IDX, MILL, DOLLARS = "Index Numbers", "$ Millions", "$"
WPI_DID = (
    "Quarterly Index ;  Total hourly rates of pay excluding bonuses ;  "
    "Australia ;  Private and Public ;  All industries ;"
)
HOURS_WORKED_DID = "Volume; Labour Account hours actually worked in all jobs ;"
GDP_CVM_DID = "Gross domestic product: Chain volume measures ;"

WANTED_ABS: dict[str, tuple[str, str, dict[str, str]]] = {
    # indexes
    "CPI Index SA": (CPI_CAT, CPI_APPENDIX, {"All groups CPI, seasonally adjusted": mc.did, IDX: mc.unit}),
    "CPI Index TM SA": (CPI_CAT, CPI_APPENDIX, {"Trimmed Mean": mc.did, IDX: mc.unit}),
    "HHIPD Index CVM SA": (
        GDP_CAT,
        GDP_IPD,
        {"Households ;  Final consumption expenditure ;": mc.did, SA: mc.stype, IDX: mc.unit},
    ),
    "GNEIPD Index CVM SA": (
        GDP_CAT,
        GDP_IPD,
        {"Gross national expenditure ;": mc.did, SA: mc.stype, IDX: mc.unit},
    ),
    "GDPIPD Index CVM SA": (GDP_CAT, GDP_IPD, {"GROSS DOMESTIC PRODUCT ;": mc.did, SA: mc.stype, IDX: mc.unit}),
    "WPI Index SA": (WPI_CAT, WPI_TABLE, {WPI_DID: mc.did, SA: mc.stype, IDX: mc.unit}),
    "WPI Index Orig": (WPI_CAT, WPI_TABLE, {WPI_DID: mc.did, ORIG: mc.stype, IDX: mc.unit}),
    # employment
    "Thousand Employed SA": (
        LFS_CAT,
        LFS_TABLE,
        {"Employed total ;  Persons ;": mc.did, SA: mc.stype, "000": mc.unit},
    ),
    "Unemployment Rate SA": (
        LFS_CAT,
        LFS_TABLE,
        {"Unemployment rate ;  Persons ;": mc.did, SA: mc.stype, "Percent": mc.unit},
    ),
    # Labour Account: hours sought (total-industries table) and hours worked by industry (summary table)
    "LA Hours sought SA": (
        LA_CAT,
        LA_TOTAL,
        {
            LA_TOTAL: mc.table,
            "Volume; Hours sought but not worked ;": mc.did,
            "Total all industries": mc.did,
            SA: mc.stype,
            "000 Hours": mc.unit,
        },
    ),
    "LA Hours worked total SA": (
        LA_CAT,
        LA_SUMMARY,
        {
            LA_SUMMARY: mc.table,
            HOURS_WORKED_DID: mc.did,
            "Total all industries": mc.did,
            SA: mc.stype,
            "000 Hours": mc.unit,
        },
    ),
    "LA Hours worked agriculture SA": (
        LA_CAT,
        LA_SUMMARY,
        {
            LA_SUMMARY: mc.table,
            HOURS_WORKED_DID: mc.did,
            "Agriculture, forestry and fishing": mc.did,
            SA: mc.stype,
            "000 Hours": mc.unit,
        },
    ),
    # population
    "Estimated Resident Population Orig": (
        ERP_CAT,
        ERP_TABLE,
        {"Estimated Resident Population (ERP) ;  Australia ;": mc.did, ORIG: mc.stype, "000": mc.unit},
    ),
    "GDP per capita CVM Orig": (
        GDP_CAT,
        GDP_KAGS,
        {"GDP per capita: Chain volume measures ;": mc.did, ORIG: mc.stype, DOLLARS: mc.unit},
    ),
    "GDP CVM Orig": (GDP_CAT, GDP_KAGS, {GDP_CVM_DID: mc.did, ORIG: mc.stype, MILL: mc.unit}),
    # GDP
    "GDP CVM SA": (GDP_CAT, GDP_KAGS, {GDP_CVM_DID: mc.did, SA: mc.stype, MILL: mc.unit}),
    "Household savings ratio SA": (
        GDP_CAT,
        GDP_KAGS,
        {"Household saving ratio: Ratio ;": mc.did, SA: mc.stype, "proportion": mc.unit},
    ),
    "Household consumption CVM SA": (
        GDP_CAT,
        GDP_HHC,
        {"FINAL CONSUMPTION EXPENDITURE: Chain volume measures ;": mc.did, SA: mc.stype, MILL: mc.unit},
    ),
    "GNE CVM SA": (GDP_CAT, GDP_EXP, {"Gross national expenditure ;": mc.did, SA: mc.stype, MILL: mc.unit}),
    "Exports CVM SA": (GDP_CAT, GDP_EXP, {"Exports of goods and services ;": mc.did, SA: mc.stype, MILL: mc.unit}),
    "Imports CVM SA": (GDP_CAT, GDP_EXP, {"Imports of goods and services ;": mc.did, SA: mc.stype, MILL: mc.unit}),
    "Gross Disposable Income CP SA": (
        GDP_CAT,
        GDP_HHI,
        {"GROSS DISPOSABLE INCOME ;": mc.did, SA: mc.stype, MILL: mc.unit},
    ),
    "Taxes on income CP SA": (
        GDP_CAT,
        GDP_TAX,
        {"Taxes on income - Total ;": mc.did, SA: mc.stype, MILL: mc.unit},
    ),
    "Terms of Trade Index (SA)": (
        GDP_CAT,
        GDP_KAGS,
        {"Terms of trade: Index ;": mc.did, SA: mc.stype, IDX: mc.unit},
    ),
    "Non-farm GDP CVM SA": (GDP_CAT, GDP_SAS, {f"Non-farm ;  {GDP_CVM_DID}": mc.did, SA: mc.stype, MILL: mc.unit}),
    "Non-farm total compensation employees CP SA": (
        GDP_CAT,
        GDP_SAS,
        {"Non-farm ;  Total compensation of employees: Current prices ;": mc.did, SA: mc.stype, MILL: mc.unit},
    ),
    # the SOMP's "Business Investment" is the ABS "New private business investment", not the total
    "New private business investment CVM SA": (
        GDP_CAT,
        GDP_SAS,
        {"New private business investment: Chain volume measures ;": mc.did, SA: mc.stype, MILL: mc.unit},
    ),
    "NF hourly pay CP SA": (
        GDP_CAT,
        GDP_SAS,
        {"Non-farm compensation of employees per hour: Current prices ;": mc.did, SA: mc.stype, DOLLARS: mc.unit},
    ),
    "Public Final demand CVM SA": (
        GDP_CAT,
        GDP_SAS,
        {"Public ;  Final demand: Chain volume measures ;": mc.did, SA: mc.stype, MILL: mc.unit},
    ),
    "Social Assistance Benefits CP Orig": (
        GDP_CAT,
        GDP_PAY,
        {"General government ;  Total personal benefits payments ;": mc.did, ORIG: mc.stype, MILL: mc.unit},
    ),
    # other
    "Dwelling Investment CVM SA": (
        GDP_CAT,
        GDP_EXP,
        {"Dwellings - Total": mc.did, "Private": mc.did, SA: mc.stype, MILL: mc.unit},
    ),
}

# left-footer fragments: text, full stop, space
ORIGINAL_NOTE = "Original series. "
SA_NOTE = "Seasonally adjusted. "
CVM_SA_NOTE = f"CVM. {SA_NOTE}"
LFS_NOTE = f"Quarterly mean monthly data from Labour Force Survey. {SA_NOTE}"
CPI_NOTE = "Calculated using CPI. "
HFCE_NOTE = "Deflated by Household FCE IPD. "
UNDERUTILISATION_NOTE = f"Labour Account: hours sought / (sought + worked). {SA_NOTE}"
PRODUCTIVITY_NOTE = f"Non-farm GDP per Labour Account non-farm hours worked. {SA_NOTE}"
MIDDLE_MONTH_NOTE = "SOMP assumptions on each quarter's middle month. "

SOMP_ABS_PAIRS = (  # (SOMP series, ABS series, left-footer note)
    ("Gross Domestic Product", "GDP CVM SA", CVM_SA_NOTE),
    ("Household Consumption", "Household consumption CVM SA", CVM_SA_NOTE),
    ("Gross National Expenditure", "GNE CVM SA", CVM_SA_NOTE),
    ("Exports", "Exports CVM SA", CVM_SA_NOTE),
    ("Imports", "Imports CVM SA", CVM_SA_NOTE),
    ("Wage Price Index", "WPI Index SA", SA_NOTE),
    ("Employment", "Thousand Employed SA", LFS_NOTE),
    ("Unemployment Rate", "Unemployment Rate SA", LFS_NOTE),
    ("Trimmed Mean Inflation", "CPI Index TM SA", SA_NOTE),
    ("Consumer Price Index", "CPI Index SA", SA_NOTE),
    (
        "Estimated Resident Population",
        "GDP population",
        f"Population implied in ABS National Accounts. {ORIGINAL_NOTE}",
    ),
    (
        "Estimated Resident Population",
        "Estimated Resident Population Orig",
        f"ABS population estimates. {ORIGINAL_NOTE}",
    ),
    ("Terms Of Trade", "Terms of Trade Index (SA)", SA_NOTE),
    ("Labour Productivity", "NF labour productivity", PRODUCTIVITY_NOTE),
    ("Real Wage Price Index", "Real WPI", f"{CPI_NOTE}{SA_NOTE}"),
    ("Real Average Earnings Per Hour (Non-Farm)", "Real hourly pay", f"{CPI_NOTE}{SA_NOTE}"),
    ("Public Demand", "Public Final demand CVM SA", CVM_SA_NOTE),
    ("Dwelling Investment", "Dwelling Investment CVM SA", f"Private. {CVM_SA_NOTE}"),
    (
        "Business Investment",
        "New private business investment CVM SA",
        f"New private business investment. {CVM_SA_NOTE}",
    ),
    ("Household Savings Rate (%)", "Household savings ratio SA", SA_NOTE),
    ("Nominal Average Earnings Per Hour (Non-Farm)", "NF hourly pay CP SA", SA_NOTE),
    ("Real Household Disposable Income", "Real Household Disposable Income", HFCE_NOTE),
    ("Hours-Based Underutilisation Rate (Quarterly, %)", "Hours-Based Underutilisation", UNDERUTILISATION_NOTE),
)
LEVEL_SERIES = (  # SOMP series charted as levels; the rest as annual growth
    "Unemployment Rate",
    "Household Savings Rate (%)",
    "Hours-Based Underutilisation Rate (Quarterly, %)",
)

# RBA and Yahoo series
RBA_SERIES = {"Trade-weighted index": "FXRTWI"}  # label: RBA series ID
TWI_TABLE = "Z:F11.1-Monthly"
CASH_RATE_NAME = "RBA Official Cash Rate"
BRENT_TICKER = "BZ=F"
BRENT_START = "2015-01-01"
MIN_TRADING_DAYS = 15  # a month with fewer daily quotes (the partial current month) is dropped


@dataclass(frozen=True)
class SompData:
    """SOMP forecasts by subject (rows: forecast quarter, columns: report quarter); history to compare."""

    somp: dict[str, pd.DataFrame]
    abs_series: dict[str, pd.Series]
    abs_sources: dict[str, str]  # handle: "ABS: <catalogue>"
    cash_rate: pd.Series
    twi: pd.Series
    brent: pd.Series


# --- data
def _clean(table: pd.DataFrame) -> pd.DataFrame:
    """Index a raw SOMP table by subject, with numbers (fractions resolved) for the forecasts."""
    table = table.set_index(table.columns[0])
    table.index.name = "Index"
    for col in table.columns:
        text = table[col].astype(str)
        for symbol, replacement in FRACTIONS.items():
            text = text.str.replace(symbol, replacement)
        table[col] = pd.to_numeric(text, errors="coerce")
    table = table.dropna(how="all", axis="index")  # section headings, from Feb 2024
    table.index = table.index.str.replace(FOOTNOTE_MARKER, "", regex=True).str.title()
    return table


def _somp_reports() -> dict[str, pd.DataFrame]:
    """Each SOMP forecast table so far, keyed by report quarter (e.g. "2026Q3")."""
    now = datetime.now(tz=ZoneInfo(LOCAL_TIME))
    last_year, last_quarter = now.year, (now.month + 1) // 4 + 1
    reports = {}
    for year in range(FIRST_YEAR, last_year + 1):
        for quarter in QUARTERS:
            if year == last_year and quarter > last_quarter:
                break
            raw = rba.get_somp_table(year, quarter)
            if raw is not None:
                reports[f"{year}Q{quarter}"] = _clean(raw)
    if not reports:
        raise ValueError("No SOMP forecast tables found")
    return reports


def _by_subject(reports: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Regroup report tables into one table per subject: forecast quarters by report quarters."""
    rows: dict[str, list[pd.Series]] = {}
    for report, table in reports.items():
        for subject in table.index:
            if subject.startswith("("):
                continue  # a footnote
            row = table.loc[subject].rename(report)
            rows.setdefault(UNEMPLOYMENT if UNEMPLOYMENT in subject else subject, []).append(row)
    by_subject = {}
    for subject, subject_rows in rows.items():
        table = pd.concat(subject_rows, axis=1)
        by_subject[subject] = pd.DataFrame(
            table.to_numpy(),
            columns=pd.PeriodIndex(table.columns, freq=REPORT_FREQ),
            index=pd.PeriodIndex(table.index, freq=FORECAST_FREQ),
        )
    return by_subject


def _abs_series() -> tuple[dict[str, pd.Series], dict[str, str]]:
    """Each wanted ABS series by handle, and its source note."""
    releases = {}
    series, sources = {}, {}
    for handle, (catalogue, table_name, selector) in WANTED_ABS.items():
        if (catalogue, table_name) not in releases:
            releases[(catalogue, table_name)] = fetch_release(catalogue, single_excel_only=table_name)
        release = releases[(catalogue, table_name)]
        table, series_id, _ = ra.find_abs_id(release.meta, {table_name: mc.table, **selector}, verbose=False)
        series[handle] = release.data[table][series_id]
        sources[handle] = release.source
    return series, sources


def _derived(series: dict[str, pd.Series], sources: dict[str, str]) -> None:
    """Add the series the RBA forecasts but the ABS does not publish as such (in place)."""
    # population implied by GDP and GDP per capita
    series["GDP population"] = series["GDP CVM Orig"] / series["GDP per capita CVM Orig"]
    sources["GDP population"] = sources["GDP per capita CVM Orig"]

    # non-farm labour productivity: non-farm GDP per Labour Account non-farm hours
    non_farm_hours = series["LA Hours worked total SA"] - series["LA Hours worked agriculture SA"]
    series["NF labour productivity"] = series["Non-farm GDP CVM SA"] / non_farm_hours
    sources["NF labour productivity"] = f"{sources['Non-farm GDP CVM SA']}, {LA_CAT}"

    # hours-based underutilisation: hours sought / (sought + worked); it runs ~0.3-0.4pp above
    # the RBA's series, probably from how the unemployed's sought hours are imputed
    sought, worked = series["LA Hours sought SA"], series["LA Hours worked total SA"]
    series["Hours-Based Underutilisation"] = PERCENT * sought / (sought + worked)
    sources["Hours-Based Underutilisation"] = sources["LA Hours sought SA"]

    # real wages and income
    series["Real WPI"] = series["WPI Index SA"] / series["CPI Index SA"]
    sources["Real WPI"] = f"{sources['WPI Index SA']}, {CPI_CAT}"
    series["Real hourly pay"] = series["NF hourly pay CP SA"] / series["CPI Index SA"]
    sources["Real hourly pay"] = f"{sources['NF hourly pay CP SA']}, {CPI_CAT}"
    series["Real Household Disposable Income"] = (
        series["Gross Disposable Income CP SA"] / series["HHIPD Index CVM SA"]
    )
    sources["Real Household Disposable Income"] = sources["Gross Disposable Income CP SA"]


def _twi() -> pd.Series:
    """Return the monthly trade-weighted index (RBA F11.1 history)."""
    frame, _ = rba.get_table(TWI_TABLE)
    twi = frame[RBA_SERIES["Trade-weighted index"]].astype(float).dropna()
    if not isinstance(twi.index, pd.PeriodIndex):
        raise TypeError(f"RBA {TWI_TABLE}: expected a PeriodIndex")
    twi.index = twi.index.to_timestamp().to_period("M")
    return twi.rename("TWI")


def _brent() -> pd.Series:
    """Monthly mean of daily Brent front-month futures, complete months only."""
    daily = yahoo.get_close(BRENT_TICKER, BRENT_START)
    counts = daily.resample("M").count()
    return daily.resample("M").mean()[counts >= MIN_TRADING_DAYS].rename("Brent")


def fetch() -> SompData:
    """Fetch every SOMP forecast table and the outcomes to compare them with."""
    abs_series, abs_sources = _abs_series()
    _derived(abs_series, abs_sources)
    return SompData(
        somp=_by_subject(_somp_reports()),
        abs_series=abs_series,
        abs_sources=abs_sources,
        cash_rate=get_cash_rate().rename(CASH_RATE_NAME),
        twi=_twi(),
        brent=_brent(),
    )


# --- helpers
def _annotation(*, single: bool, label: str = "") -> dict[str, Any]:
    """End-of-line labels: with one vintage, values at the right edge; with more, each line's vintage."""
    if single:
        return {"annotate": True, "force_right": True, "leader_lines": True}
    return {"annotate": label, "leader_lines": True, "fontsize": "xx-small"}


def _tag(vintages: int) -> str:
    """Return the file-name tag for a vintage count: "all", "2" or "1"."""
    return "all" if vintages == ALL_VINTAGES else str(vintages)


def _shading_note(forecasts: pd.DataFrame, vintages: int) -> str:
    """Return the header explaining the shades of an all-vintages chart; empty otherwise."""
    if vintages != ALL_VINTAGES:
        return ""
    first = forecasts.columns[0]
    if not isinstance(first, pd.Period):
        raise TypeError(f"SOMP report {first!r} is not a Period")
    return f"Earlier SOMPs shaded dark ({first.year}) to light."


def _plot_all_forecasts(axes: Axes, forecasts: pd.DataFrame) -> None:
    """Add every SOMP vintage: earlier ones thin, shaded and unlabelled; the latest labelled in dark red."""
    earlier, last = forecasts.columns[:-1], forecasts.columns[-1]
    shades = [to_hex(shade) for shade in colormaps[SHADE_MAP](np.linspace(0, 1, len(earlier)))]
    for report, shade in zip(earlier, shades, strict=True):
        series = forecasts[report].astype(float).dropna()
        if series.empty:
            continue  # a vintage wholly before the chart window
        mg.line_plot(series.rename(NO_LEGEND), ax=axes, color=[shade], width=FORECAST_WIDTH, annotate=False)
    label = str(last)[2:]  # e.g. "26Q3"
    mg.line_plot(
        forecasts[last].astype(float).dropna().rename(label),
        ax=axes,
        color=[LATEST_COLOR],
        width=FORECAST_WIDTH,
        marker=MARKERS[0],
        markersize=FORECAST_MARKERSIZE,
        **_annotation(single=False, label=label),
    )


def _plot_forecasts(axes: Axes, forecasts: pd.DataFrame, vintages: int, start: pd.Period) -> None:
    """Add SOMP forecast vintages from start: every one, or the latest few with the latest in dark red."""
    forecasts = forecasts.loc[forecasts.index >= start]
    if vintages == ALL_VINTAGES:
        _plot_all_forecasts(axes, forecasts)
        return
    forecasts = forecasts[forecasts.columns[-vintages:]]
    single = len(forecasts.columns) == 1
    last = forecasts.columns[-1]
    for count, (report, color) in enumerate(zip(forecasts.columns, FORECAST_COLORS, strict=False)):
        series = forecasts[report].astype(float).dropna()
        if series.empty:
            continue
        label = str(report)[2:]  # e.g. "26Q3"
        mg.line_plot(
            series.rename(label),
            ax=axes,
            color=[LATEST_COLOR if report == last else color],
            width=FORECAST_WIDTH,
            style=STYLES[count % len(STYLES)],
            marker=MARKERS[count % len(MARKERS)],
            markersize=FORECAST_MARKERSIZE,
            **_annotation(single=single, label=label),
        )


def _history_with_forecasts(
    history: pd.Series,
    forecasts: pd.DataFrame,
    vintages: int,
    *,
    title: str,
    ylabel: str,
    lfooter: str,
    rfooter: str,
    drawstyle: str | None = None,
    y0: bool = False,
    middle_month: bool = False,
) -> None:
    """Chart a monthly history with quarterly SOMP forecasts placed on a month of each quarter.

    The forecast goes on the quarter's last month, or with middle_month on its middle month
    (for a quarterly average of a monthly series). dropna=False keeps each vintage's own span.
    """
    monthly = ra.qtly_to_monthly(forecasts, interpolate=False, dropna=False)
    if middle_month:
        monthly.index = monthly.index - 1
    kwargs: dict[str, Any] = {"color": HISTORY_COLOR, "width": HISTORY_WIDTH, **_annotation(single=vintages == 1)}
    if drawstyle is not None:
        kwargs["drawstyle"] = drawstyle
    axes = mg.line_plot(history, **kwargs)
    _plot_forecasts(axes, monthly, vintages, pd.Period(PLOT_START_M, freq="M"))
    mg.finalise_plot(
        axes,
        title=title,
        ylabel=ylabel,
        legend={
            "loc": "best",
            "fontsize": "xx-small" if len(monthly.columns) > CROWDED_LEGEND else "x-small",
            "ncol": 3,
        },
        lfooter=f"{lfooter}Data to {history.index[-1]}. ",
        rfooter=rfooter,
        lheader=_shading_note(forecasts, vintages),
        tag=_tag(vintages),
        y0=y0,
    )


# --- charts
def somp_vs_abs(data: SompData) -> None:
    """Chart each SOMP forecast against the ABS outcome: annual growth, or the level for rates."""
    for vintages in VINTAGE_COUNTS:
        for i, (subject, handle, note) in enumerate(SOMP_ABS_PAIRS):
            series = data.abs_series[handle]
            if not isinstance(series.index, pd.PeriodIndex):
                raise TypeError(f"ABS {handle}: expected a PeriodIndex")
            if series.index.freqstr[0] == "M":
                series = ra.monthly_to_qtly(series, q_ending="DEC", f="mean")
            if subject in LEVEL_SERIES:
                history, measure = series, ""
            else:
                history = series.pct_change(periods=YEAR_QUARTERS, fill_method=None).dropna() * PERCENT
                measure = "Annual Growth"
            axes = mg.line_plot(
                history.loc[PLOT_START_Q:].rename(subject),
                color=HISTORY_COLOR,
                width=HISTORY_WIDTH,
                **_annotation(single=vintages == 1),
            )
            _plot_forecasts(axes, data.somp[subject], vintages, pd.Period(PLOT_START_Q, freq=FORECAST_FREQ))
            mg.finalise_plot(
                axes,
                title=f"SOMP: {subject} {measure}".rstrip(),
                ylabel=f"% {measure}",
                xlabel=None,
                legend={"loc": "best", "fontsize": "x-small", "ncol": 3},
                lfooter=f"Australia. {note}Data to {history.index[-1]}. ",
                rfooter=f"{data.abs_sources[handle]}; RBA: SOMP",
                lheader=_shading_note(data.somp[subject], vintages),
                tag=f"{i}-{_tag(vintages)}",
                y0=True,
            )


def cash_rate_assumptions(data: SompData) -> None:
    """Chart the cash rate against each SOMP's market-based path."""
    for vintages in VINTAGE_COUNTS:
        _history_with_forecasts(
            data.cash_rate.loc[PLOT_START_M:],
            data.somp["Cash Rate (%)"],
            vintages,
            title="SOMP: Official Cash Rate",
            ylabel="%",
            lfooter="Australia. OCR at month end. SOMP assumptions on each quarter's last month. ",
            rfooter="RBA: A2, SOMP",
            drawstyle="steps-post",
            y0=True,
        )


def twi_assumptions(data: SompData) -> None:
    """Chart the monthly trade-weighted index against each SOMP's assumption."""
    for vintages in VINTAGE_COUNTS:
        _history_with_forecasts(
            data.twi.loc[PLOT_START_M:],
            data.somp["Trade-Weighted Index (Index)"],
            vintages,
            title="SOMP: Trade-Weighted Index",
            ylabel="Index (May 1970 = 100)",
            lfooter=f"Australia. {ORIGINAL_NOTE}Monthly TWI. {MIDDLE_MONTH_NOTE}",
            rfooter="RBA: F11.1, SOMP",
            middle_month=True,
        )


def oil_assumptions(data: SompData) -> None:
    """Chart the monthly Brent price against each SOMP's assumption."""
    for vintages in VINTAGE_COUNTS:
        _history_with_forecasts(
            data.brent.loc[PLOT_START_M:],
            data.somp["Brent Crude Oil Price (Us$/Bbl)"],
            vintages,
            title="SOMP: Brent Crude Oil Price",
            ylabel="US$ per barrel",
            lfooter=f"Monthly mean of daily front-month futures ({BRENT_TICKER}). {MIDDLE_MONTH_NOTE}",
            rfooter="Yahoo; RBA: SOMP",
            middle_month=True,
        )


def unemployment_monthly(data: SompData) -> None:
    """Chart the monthly unemployment rate against each SOMP's forecasts (quarterly averages)."""
    handle = "Unemployment Rate SA"
    for vintages in VINTAGE_COUNTS:
        _history_with_forecasts(
            data.abs_series[handle].astype(float).dropna().rename(UNEMPLOYMENT).loc[PLOT_START_M:],
            data.somp[UNEMPLOYMENT],
            vintages,
            title="SOMP: Unemployment Rate (Monthly)",
            ylabel="%",
            lfooter="Australia. Monthly LFS, seasonally adjusted. SOMP forecasts on each quarter's middle month. ",
            rfooter=f"{data.abs_sources[handle]}; RBA: SOMP",
            middle_month=True,
        )


CHARTS = (
    (somp_vs_abs, ()),
    (cash_rate_assumptions, ()),
    (twi_assumptions, ()),
    (oil_assumptions, ()),
    (unemployment_monthly, ()),
)
