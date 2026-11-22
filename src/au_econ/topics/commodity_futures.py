"""Commodity futures and indices: front-month prices for metals, grains and softs, and broad commodity indices.

Futures prices are Yahoo Finance front-month closes. Yahoo no longer carries the Bloomberg
Commodity Index (^BCOM), so the broad index charts use two stand-ins: the iPath Bloomberg
Commodity Index Total Return ETN (DJP), a traded note tracking the index, for the recent
daily chart; and the IMF's monthly all-commodities price index, through FRED, for the
long history and the comparison with Australian inflation.
"""

# --- dependencies
from dataclasses import dataclass

import mgplot as mg
import numpy as np
import pandas as pd
import readabs as ra
from mgplot.utilities import get_color_list

from au_econ.charting.daily_prices import (
    SOURCE_YAHOO,
    fetch_closes,
    frame_chart,
    last_day,
    recent_starts,
    single_charts,
    summarise,
)
from au_econ.charting.targets import ANNUAL_CPI_TARGET_RANGE
from au_econ.charting.turning_points import turning_points_plot
from au_econ.series.prices import get_cpi, get_monthly_cpi
from au_econ.sources import fred

# --- module contract
RELEASE = ("yahoo",)
TOPICS = ("commodities",)
TITLE = "Commodity Futures"

# --- constants
RECENT_YEARS = 2  # each Yahoo chart is drawn for its full history, then this many years
METALS = [
    ("GC=F", "Gold", "USD per troy ounce"),
    ("SI=F", "Silver", "USD per troy ounce"),
    ("PL=F", "Platinum", "USD per troy ounce"),
    ("PA=F", "Palladium", "USD per troy ounce"),
    ("HG=F", "Copper", "USD per pound"),
    ("TIO=F", "Iron Ore", "USD per tonne"),
]
GRAINS = {"ZW=F": "Wheat", "ZC=F": "Corn"}
SOFTS = [
    ("ZS=F", "Soybeans", "USD cents per bushel"),
    ("KC=F", "Coffee", "USD cents per pound"),
    ("SB=F", "Sugar", "USD cents per pound"),
    ("CC=F", "Cocoa", "USD per tonne"),
    ("CT=F", "Cotton", "USD cents per pound"),
    ("ZR=F", "Rice", "USD per hundredweight"),
    ("UFV=F", "Urea", "USD per tonne"),
]

# broad commodity indices
BCOM_ETN = "DJP"  # iPath Bloomberg Commodity Index Total Return ETN
IMF_ALL_COMMODITIES = "PALLFNFINDEXM"  # FRED: IMF global price index of all commodities, monthly, 2016 = 100
IMF_START = "1992-01-01"
SOURCE_IMF = "IMF: PCPS (via FRED)"  # IMF Primary Commodity Prices
MONTHS_IN_YEAR, QUARTERS_IN_YEAR = 12, 4
PERCENT = 100
COMMODITY_SCALE = 10  # divides commodity price growth onto the CPI scale (it swings about 10-14 times as much)
CPI_SHADE_ABOVE = 3.0  # per cent: the top of the RBA's target band
CPI_SHADE = {"color": "goldenrod", "alpha": 0.18}
COMMODITY_LABEL = f"Commodity prices YoY (IMF, monthly, divided by {COMMODITY_SCALE} for scale)"
CPI_LABEL = "AU CPI YoY (quarterly, SA)"

# lagged correlation of commodity index growth with CPI growth
MAX_LEAD_MONTHS = 12
LAG_PERIODS = {  # line label: (first month, last month); None is open-ended
    "Full sample": (None, None),
    "To 2019": (None, "2019-12"),
    "2020 on": ("2020-01", None),
}
DIFFERENCED = r"$\Delta$"  # marks the monthly change in a YoY rate
LINE_STYLES = {False: "-", True: "--"}  # by differenced: YoY rates solid, their monthly changes dashed
CORRELATION_LIMITS = (-1.0, 1.0)  # the full range of a correlation; leaves the legend clear of the lines

# CPI scenario: commodity prices held at the latest close, through the same-month first-difference model
SCENARIO_END = "2027-12"
BACKTEST_FROM = "2013-01"  # five years of training data before the first backtest forecast
FORECAST_HISTORY_MONTHS = 36  # CPI history shown before the scenario
FORECAST_BANDS = {  # label: (lower, upper) quantiles of backtest errors, and the band's opacity
    "95% band": ((0.025, 0.975), 0.15),
    "80% band": ((0.10, 0.90), 0.3),
}
BREAKDOWN_LINE = {  # marks the first month the model's backtest error is no smaller than no-change's
    "linestyle": "--",
    "linewidth": 0.75,
    "color": "#555555",
    "text": "No better than no-change from here",
}


@dataclass(frozen=True)
class FuturesData:
    """Daily closes by Yahoo ticker; the monthly IMF commodity index; the quarterly and monthly SA CPI indexes."""

    closes: dict[str, pd.Series]
    imf_index: pd.Series
    cpi: pd.Series
    monthly_cpi: pd.Series


# --- data
def fetch() -> FuturesData:
    """Fetch every futures close and the commodity ETN (their full histories), the IMF index and CPI."""
    tickers = [ticker for ticker, _, _ in METALS] + list(GRAINS) + [ticker for ticker, _, _ in SOFTS] + [BCOM_ETN]
    imf = fred.get_series(IMF_ALL_COMMODITIES, IMF_START)
    imf.index = pd.PeriodIndex(imf.index, freq="M")
    cpi, _, _ = get_cpi("headline_sa")
    monthly_cpi, _, _ = get_monthly_cpi()
    return FuturesData(
        closes=fetch_closes(tickers, None), imf_index=imf.dropna(), cpi=cpi, monthly_cpi=monthly_cpi
    )


# --- helpers
def _monthly_closes(etn: pd.Series) -> pd.Series:
    """Monthly average of the commodity ETN's daily closes."""
    etn_index = etn.index
    if not isinstance(etn_index, pd.PeriodIndex):
        raise TypeError(f"{BCOM_ETN}: expected a daily PeriodIndex")
    return etn.groupby(etn_index.asfreq("M")).mean()


def _yoy_pair(etn: pd.Series, monthly_cpi: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Year-on-year growth of the commodity ETN (monthly average of daily closes) and of monthly CPI."""
    commodity_yoy = ra.percent_change(_monthly_closes(etn), MONTHS_IN_YEAR).dropna()
    cpi_yoy = ra.percent_change(monthly_cpi, MONTHS_IN_YEAR).dropna()
    return commodity_yoy, cpi_yoy


def _difference_fit(commodity_change: pd.Series, cpi_change: pd.Series, through: pd.Period) -> tuple[float, float]:
    """Fit monthly change in CPI growth = a + b * same-month change in commodity growth, up to through."""
    pair = pd.concat([commodity_change, cpi_change], axis=1).dropna().loc[:through]
    slope, intercept = np.polyfit(pair.iloc[:, 0], pair.iloc[:, 1], 1)
    return float(intercept), float(slope)


def _difference_path(fit: tuple[float, float], start: float, commodity_change: pd.Series) -> pd.Series:
    """CPI growth from start, adding the fitted change for each month of commodity_change in turn."""
    intercept, slope = fit
    return start + (intercept + slope * commodity_change).cumsum()


def _scenario_backtest(
    commodity_change: pd.Series, cpi_change: pd.Series, cpi_yoy: pd.Series, horizons: int
) -> tuple[dict[int, list[float]], dict[int, list[float]]]:
    """Backtest errors by horizon (1 to horizons) of the first-difference model, and of no-change.

    From each origin month from BACKTEST_FROM, the model is fitted on data to that month and run
    forward on the commodity changes that happened.
    """
    errors: dict[int, list[float]] = {horizon: [] for horizon in range(1, horizons + 1)}
    no_change: dict[int, list[float]] = {horizon: [] for horizon in errors}
    last = cpi_yoy.index[-1]
    if not isinstance(last, pd.Period):
        raise TypeError("Expected a monthly PeriodIndex")
    origins = cpi_yoy.loc[pd.Period(BACKTEST_FROM, freq="M") : last - 1]
    for origin, start in origins.items():
        if not isinstance(origin, pd.Period):
            raise TypeError("Expected a monthly PeriodIndex")
        run = _difference_path(
            _difference_fit(commodity_change, cpi_change, origin), start, commodity_change.loc[origin + 1 : last]
        )
        outcomes = cpi_yoy.reindex(run.index)
        for horizon, (error, still) in enumerate(zip(outcomes - run, outcomes - start, strict=True), start=1):
            if horizon in errors:
                errors[horizon].append(error)
                no_change[horizon].append(still)
    return errors, no_change


def _aligned(
    commodity_yoy: pd.Series, cpi_yoy: pd.Series, lead: int, first: str | None, last: str | None
) -> pd.DataFrame:
    """Commodity growth led by lead months (first column) beside CPI growth, from first to last month."""
    return pd.concat([commodity_yoy.shift(lead), cpi_yoy], axis=1).dropna().loc[first:last]


# --- charts
def metals(data: FuturesData) -> None:
    """Precious and base metals, and iron ore: one chart each."""
    single_charts(data.closes, METALS, recent_years=RECENT_YEARS, turning_points=True)


def grains(data: FuturesData) -> None:
    """Wheat and corn on one chart."""
    frame = pd.DataFrame({label: data.closes[ticker] for ticker, label in GRAINS.items()}).dropna()
    summarise(frame, "Grains")
    frame_chart(
        frame,
        title="Grain Futures: Wheat and Corn",
        ylabel="USD cents per bushel",
        lfooter=f"CBOT front-month futures. Data to {last_day(frame)}.",
        recent_years=RECENT_YEARS,
    )


def softs(data: FuturesData) -> None:
    """Soybeans, softs, rice and urea: one chart each."""
    single_charts(data.closes, SOFTS, recent_years=RECENT_YEARS, turning_points=True)


def commodity_index(data: FuturesData) -> None:
    """Chart the Bloomberg Commodity Index, through the traded note that tracks it (DJP)."""
    if BCOM_ETN not in data.closes:
        print(f"{BCOM_ETN}: no data, skipping")
        return
    etn = data.closes[BCOM_ETN]
    mg.multi_start(
        etn,
        function=turning_points_plot,
        starts=recent_starts(etn, RECENT_YEARS),
        title="Bloomberg Commodity Index ETN (DJP)",
        ylabel="USD per note",
        xlabel=None,
        lfooter=(
            "Daily close of the iPath BCOM Total Return ETN: the index plus collateral interest, "
            f"less fees. Data to {last_day(etn)}."
        ),
        rfooter=SOURCE_YAHOO,
    )


def commodity_index_history(data: FuturesData) -> None:
    """Chart the IMF all-commodities price index since 1992."""
    last = data.imf_index.dropna().index[-1]
    if not isinstance(last, pd.Period):
        raise TypeError("Expected a PeriodIndex")
    mg.line_plot_finalise(
        data.imf_index.rename("IMF all commodities"),
        title="Global Commodity Prices: Since 1992",
        ylabel="Index (2016 = 100)",
        xlabel=None,
        annotate=True,
        lfooter=f"IMF global price index of all commodities, monthly average. Data to {last.strftime('%b %Y')}.",
        rfooter=SOURCE_IMF,
    )


def commodities_vs_cpi(data: FuturesData) -> None:
    """Commodity price growth (scaled) against Australian CPI growth, shading CPI above 3 per cent."""
    commodity_yoy = ra.percent_change(data.imf_index, MONTHS_IN_YEAR)
    commodity_yoy = commodity_yoy.dropna() / COMMODITY_SCALE
    cpi_yoy = ra.percent_change(data.cpi, QUARTERS_IN_YEAR).dropna()
    cpi_yoy.index = pd.PeriodIndex(cpi_yoy.index, freq="Q")
    cpi_monthly = pd.Series(cpi_yoy.to_numpy(), index=cpi_yoy.index.asfreq("M", how="E"), name=CPI_LABEL)
    start = commodity_yoy.index[0]
    frame = pd.DataFrame({COMMODITY_LABEL: commodity_yoy, CPI_LABEL: cpi_monthly})
    frame = frame[frame.index >= start].dropna(how="all")
    # the (first, last) quarters of each unbroken run with CPI growth above the threshold
    runs: list[tuple[pd.Period, pd.Period]] = []
    run_start: pd.Period | None = None
    previous: pd.Period | None = None
    for quarter, value in cpi_yoy[cpi_yoy.index.asfreq("M", how="E") >= start].items():
        if not isinstance(quarter, pd.Period):
            raise TypeError("Expected a PeriodIndex")
        if value > CPI_SHADE_ABOVE and run_start is None:
            run_start = quarter
        elif value <= CPI_SHADE_ABOVE and run_start is not None and previous is not None:
            runs.append((run_start, previous))
            run_start = None
        previous = quarter
    if run_start is not None and previous is not None:
        runs.append((run_start, previous))
    spans = [
        {"xmin": first.asfreq("M", how="start"), "xmax": last.asfreq("M", how="end"), **CPI_SHADE}
        for first, last in runs
    ]
    mg.line_plot_finalise(
        frame,
        title="Commodity Prices vs Australian CPI: Year-on-Year",
        ylabel="Per cent",
        xlabel=None,
        legend={"loc": "upper left", "fontsize": "x-small"},
        annotate=True,
        rounding=1,
        dropna=True,
        y0=True,
        axvspan=spans,
        lfooter=f"CPI plotted at quarter-end months. Shaded: CPI YoY above {CPI_SHADE_ABOVE:.0f}%.",
        rfooter=f"{SOURCE_IMF}; ABS: 6401.0",
    )


def commodity_cpi_lags(data: FuturesData) -> None:
    """Chart the correlation of BCOM growth, led 0 to 12 months, with Australian CPI growth."""
    if BCOM_ETN not in data.closes:
        print(f"{BCOM_ETN}: no data, skipping")
        return
    commodity_yoy, cpi_yoy = _yoy_pair(data.closes[BCOM_ETN], data.monthly_cpi)
    overlap = pd.concat([commodity_yoy, cpi_yoy], axis=1).dropna().index
    print(f"{BCOM_ETN} vs CPI lagged correlations, {overlap[0]} to {overlap[-1]}:")
    # one line per period, for the YoY rates and for their monthly changes; each legend label is
    # the least-squares fit of CPI on commodities at that line's peak lead
    columns: dict[str, pd.Series] = {}
    colors: list[str] = []
    styles: list[str] = []
    for differenced in (False, True):
        mark = DIFFERENCED if differenced else ""
        commodity = commodity_yoy.diff().dropna() if differenced else commodity_yoy
        cpi = cpi_yoy.diff().dropna() if differenced else cpi_yoy
        period_colors = get_color_list(len(LAG_PERIODS))
        for (label, (first, last)), color in zip(LAG_PERIODS.items(), period_colors, strict=True):
            correlation = pd.Series(
                [
                    _aligned(commodity, cpi, lead, first, last).corr().iloc[0, 1]
                    for lead in range(MAX_LEAD_MONTHS + 1)
                ]
            )
            peak = correlation.idxmax()
            if not isinstance(peak, (int, np.integer)):
                raise TypeError(f"{label}: expected an integer lead, got {peak!r}")
            lead = int(peak)
            pair = _aligned(commodity, cpi, lead, first, last)
            slope, intercept = np.polyfit(pair.iloc[:, 0], pair.iloc[:, 1], 1)
            name = (
                f"{label}: {mark}CPI = {intercept:.2f} + {slope:.3f} {mark}BCOM(t-{lead}), "
                f"$R^2$ {correlation.max() ** 2:.2f}, n={len(pair)}"
            )
            print(name, correlation.round(2).tolist())
            columns[name] = correlation
            colors.append(color)
            styles.append(LINE_STYLES[differenced])
    correlations = pd.DataFrame(columns)
    mg.line_plot_finalise(
        correlations,
        title="Bloomberg Commodities Leading Australian CPI",
        ylabel="Correlation",
        xlabel="Months by which commodity growth leads CPI",
        color=colors,
        style=styles,
        legend={"loc": "lower left", "fontsize": "x-small"},
        ylim=CORRELATION_LIMITS,
        annotate=True,
        rounding=2,
        y0=True,
        lfooter=(
            f"Australia. Seasonally adjusted. YoY growth. {DIFFERENCED}: its monthly change. "
            f"BCOM via {BCOM_ETN}; CPI interp. pre-2017. "
            f"{overlap[0].strftime('%b %Y')} to {overlap[-1].strftime('%b %Y')}."
        ),
        rfooter=f"ABS: 6401.0, 6484.0; {SOURCE_YAHOO}",
    )


def cpi_scenario(data: FuturesData) -> None:
    """Chart CPI growth to SCENARIO_END if commodity prices hold at the latest close.

    The path adds up the same-month first-difference model: the monthly change in CPI growth
    on the monthly change in commodity growth. Its bands are quantiles of backtest errors from
    refitting at every month from BACKTEST_FROM and running forward on the commodity changes
    that happened: the model's error given the commodity path, not uncertainty about the path.
    """
    if BCOM_ETN not in data.closes:
        print(f"{BCOM_ETN}: no data, skipping")
        return
    etn = data.closes[BCOM_ETN]
    monthly = _monthly_closes(etn)
    end = pd.Period(SCENARIO_END, freq="M")
    latest_close = float(etn.iloc[-1])
    held = pd.Series(latest_close, index=pd.period_range(monthly.index[-1], end, freq="M"))
    commodity_yoy = ra.percent_change(pd.concat([monthly.iloc[:-1], held]), MONTHS_IN_YEAR).dropna()
    commodity_change = commodity_yoy.diff().dropna()
    cpi_yoy = ra.percent_change(data.monthly_cpi, MONTHS_IN_YEAR).dropna()
    cpi_change = cpi_yoy.diff().dropna()
    last = cpi_yoy.index[-1]
    if not isinstance(last, pd.Period):
        raise TypeError("Expected a monthly PeriodIndex")
    actual = float(cpi_yoy.iloc[-1])
    fit = _difference_fit(commodity_change, cpi_change, last)
    path = _difference_path(fit, actual, commodity_change.loc[last + 1 : end])

    errors, no_change = _scenario_backtest(commodity_change, cpi_change, cpi_yoy, len(path))

    print(f"CPI scenario: {BCOM_ETN} held at {latest_close:.2f} (close of {etn.index[-1]}) from {held.index[0]}")
    print(f"  fit: change in CPI YoY = {fit[0]:.3f} + {fit[1]:.3f} x change in BCOM YoY")
    bands: dict[str, pd.DataFrame] = {}
    for label, ((lower, upper), _) in FORECAST_BANDS.items():
        offsets = pd.DataFrame(
            {
                "lower": [float(pd.Series(errors[h]).quantile(lower)) for h in errors],
                "upper": [float(pd.Series(errors[h]).quantile(upper)) for h in errors],
            },
            index=path.index,
        )
        start_row = pd.DataFrame({"lower": [actual], "upper": [actual]}, index=pd.PeriodIndex([last], freq="M"))
        bands[label] = pd.concat([start_row, offsets.add(path, axis=0)])
    breakdown: pd.Period | None = None
    for horizon, (month, value) in enumerate(path.items(), start=1):
        model_rmse = np.sqrt(np.mean(np.square(errors[horizon])))
        still_rmse = np.sqrt(np.mean(np.square(no_change[horizon])))
        if breakdown is None and model_rmse >= still_rmse and isinstance(month, pd.Period):
            breakdown = month
        band = bands["80% band"].iloc[horizon]
        print(
            f"  {month}: BCOM YoY {commodity_yoy.loc[month:month].iloc[0]:6.1f}  CPI {value:.2f}"
            f"  80% {band['lower']:.2f} to {band['upper']:.2f}"
            f"  RMSE {model_rmse:.2f} vs no-change {still_rmse:.2f}, n={len(errors[horizon])}"
        )

    # the summed monthly changes reduce to: CPI now + drift per month + slope x (BCOM growth - BCOM growth now)
    times = "\N{MULTIPLICATION SIGN}"
    fitted_from = pd.concat([commodity_change, cpi_change], axis=1).dropna().index[0]
    scenario_label = (
        f"Scenario: CPI = {actual:.2f} + {fit[0]:.3f} {times} months ahead + {fit[1]:.3f} {times} "
        f"(BCOM \N{MINUS SIGN} {commodity_yoy.loc[last:last].iloc[0]:.1f})\n"
        f"CPI and BCOM as YoY %; fitted on monthly changes since {fitted_from.year}"
    )
    actual_color, scenario_color = get_color_list(2)
    ax = None
    for label, (_, alpha) in FORECAST_BANDS.items():
        ax = mg.fill_between_plot(bands[label], ax=ax, color=scenario_color, alpha=alpha, label=label)
    lines = pd.DataFrame(
        {
            "CPI, annual growth": cpi_yoy.iloc[-FORECAST_HISTORY_MONTHS:],
            scenario_label: pd.concat([cpi_yoy.iloc[-1:], path]),
        }
    )
    ax = mg.line_plot(
        lines, ax=ax, color=[actual_color, scenario_color], style=["-", "--"], annotate=True, rounding=2
    )
    mg.finalise_plot(
        ax,
        title="Australian CPI: Scenario with Commodity Prices Held Flat",
        ylabel="Per cent, year on year",
        legend={"loc": "upper left", "fontsize": "x-small"},
        axhspan=ANNUAL_CPI_TARGET_RANGE,
        axvline=None if breakdown is None else {"x": breakdown, **BREAKDOWN_LINE},
        lfooter=(
            f"Australia. Seasonally adjusted. BCOM ({BCOM_ETN}) held at {etn.index[-1]} close. "
            f"Bands: backtest errors given actual BCOM, from {BACKTEST_FROM[:4]}."
        ),
        rfooter=f"ABS: 6401.0, 6484.0; {SOURCE_YAHOO}",
    )


# --- table of contents, in run order
CHARTS = (
    (metals, ()),
    (grains, ()),
    (softs, ()),
    (commodity_index, ()),
    (commodity_index_history, ()),
    (commodities_vs_cpi, ()),
    (commodity_cpi_lags, ()),
    (cpi_scenario, ()),
)
