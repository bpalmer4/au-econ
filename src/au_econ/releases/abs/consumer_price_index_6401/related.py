"""CPI against related series, drawing on other releases as well as 6401.0.

The long splices with the discontinued monthly indicator (6484.0), the CPI beside other price
measures (WPI, PPI, deflators), Phillips curves, nominal GDP per capita, the misery index, and
the CPI rebased against rents, wages and household income.
"""

# --- dependencies
from functools import cache
from typing import TYPE_CHECKING, Any

import matplotlib.pyplot as plt
import mgplot as mg
import numpy as np
import pandas as pd
import readabs as ra
from readabs import metacol as mc
from statsmodels.tsa.filters.hp_filter import hpfilter

from au_econ.charting.footers import SERIES_TYPE_NOTES, data_to
from au_econ.charting.targets import ANNUAL_CPI_TARGET_RANGE, QUARTERLY_CPI_TARGET
from au_econ.charting.windows import quarterly_plot_times
from au_econ.releases.abs.consumer_price_index_6401.measures import (
    APPENDIX,
    APPENDIX_NOTE,
    LONG_HEADLINE,
    MONTHLY,
    long_headline,
    to_monthly,
)

if TYPE_CHECKING:
    from matplotlib.axes import Axes

    from au_econ.sources.abs import AbsRelease

# --- constants
PERCENT = 100
MONTHS_PER_YEAR, QUARTERS_PER_YEAR = 12, 4
ORIGINAL, SEASONALLY_ADJUSTED = "Original", "Seasonally Adjusted"
STYPES = {"O": ORIGINAL, "S": SEASONALLY_ADJUSTED}
YEAR_ON_YEAR_TERMS = ("Percentage", "revious", "ear")  # the published year-on-year series; ABS case varies
AUSTRALIA = "Australia. "

# catalogues and tables beyond 6401.0
INDICATOR = "6484.0"  # the discontinued Monthly CPI Indicator
INDICATOR_URL = (
    "https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/"
    "monthly-consumer-price-index-indicator/latest-release"
)
FINAL_QUARTERLY_URL = (  # the last quarterly CPI, Sep quarter 2025: its 640108 is not in later releases
    "https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/"
    "consumer-price-index-australia/sep-quarter-2025"
)
FINAL_QUARTERLY_TABLE = "640108"
NA, NA_DEFLATORS = "5206.0", "5206005_Expenditure_Implicit_Price_Deflators"
NA_KEY_AGGS, NA_HOUSEHOLD_INCOME = "5206001_Key_Aggregates", "5206020_Household_Income"
WPI, WPI_TABLE = "6345.0", "634501"
PPI, PPI_TABLE = "6427.0", "642701"
LFS, LFS_TABLE = "6202.0", "62020001"
AWE, AWE_TABLE = "6302.0", "6302002"
MODELLERS, MODELLERS_TABLE = "1364.0.15.003", "1364015003"
CPI = "6401.0"


# a requested series: (catalogue, table, description, series type code, unit, published year-on-year,
# calculate year-on-year)
type Request = tuple[str, str, str, str, str, bool, bool]

MULTI_MEASURE: dict[str, Request] = {
    "Qrtly Headline CPI (SA)": (CPI, APPENDIX, "All groups CPI, seasonally adjusted", "S", "", True, False),
    "Qrtly Trimmed Mean CPI (SA)": (CPI, APPENDIX, "Trimmed Mean", "S", "", True, False),
    "Qrtly Weighted Median CPI (SA)": (CPI, APPENDIX, "Weighted Median", "S", "", True, False),
    "Monthly Headline CPI (SA)": (CPI, MONTHLY, "All groups CPI, seasonally adjusted", "S", "", True, False),
    "Monthly Trimmed Mean CPI (SA)": (CPI, MONTHLY, "Trimmed Mean", "S", "", True, False),
    "Monthly Weighted Median CPI (SA)": (CPI, MONTHLY, "Weighted Median", "S", "", True, False),
    "Producer Price Index (Orig)": (PPI, PPI_TABLE, "Final ;  Total (Source) ;", "O", "", True, False),
    "Wage Price Index (All sectors) (SA)": (
        WPI,
        WPI_TABLE,
        "Total hourly rates of pay excluding bonuses ;  Private and Public ;  All industries ;",
        "S",
        "",
        True,
        False,
    ),
    "Households implicit price deflator (SA)": (
        NA,
        NA_DEFLATORS,
        "Households ;  Final consumption expenditure ;",
        "S",
        "Index",
        False,
        True,
    ),
    "GNE implicit price deflator (SA)": (
        NA,
        NA_DEFLATORS,
        "Gross national expenditure ;",
        "S",
        "Index",
        False,
        True,
    ),
}
MEASURES_LFOOTER = f"{AUSTRALIA}Orig = Original series. SA = Seasonally adjusted. Quarterly CPI from Appendix 1a. "
MULTI_MEASURE_STARTS = (0, pd.Period("1989-12"), pd.Period("2019-12"), pd.Period("2022-12"), pd.Period("2024-06"))
TEN_COLOURS = (
    "tab:blue",
    "tab:orange",
    "tab:green",
    "tab:red",
    "tab:purple",
    "tab:brown",
    "tab:pink",
    "tab:gray",
    "tab:olive",
    "tab:cyan",
)

MEASURE_GROWTH: dict[str, Request] = {
    "Producer Price Index (Orig)": (
        PPI,
        PPI_TABLE,
        "Final ;  Total (Source) ;",
        "O",
        "Index Numbers",
        False,
        False,
    ),
    "Wage Price Index (All sectors) (SA)": (
        WPI,
        WPI_TABLE,
        "Quarterly Index ;  Total hourly rates of pay excluding bonuses ;  Australia ;  Private and Public",
        "S",
        "Index Numbers",
        False,
        False,
    ),
    "Households implicit price deflator (SA)": (
        NA,
        NA_DEFLATORS,
        "Households ;  Final consumption expenditure ;",
        "S",
        "Index",
        False,
        False,
    ),
    "GNE implicit price deflator (SA)": (
        NA,
        NA_DEFLATORS,
        "Gross national expenditure ;",
        "S",
        "Index",
        False,
        False,
    ),
}
GROWTH_FROM = quarterly_plot_times[1]

# goods v services, tradeables v non-tradeables
GOODS_SERVICES = {"Goods": "All groups, goods component", "Services": "All groups, services component"}
TRADEABLES = {"Tradeables": "Tradables ;", "Non-tradeables": "Non-tradables ;"}
PAIR_RFOOTER = "ABS: 6401.0, 6484.0"
PAIR_LFOOTER = (
    f"{AUSTRALIA}Original series. Year-ended growth. Monthly CPI Indicator (6484.0) spliced under the monthly "
    "CPI (6401.0). "
)
OVERLAY_LFOOTER = (
    f"{AUSTRALIA}Original series. Year-ended growth. Solid: monthly CPI. "
    "Dashed: final quarterly CPI (Sep-qtr 2025). "
)
LONG_LFOOTER = (
    f"{AUSTRALIA}Original series. Year-ended growth. Monthly CPI over indicator over final quarterly "
    "CPI (Sep-qtr 2025). "
)
OVERLAY_COLOURS = ("darkblue", "darkorange", "darkblue", "darkorange")
OVERLAY_STYLES = ("-", "-", "--", "--")
pair_starts = 0, -(3 * MONTHS_PER_YEAR + 1)

# headline v trimmed mean
HVT_YOY_DID = "Percentage Change from Corresponding Month of Previous Year ;"
HVT_MEASURES = {  # label: (description, current CPI series type, indicator series type)
    "Headline": ("All groups CPI ;  Australia ;", ORIGINAL, ORIGINAL),
    "Trimmed Mean": ("Trimmed Mean ;  Australia ;", SEASONALLY_ADJUSTED, ORIGINAL),
}
HVT_LFOOTER = (
    f"{AUSTRALIA}Year-ended. Headline Orig. Trimmed mean SA. "
    "Before dashed line: CPI Indicator (trimmed mean Orig). "
)
HVT_JUNCTION_LINE = {"color": "darkgrey", "linestyle": "--", "linewidth": 1}

# Phillips curves
PHILLIPS: dict[str, Request] = {
    "Qrtly Trimmed Mean CPI (SA)": (CPI, APPENDIX, "Trimmed Mean", "S", "", True, False),
    "Households implicit price deflator (SA)": (
        NA,
        NA_DEFLATORS,
        "Households ;  Final consumption expenditure ;",
        "S",
        "Index",
        False,
        True,
    ),
    "Unemployment rate monthly (SA)": (LFS, LFS_TABLE, "Unemployment rate ;  Persons ;", "S", "", False, False),
}
PHILLIPS_FROM = "2021Q1"
TRIMMED_MEAN_SOURCE = "ABS: 6202.0, 6401.0"
PHILLIPS_LFOOTER = f"{AUSTRALIA}Seasonally adjusted. Unemployment rate is quarterly mean. "
TARGET_LINE = 2.5
STYLISED_PERIODS = (  # (first quarter, last quarter or None for the latest, colour, polynomial degree)
    ("2021Q1", None, "brown", 3),
    ("2010Q1", "2019Q4", "blue", 1),
    ("2003Q1", "2008Q4", "orange", 3),
    ("1998Q1", "2002Q4", "skyblue", 1),
)
REGRESSION_POINTS = 50

# nominal GDP per capita
NGDP_FROM = pd.Period("1993Q1", freq="Q")  # the inflation-target era
NGDP_TARGET = 2.5  # CPI midpoint
NGDP_HP_LAMBDA = 25_600
NGDP_FLAT = 4.2  # fixed non-inflationary nominal benchmark (% pa)
NGDP_GFC = pd.Period("2008Q3", freq="Q")  # nominal growth steps down after the GFC
NGDP_PRE, NGDP_POST = 5.25, 3.25  # pre- and post-GFC nominal growth (% pa)

# misery index
MISERY_FROM = pd.Period("1959Q3", freq="Q").asfreq("M", how="start")
STAGFLATION_WINDOW, STAGFLATION_MIN_PERIODS = 120, 12  # months, for the 10-year unemployment minimum
STAGFLATION_INFLATION, STAGFLATION_UR_MULTIPLE, STAGFLATION_MIN_RUN = 5.0, 1.75, 12
MISERY_RECENT = 121  # months

# CPI, rents, wages and household income rebased
REBASE_QUARTERS = (pd.Period("2018Q4", freq="Q"), pd.Period("2020Q4", freq="Q"))


# --- data
@cache
def _read(cat: str, table: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read one table of a catalogue (cached; not for mutation): its data and its own metadata rows."""
    data, meta = ra.read_abs_cat(cat, single_excel_only=table, verbose=False)
    return data[table], meta[meta[mc.table] == table]


@cache
def _indicator() -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """Read the discontinued Monthly CPI Indicator (cached; not for mutation)."""
    return ra.read_abs_cat(INDICATOR, url=INDICATOR_URL)


def _table(release: AbsRelease, cat: str, table: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return one table and its metadata rows, from the CPI release or read from another catalogue."""
    if cat == CPI:
        return release.data[table], release.meta[release.meta[mc.table] == table]
    return _read(cat, table)


def _load(release: AbsRelease, request: Request) -> pd.Series:
    """Return a requested series, trailing gaps trimmed; optionally its published or calculated annual growth."""
    cat, table, did, stype, unit, seek_yr_growth, calc_growth = request
    data, meta = _table(release, cat, table)
    selector = {did: mc.did, STYPES[stype]: mc.stype}
    if unit:
        selector[unit] = mc.unit
    if seek_yr_growth:
        selector |= dict.fromkeys(YEAR_ON_YEAR_TERMS, mc.did)
    _table_name, series_id, _units = ra.find_abs_id(meta, selector, verbose=False)
    series = data[series_id]
    last_valid = series.last_valid_index()
    if last_valid is not None:
        series = series.loc[:last_valid]
    if calc_growth:
        if not isinstance(series.index, pd.PeriodIndex):
            raise TypeError(f"Expected a PeriodIndex for {did!r}")
        periods = {"Q": QUARTERS_PER_YEAR, "M": MONTHS_PER_YEAR}[series.index.freqstr[0]]
        series = series.pct_change(periods=periods) * PERCENT
    return series


def _source(requests: dict[str, Request]) -> str:
    """Return the rfooter naming each catalogue the requests draw on."""
    return f"ABS: {', '.join(sorted({request[0] for request in requests.values()}))}"


def _year_ended(series: pd.Series, periods: int) -> pd.Series:
    """Return year-ended growth."""
    return ((series / series.shift(periods) - 1) * PERCENT).dropna()


def _pair_segments(release: AbsRelease, did: str) -> list[pd.Series]:
    """Return monthly year-ended growth for one analytical series: current CPI, then the indicator."""
    indicator, indicator_meta = _indicator()
    selector = {did: mc.did, "Australia ;": mc.did, "Index Numbers": mc.unit, ORIGINAL: mc.stype, "Month": mc.freq}
    new, old = ra.select([(release.data, release.meta, selector), (indicator, indicator_meta, selector)])
    return [_year_ended(new, MONTHS_PER_YEAR), _year_ended(old, MONTHS_PER_YEAR)]


def _pair_monthly(release: AbsRelease, did: str) -> pd.Series:
    """Return year-ended growth spliced across the two monthly sources."""
    spliced, _report = ra.splice(_pair_segments(release, did), rebase=False)
    return spliced


def _pair_quarterly(did: str) -> pd.Series:
    """Return year-ended growth as published in the final quarterly CPI (Sep quarter 2025)."""
    data, meta = ra.read_abs_cat(CPI, url=FINAL_QUARTERLY_URL, single_excel_only=FINAL_QUARTERLY_TABLE)
    selector = {
        "Percentage Change from Corresponding Quarter of Previous Year": mc.did,
        did: mc.did,
        "Australia ;": mc.did,
        "Percent": mc.unit,
        ORIGINAL: mc.stype,
        "Quarter": mc.freq,
    }
    return ra.select_one(data, meta, selector)


def _pair_long(release: AbsRelease, did: str) -> pd.Series:
    """Return year-ended growth as one monthly line: current CPI, indicator, then the quarterly rates."""
    spliced, _report = ra.splice(
        [*_pair_segments(release, did), _pair_quarterly(did)], target="M", fill="interpolate", rebase=False
    )
    return spliced


def _pair_charts(release: AbsRelease, title: str, concepts: dict[str, str]) -> None:
    """Draw a pair of CPI analytical series: monthly, with the quarterly overlay, and long run."""
    common: dict[str, Any] = {
        "title": f"Australian CPI: {title}",
        "ylabel": "CPI (annual % change)",
        "axhspan": ANNUAL_CPI_TARGET_RANGE,
        "legend": {"loc": "best", "fontsize": "small"},
        "rfooter": PAIR_RFOOTER,
        "y0": True,
    }
    monthly = {label: _pair_monthly(release, did) for label, did in concepts.items()}
    frame = pd.DataFrame(monthly)
    mg.multi_start(
        frame,
        function=mg.line_plot_finalise,
        starts=pair_starts,
        lfooter=f"{PAIR_LFOOTER}{data_to(frame)}",
        **common,
    )
    quarterly = {
        f"{label} (quarterly)": ra.qtly_to_monthly(_pair_quarterly(did)) for label, did in concepts.items()
    }
    mg.multi_start(
        pd.DataFrame(monthly | quarterly),
        function=mg.line_plot_finalise,
        starts=pair_starts,
        color=OVERLAY_COLOURS,
        style=OVERLAY_STYLES,
        tag="with-quarterly",
        lfooter=f"{OVERLAY_LFOOTER}{data_to(frame)}",
        **common,
    )
    long_run = pd.DataFrame({label: _pair_long(release, did) for label, did in concepts.items()})
    mg.line_plot_finalise(
        long_run,
        tag="long-run",
        lfooter=f"{LONG_LFOOTER}{data_to(long_run)}",
        **common,
    )


def _xy_line(frame: pd.DataFrame, label: str, ax: Axes, *, width: float, color: str) -> None:
    """Draw the second column of a frame against its first, as one line."""
    ax.plot(frame[frame.columns[0]], frame[frame.columns[1]], lw=width, color=color, label=label or "_nolegend_")


def _regression(ax: Axes, frame: pd.DataFrame, label: str, *, degree: int, **style: Any) -> None:
    """Draw a polynomial fit of the second column of a frame on its first."""
    x, y = frame[frame.columns[0]], frame[frame.columns[1]]
    model = np.poly1d(np.polyfit(x, y, degree))
    line = np.linspace(x.min(), x.max(), REGRESSION_POINTS)
    ax.plot(line, model(line), label=label or "_nolegend_", **style)


def _phillips_data(release: AbsRelease) -> dict[str, pd.Series]:
    """Return trimmed mean and household deflator annual growth, and the quarterly unemployment rate."""
    return {label: _load(release, request) for label, request in PHILLIPS.items()}


def _consecutive_runs(mask: pd.Series, min_length: int) -> list[tuple[Any, Any]]:
    """Return (start, end) index pairs where the mask is True for at least min_length periods."""
    mask = mask.fillna(False).astype(bool)
    block_id = (mask != mask.shift()).cumsum()
    return [
        (block.index[0], block.index[-1])
        for _, block in mask.groupby(block_id)
        if block.iloc[0] and len(block) >= min_length
    ]


def _modellers_unemployment_rate() -> pd.Series:
    """Return the quarterly unemployment rate from the Modellers' Database: unemployed over labour force."""
    data, meta = _read(MODELLERS, MODELLERS_TABLE)
    _, unemployed_id, _ = ra.find_abs_id(meta, {MODELLERS_TABLE: mc.table, "Total unemployed ;": mc.did})
    _, labour_force_id, _ = ra.find_abs_id(meta, {MODELLERS_TABLE: mc.table, "Total labour force ;": mc.did})
    return (data[unemployed_id] / data[labour_force_id]) * PERCENT


def _key_aggregate(did: str) -> pd.Series:
    """Return one seasonally adjusted key aggregates series, as floats."""
    data, meta = _read(NA, NA_KEY_AGGS)
    _, series_id, _ = ra.find_abs_id(
        meta, {NA_KEY_AGGS: mc.table, did: mc.did, SEASONALLY_ADJUSTED: mc.stype}, verbose=False
    )
    return data[series_id].astype(float)


# --- charts
def long_run_headline(release: AbsRelease) -> None:
    """Headline year-ended inflation since 1949: monthly CPI over the indicator over the quarterly CPI."""
    indicator, indicator_meta = _indicator()
    base = {"Index Numbers ;  All groups CPI ;  Australia ;": mc.did, "Index Numbers": mc.unit, ORIGINAL: mc.stype}
    monthly, indicator_monthly, quarterly = ra.select(
        [
            (release.data, release.meta, base | {"Month": mc.freq}),
            (indicator, indicator_meta, base | {"Month": mc.freq}),
            (release.data, release.meta, base | {"Quarter": mc.freq}),
        ]
    )
    spliced, _report = ra.splice(
        [
            _year_ended(monthly, MONTHS_PER_YEAR),
            _year_ended(indicator_monthly, MONTHS_PER_YEAR),
            _year_ended(quarterly, QUARTERS_PER_YEAR),
        ],
        rebase=False,
        name="Headline CPI Y/Y (spliced)",
    )
    mg.line_plot_finalise(
        spliced,
        title="Australian Headline CPI: Year-ended Inflation (spliced, 1949 to current)",
        ylabel="Annual % change",
        rfooter=PAIR_RFOOTER,
        lfooter=f"{AUSTRALIA}Original series. Monthly (new CPI + indicator) spliced over quarterly. "
        f"{data_to(spliced)}",
        y0=True,
    )


def measures(release: AbsRelease) -> None:
    """Chart the CPI measures beside the PPI, WPI and price deflators: annual growth from five starts."""
    combined = {name: to_monthly(_load(release, request)) for name, request in MULTI_MEASURE.items()}
    combined = {LONG_HEADLINE: ra.qtly_to_monthly(long_headline(release))} | combined
    frame = pd.DataFrame(combined)
    mg.multi_start(
        frame,
        function=mg.line_plot_finalise,
        starts=list(MULTI_MEASURE_STARTS),
        title="Australian Inflation Measures",
        ylabel="Inflation (annual % change)",
        axhspan=ANNUAL_CPI_TARGET_RANGE,
        legend={"loc": "best", "ncol": 3, "fontsize": "xx-small"},
        lfooter=f"{MEASURES_LFOOTER}{data_to(frame)}",
        rfooter=_source(MULTI_MEASURE),
        color=list(TEN_COLOURS),
        y0=True,
    )


def measure_growth(release: AbsRelease) -> None:
    """Quarterly and annual growth in the PPI, WPI and the household and GNE deflators."""
    for key, request in MEASURE_GROWTH.items():
        series = _load(release, request)
        mg.growth_plot_finalise(
            data=mg.calc_growth(series),
            plot_from=GROWTH_FROM,
            title=f"Growth: {key}",
            ylabel="Per cent",
            lfooter=f"{AUSTRALIA}{SERIES_TYPE_NOTES[STYPES[request[3]]]} {data_to(series)}",
            axhline=QUARTERLY_CPI_TARGET,
            axhspan=ANNUAL_CPI_TARGET_RANGE,
            rfooter=f"ABS: {request[0]}",
        )


def goods_services(release: AbsRelease) -> None:
    """Goods against services inflation: monthly, with the quarterly series, and long run."""
    _pair_charts(release, "Goods versus Services", GOODS_SERVICES)


def tradeables(release: AbsRelease) -> None:
    """Tradeables against non-tradeables inflation: monthly, with the quarterly series, and long run."""
    _pair_charts(release, "Tradeables versus Non-tradeables", TRADEABLES)


def headline_vs_trimmed(release: AbsRelease) -> None:
    """Monthly headline and trimmed mean year-ended inflation, the indicator spliced beneath the CPI."""
    indicator, indicator_meta = _indicator()
    segments = {}
    for label, (did, cpi_stype, indicator_stype) in HVT_MEASURES.items():
        base = {HVT_YOY_DID: mc.did, did: mc.did, "Percent": mc.unit, "Month": mc.freq}
        segments[label] = ra.select(
            [
                (release.data, release.meta, base | {cpi_stype: mc.stype}),
                (indicator, indicator_meta, base | {indicator_stype: mc.stype}),
            ]
        )
        if any(s.dropna().empty for s in segments[label]):
            raise ValueError(f"Empty year-ended growth segment for {did!r}")
    frame = pd.DataFrame({label: ra.splice(segs, rebase=False)[0] for label, segs in segments.items()}).dropna()
    junction = max(segs[0].dropna().index[0] for segs in segments.values())  # where the CPI takes over
    mg.line_plot_finalise(
        frame,
        title="Australian Monthly CPI: Headline v Trimmed Mean",
        ylabel="CPI (annual % change)",
        axhspan=ANNUAL_CPI_TARGET_RANGE,
        axvline=HVT_JUNCTION_LINE | {"x": junction},
        legend={"loc": "best", "fontsize": "small"},
        lfooter=f"{HVT_LFOOTER}{data_to(frame)}",
        rfooter=PAIR_RFOOTER,
        y0=True,
    )


def phillips_curves(release: AbsRelease) -> None:
    """Phillips curves since 2021 for trimmed mean and household deflator inflation; stylised curves by period."""
    data = _phillips_data(release)
    unemployment = ra.monthly_to_qtly(data["Unemployment rate monthly (SA)"])
    trimmed_mean = data["Qrtly Trimmed Mean CPI (SA)"]
    common: dict[str, Any] = {
        "ylabel": "Unemployment Rate (%)",
        "legend": True,
    }

    for label, inflation, source in (
        ("Trimmed Mean CPI", trimmed_mean, TRIMMED_MEAN_SOURCE),
        ("Household Expenditure IPD", data["Households implicit price deflator (SA)"], "ABS: 5206.0, 6202.0"),
    ):
        frame = pd.DataFrame({label: inflation, "_Unemployment Rate": unemployment})
        latest_rate = frame.iloc[-1, 1]
        if not isinstance(latest_rate, float):
            raise TypeError(f"Expected a float unemployment rate, got {type(latest_rate).__name__}")
        last = latest_rate if frame.iloc[-1].isna().any() else 0.0
        last_date = frame.index[-1]
        frame = frame.loc[lambda x: x.index >= PHILLIPS_FROM].dropna()
        _fig, ax = plt.subplots()
        _xy_line(frame, "Phillips curve", ax, width=2, color="royalblue")
        for n in (0, -1):  # label the start and end
            ax.text(
                frame[frame.columns[0]].iloc[n],
                frame[frame.columns[1]].iloc[n],
                f"{frame.index[n]} ",
                fontsize="x-small",
                ha="right",
            )
        _regression(ax, frame, "Stylised Phillips curve", degree=3, color="darkred", linestyle="--", lw=0.75)
        ax.axvline(TARGET_LINE, color="darkblue", linestyle=":", lw=0.75, label="2.5% Inflation target")
        if last > 0.0:
            ax.axhline(last, color="darkgreen", linestyle="-.", lw=0.75, label=f"Unemployment rate {last_date}")
        mg.finalise_plot(
            ax,
            title=f"Phillips Curve: {label} vs Unemployment",
            xlabel=f"{label} Annual Growth Rate (%)",
            lfooter=f"{PHILLIPS_LFOOTER}{APPENDIX_NOTE}{data_to(frame)}",
            rfooter=source,
            **common,
        )

    both = pd.DataFrame({"Trimmed Mean CPI": trimmed_mean, "Unemployment Rate": unemployment}).dropna()
    _fig, ax = plt.subplots()
    for first, final, colour, degree in STYLISED_PERIODS:
        periods = pd.period_range(
            pd.Period(first, freq="Q"), trimmed_mean.index[-1] if final is None else pd.Period(final, freq="Q")
        )
        frame = pd.DataFrame({"Trimmed Mean CPI": trimmed_mean, "Unemployment Rate": unemployment})
        frame = frame.loc[periods[0] : periods[-1]].dropna()
        _xy_line(frame, "", ax, width=0.5, color=colour)
        _regression(ax, frame, f"{periods[0]}-{periods[-1]}", degree=degree, color=colour, linestyle="-", lw=3.0)
    mg.finalise_plot(
        ax,
        title="Stylised Phillips Curves: Trimmed Mean CPI vs Unemployment",
        xlabel="Trimmed Mean CPI Annual Growth Rate (%)",
        axvline={
            "x": TARGET_LINE,
            "color": "darkblue",
            "linestyle": ":",
            "lw": 0.75,
            "label": "2.5% Inflation target",
        },
        lfooter=f"{PHILLIPS_LFOOTER}{APPENDIX_NOTE}{data_to(both)}",
        rfooter=TRIMMED_MEAN_SOURCE,
        **common,
    )


def nominal_gdp(_release: AbsRelease) -> None:
    """Nominal GDP per capita: growth against trend benchmarks, and its log level against projected paths."""
    ngdp_pc = _key_aggregate("GDP per capita: Current prices ;")
    rgdp_pc = _key_aggregate("GDP per capita: Chain volume measures ;")

    # growth against three non-inflationary benchmarks
    actual = (ngdp_pc.pct_change(QUARTERS_PER_YEAR) * PERCENT).rename("Nominal GDP per capita growth (YoY)")
    real_growth = (rgdp_pc.pct_change(QUARTERS_PER_YEAR) * PERCENT).dropna()
    real_growth = real_growth[real_growth.index >= NGDP_FROM]
    flat = pd.Series(NGDP_FLAT, index=real_growth.index, name=f"Flat trend ({NGDP_FLAT:.1f}%)")
    x = np.arange(len(real_growth))
    a, b = np.polyfit(x, real_growth.to_numpy(), 1)
    sloping = pd.Series((b + a * x) + NGDP_TARGET, index=real_growth.index, name="Sloping (regression)")
    _, trend_log = hpfilter(np.log(rgdp_pc.dropna()), lamb=NGDP_HP_LAMBDA)
    hp = (trend_log.diff(QUARTERS_PER_YEAR) * PERCENT + NGDP_TARGET).rename(
        f"HP trend (log level, λ={NGDP_HP_LAMBDA:,})"
    )
    frame = pd.DataFrame({actual.name: actual, flat.name: flat, sloping.name: sloping, hp.name: hp})
    mg.line_plot_finalise(
        frame[frame.index >= NGDP_FROM],
        width=[2.0, 1.0, 1.0, 1.6],
        style=["-", ":", "--", "-"],
        title="Nominal GDP per Capita Growth vs Trend Benchmarks",
        ylabel="Annual % change",
        legend={"loc": "upper right", "fontsize": "xx-small"},
        rfooter="ABS: 5206.0",
        lfooter=f"{AUSTRALIA}Seasonally adjusted. Benchmark = trend real GDP/capita + {NGDP_TARGET}% target. "
        f"{data_to(actual)}",
        y0=True,
        annotate=[False, True, True, True],
        rounding=1,
    )

    # log level against a flat path and a stepped pre/post-GFC path, both anchored in 1993Q1
    log_ngdp = np.log(ngdp_pc.dropna())
    log_ngdp = log_ngdp[log_ngdp.index >= NGDP_FROM]
    index = log_ngdp.index
    quarters = np.arange(len(index))
    flat_path = pd.Series(log_ngdp.iloc[0] + quarters * (np.log1p(NGDP_FLAT / PERCENT) / 4.0), index=index)
    step = np.where(index <= NGDP_GFC, np.log1p(NGDP_PRE / PERCENT) / 4.0, np.log1p(NGDP_POST / PERCENT) / 4.0)
    step[0] = 0.0  # the anchor has no increment
    stepped_path = pd.Series(log_ngdp.iloc[0] + np.cumsum(step), index=index)
    mg.line_plot_finalise(
        pd.DataFrame(
            {
                "log Nominal GDP per capita": log_ngdp,
                f"Non-inflationary path ({NGDP_FLAT:.1f}% pa)": flat_path,
                f"{NGDP_PRE:g}/{NGDP_POST:g} path ({NGDP_PRE:g}% to GFC, then {NGDP_POST:g}%)": stepped_path,
            }
        ),
        width=[2.0, 1.2, 1.4],
        style=["-", "--", "-."],
        title="Nominal GDP per Capita: Log Level vs Projected Paths",
        ylabel="log($ per capita)",
        legend={"loc": "lower right", "fontsize": "x-small"},
        rfooter="ABS: 5206.0",
        lfooter=f"{AUSTRALIA}Seasonally adjusted. Paths anchored at 1993Q1. {data_to(log_ngdp)}",
    )


def misery_index(release: AbsRelease) -> None:
    """Unemployment plus CPI inflation since 1959, with periods of stagflation shaded."""
    unemployment = _load(release, PHILLIPS["Unemployment rate monthly (SA)"]).combine_first(
        ra.qtly_to_monthly(_modellers_unemployment_rate())
    )
    frame = pd.DataFrame(
        {"Unemployment rate": unemployment, "CPI inflation (annual)": ra.qtly_to_monthly(long_headline(release))}
    )
    frame["Misery index"] = frame["Unemployment rate"] + frame["CPI inflation (annual)"]
    frame = frame.loc[frame.index >= MISERY_FROM]

    # stagflation: inflation at or above the threshold and unemployment well above its 10-year minimum
    ur_min = (
        frame["Unemployment rate"].rolling(window=STAGFLATION_WINDOW, min_periods=STAGFLATION_MIN_PERIODS).min()
    )
    stagflation = (frame["CPI inflation (annual)"] >= STAGFLATION_INFLATION) & (
        frame["Unemployment rate"] >= STAGFLATION_UR_MULTIPLE * ur_min
    )
    shade = [
        {
            "xmin": start,
            "xmax": end,
            "color": "goldenrod",
            "alpha": 0.25,
            "zorder": 0,
            "label": "Periods of stagflation" if i == 0 else "_nolegend_",
        }
        for i, (start, end) in enumerate(_consecutive_runs(stagflation, STAGFLATION_MIN_RUN))
    ]
    common: dict[str, Any] = {
        "data": frame,
        "title": "Australian Misery Index: Unemployment + CPI Inflation",
        "ylabel": "Per cent",
        "width": [1.25, 1.25, 2.0],
        "legend": {"loc": "best", "fontsize": "small"},
        "lfooter": f"{AUSTRALIA}UR seas adj, CPI orig. "
        f"Stagflation: inflation ≥ 5% & UR ≥ 1.75× 10-yr min, 12+ mo. {data_to(frame)}",
        "rfooter": "ABS: 1364.0.15.003, 6202.0, 6401.0",
        "y0": True,
    }
    mg.line_plot_finalise(plot_from=0, tag="0", axvspan=shade, **common)
    recent_from = frame.index[-MISERY_RECENT]
    recent_shade = [s for s in shade if s["xmax"] >= recent_from]
    mg.line_plot_finalise(plot_from=-MISERY_RECENT, tag="1", axvspan=recent_shade, **common)


def living_costs_rebased(release: AbsRelease) -> None:
    """CPI, rents, WPI, AWE and household disposable income per hour, rebased to 2018Q4 and to 2020Q4."""
    raw: dict[str, pd.Series] = {}
    appendix, appendix_meta = _table(release, CPI, APPENDIX)
    for label, terms in {
        "Headline CPI (SA)": ("Index Numbers", "All groups CPI, seasonally adjusted"),
        "Rents (SA)": ("Index Numbers", "Rents ;  Australia"),
    }.items():
        search = {APPENDIX: mc.table, SEASONALLY_ADJUSTED: mc.stype} | dict.fromkeys(terms, mc.did)
        _, series_id, _ = ra.find_abs_id(appendix_meta, search)
        raw[label] = appendix[series_id]

    wpi, wpi_meta = _read(WPI, WPI_TABLE)
    _, wpi_id, _ = ra.find_abs_id(
        wpi_meta,
        {
            WPI_TABLE: mc.table,
            "Total hourly rates of pay excluding bonuses ;  Australia ;  Private and Public": mc.did,
            SEASONALLY_ADJUSTED: mc.stype,
        },
    )
    raw["WPI (SA)"] = wpi[wpi_id]

    awe, awe_meta = _read(AWE, AWE_TABLE)
    _, awe_id, _ = ra.find_abs_id(
        awe_meta,
        {
            AWE_TABLE: mc.table,
            "Persons; Full Time; Adult; Ordinary time earnings": mc.did,
            SEASONALLY_ADJUSTED: mc.stype,
        },
    )
    earnings = awe[awe_id].dropna()
    if not isinstance(earnings.index, pd.PeriodIndex):
        raise TypeError("Expected a PeriodIndex for average weekly earnings")
    earnings.index = earnings.index.to_timestamp(how="end").to_period("Q")  # Q-NOV to Q-DEC
    raw["AWE (SA)"] = earnings

    income, income_meta = _read(NA, NA_HOUSEHOLD_INCOME)
    _, income_id, _ = ra.find_abs_id(
        income_meta,
        {NA_HOUSEHOLD_INCOME: mc.table, "GROSS DISPOSABLE INCOME": mc.did, SEASONALLY_ADJUSTED: mc.stype},
    )
    key_aggs, key_meta = _read(NA, NA_KEY_AGGS)
    _, hours_id, _ = ra.find_abs_id(
        key_meta, {NA_KEY_AGGS: mc.table, "Hours worked: Index ;": mc.did, SEASONALLY_ADJUSTED: mc.stype}
    )
    raw["Gross disposable household income per hour worked (SA)"] = (
        income[income_id].dropna() / key_aggs[hours_id].dropna()
    ).dropna()

    for base in REBASE_QUARTERS:
        rebased = {label: s / s[s.index == base].iloc[0] * PERCENT for label, s in raw.items()}
        frame = pd.DataFrame(rebased).dropna(how="all")
        mg.line_plot_finalise(
            frame,
            plot_from=base,
            title=f"CPI, Rents, Wages & Household Income: Rebased to {base} = 100",
            ylabel=f"Index ({base} = 100)",
            annotate=True,
            rounding=1,
            axhline={"y": 100, "color": "black", "linestyle": "--", "linewidth": 0.75},
            lfooter=f"{AUSTRALIA}Seasonally adjusted. {APPENDIX_NOTE}AWE is biannual. {data_to(frame)}",
            rfooter="ABS: 5206.0, 6302.0, 6345.0, 6401.0",
        )


# --- table of contents, in run order
CHARTS = (
    (long_run_headline, ()),
    (measures, ()),
    (measure_growth, ()),
    (goods_services, ()),
    (tradeables, ()),
    (headline_vs_trimmed, ()),
    (phillips_curves, ()),
    (nominal_gdp, ()),
    (misery_index, ()),
    (living_costs_rebased, ()),
)
