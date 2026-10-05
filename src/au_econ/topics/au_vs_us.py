"""Australia against the United States: productivity, unit labour costs, rates, electricity and manufacturing.

Productivity and unit labour costs are drawn against their pre-COVID log-linear trends
(fitted 2010-2019 and extrapolated). The rates charts are daily (bond yields, term spreads)
and monthly (policy rates).
"""

# --- dependencies
import re
from dataclasses import dataclass
from typing import Any

import matplotlib.pyplot as plt
import mgplot as mg
import numpy as np
import pandas as pd
import readabs as ra
from readabs import metacol as mc

from au_econ.series.gdp import get_table
from au_econ.series.prices import get_cpi
from au_econ.series.rates import get_cash_rate
from au_econ.sources import dbnomics, fred, rba

# --- module contract
RELEASE = ("au-vs-us",)
TOPICS = ("international",)
TITLE = "Australia vs United States"

# --- constants
FRED_START = "1990-01-01"
FRED_IDS = {  # label: FRED series ID
    "US non-farm business output per hour": "OPHNFB",
    "US 10-year Treasury yield": "DGS10",
    "US effective federal funds rate, monthly": "FEDFUNDS",
    "US effective federal funds rate, daily": "DFF",
    "US CPI, all urban consumers": "CPIAUCSL",
    "US manufacturing value added, share of GDP": "VAPGDPMA",
}
DBNOMICS_PATHS = {  # label: DBnomics provider/dataset/series code
    "US GDP per hour": "OECD/DSD_PDB@DF_PDB/USA.A.GDPHRS._T.XDC_H.LR.N._Z._Z",
    "AU GDP per hour": "OECD/DSD_PDB@DF_PDB/AUS.A.GDPHRS._T.XDC_H.LR.N._Z._Z",
    "US unit labour costs": "OECD/DSD_PDB@DF_PDB_ULC_Q/USA.Q.ULCE._T.IX.V._Z.S.NC",
    "AU unit labour costs": "OECD/DSD_PDB@DF_PDB_ULC_Q/AUS.Q.ULCE._T.IX.V._Z.S.NC",
    "US industrial electricity price": "EIA/ELEC/PRICE.US-IND.M",
}
OECD_PDB = "DBnomics: OECD PDB"  # the OECD productivity database, read through DBnomics
EIA_TIMEOUT = 120  # seconds: DBnomics can take over a minute to serve the EIA series cold
# RBA daily series, by ID: the archived 2013 F2 workbook has no Title row to select by
RBA_IDS = {  # label: RBA series ID
    "Australian Government 10-year bond yield": "FCMYGBAG10D",
    "Interbank overnight cash rate": "FIRMMCRID",
}
RBA_10Y = ("Australian Government 10-year bond yield", ("F2", "Z:F2-Daily-2013"))  # current vintage first
RBA_OVERNIGHT = ("Interbank overnight cash rate", ("F1", "Z:F1-Daily-2010"))

KEY_AGGREGATES = "5206001_Key_Aggregates"
INDUSTRY_GVA = "5206045_Industry_GVA_Current_Price"
PPI_CATALOGUE, PPI_TABLE = "6427.0", "6427013"
SA, ORIGINAL = "Seasonally Adjusted", "Original"

BASE_QUARTER = pd.Period("2019Q3", freq="Q")
BASE_YEAR = pd.Period("2019", freq="Y-DEC")
Q_FIT_START, Q_FIT_END = pd.Period("2010Q1", freq="Q"), pd.Period("2019Q4", freq="Q")
A_FIT_START, A_FIT_END = pd.Period("2010", freq="Y-DEC"), pd.Period("2019", freq="Y-DEC")
Q_PLOT_START = pd.Period("2010Q1", freq="Q")
A_PLOT_START = pd.Period("2010", freq="Y-DEC")
RATES_START = pd.Period("1995-01-03", freq="D")  # where the RBA's daily F2 vintage begins
ELEC_BASE = pd.Period("2010Q1", freq="Q")
INDEX_BASE = 100.0
PERCENT = 100
EN_DASH = chr(0x2013)

AU_COLOUR, US_COLOUR, TREND_COLOUR = "blue", "darkorange", "#888888"
TREND_STYLE: dict[str, Any] = {
    "color": [TREND_COLOUR, TREND_COLOUR, US_COLOUR, AU_COLOUR],
    "width": [1.0, 1.0, 2.0, 2.0],
    "style": ["--", ":", "-", "-"],
    "annotate": [False, False, True, True],
    "rounding": 1,
    "fontsize": "small",
    "dropna": True,
}
LEGEND_UL = {"loc": "upper left", "fontsize": "x-small", "frameon": False}
LEGEND_UR = {"loc": "upper right", "fontsize": "x-small", "frameon": False}
LEGEND_LL = {"loc": "lower left", "fontsize": "x-small", "frameon": False}
LINE_100 = {"y": 100, "color": "black", "linewidth": 0.5, "zorder": -1}
SIDE_BY_SIDE_SIZE = (9, 4.5)
SIDE_BY_SIDE_DPI = 300


@dataclass(frozen=True)
class Comparison:
    """Every series the charts use, indexed where the charts index them."""

    au_gdp_a: pd.Series
    us_gdp_a: pd.Series
    au_market_q: pd.Series
    us_nfb_q: pd.Series
    au_ulc_q: pd.Series
    us_ulc_q: pd.Series
    au_10y_d: pd.Series
    us_10y_d: pd.Series
    au_ocr_m: pd.Series
    us_ff_m: pd.Series
    au_overnight_d: pd.Series
    us_ff_d: pd.Series
    au_elec_real: pd.Series
    us_elec_real: pd.Series
    mfg: pd.DataFrame


# --- data
def _fred(label: str, frequency: str, freq: str) -> pd.Series:
    """Fetch a FRED series by label, at the frequency asked of FRED, on a PeriodIndex."""
    series = fred.get_series(FRED_IDS[label], FRED_START, frequency)
    series.index = pd.PeriodIndex(series.index, freq=freq)
    return series


def _rba_daily(series: tuple[str, tuple[str, ...]]) -> pd.Series:
    """Join the RBA's daily vintages of one series (label, tables), most recent vintage first.

    The RBA splits its daily tables across files with no overlapping days, so this is a
    plain concatenation; a duplicate would take the most recent vintage.
    """
    label, tables = series
    joined = pd.concat([rba.get_table(table)[0][RBA_IDS[label]].dropna().astype(float) for table in tables])
    return joined[~joined.index.duplicated(keep="first")].sort_index()


def _abs_series(data: dict[str, pd.DataFrame], meta: pd.DataFrame, selector: dict[str, str]) -> pd.Series:
    table, series_id, _units = ra.find_abs_id(meta, selector, exact_match=True, verbose=False)
    return data[table][series_id].dropna()


def _rebase(series: pd.Series, base: pd.Period) -> pd.Series:
    """Rebase a series to 100 at the base period."""
    return series / series[series.index == base].iloc[0] * INDEX_BASE


def _au_market_productivity() -> pd.Series:
    """ABS market-sector gross value added per hour worked (SA, quarterly)."""
    data, meta = get_table(KEY_AGGREGATES)
    selector = {
        KEY_AGGREGATES: mc.table,
        "Gross value added per hour worked market sector: Index ;": mc.did,
        SA: mc.stype,
    }
    table, series_id, _units = ra.find_abs_id(meta, selector, verbose=False)
    return data[table][series_id].dropna()


def _au_electricity_ppi() -> pd.Series:
    """ABS PPI input price of electricity to manufacturing (quarterly index)."""
    data, meta = ra.read_abs_cat(PPI_CATALOGUE, single_excel_only=PPI_TABLE, verbose=False)
    return _abs_series(
        data, meta, {PPI_TABLE: mc.table, "Index Numbers ;  Electricity ;": mc.did, ORIGINAL: mc.stype}
    )


def _au_manufacturing_share() -> pd.Series:
    """AU manufacturing GVA as a share of GDP, current prices, SA, quarterly."""
    gva_data, gva_meta = get_table(INDUSTRY_GVA)
    gva = _abs_series(
        gva_data,
        gva_meta,
        {INDUSTRY_GVA: mc.table, "Manufacturing (C) ;  Gross value added at basic prices ;": mc.did, SA: mc.stype},
    )
    ka_data, ka_meta = get_table(KEY_AGGREGATES)
    gdp = _abs_series(
        ka_data,
        ka_meta,
        {KEY_AGGREGATES: mc.table, "Gross domestic product: Current prices ;": mc.did, SA: mc.stype},
    )
    return (gva / gdp * PERCENT).dropna().rename("Australia")


def fetch() -> Comparison:
    """Fetch every series, and rebase the productivity, cost and electricity series."""
    us_elec_m = dbnomics.get_series(DBNOMICS_PATHS["US industrial electricity price"], timeout=EIA_TIMEOUT)
    if not isinstance(us_elec_m.index, pd.PeriodIndex):
        raise TypeError("Expected a monthly PeriodIndex for the EIA electricity price")
    us_elec_q = us_elec_m.groupby(us_elec_m.index.asfreq("Q-DEC")).mean()
    us_cpi_q = _fred("US CPI, all urban consumers", "q", "Q")
    au_cpi_q = get_cpi("headline_sa")[0]
    us_mfg = _fred("US manufacturing value added, share of GDP", "q", "Q").rename("United States")
    return Comparison(
        au_gdp_a=_rebase(dbnomics.get_series(DBNOMICS_PATHS["AU GDP per hour"]), BASE_YEAR),
        us_gdp_a=_rebase(dbnomics.get_series(DBNOMICS_PATHS["US GDP per hour"]), BASE_YEAR),
        au_market_q=_rebase(_au_market_productivity(), BASE_QUARTER),
        us_nfb_q=_rebase(_fred("US non-farm business output per hour", "q", "Q"), BASE_QUARTER),
        au_ulc_q=_rebase(dbnomics.get_series(DBNOMICS_PATHS["AU unit labour costs"]), BASE_QUARTER),
        us_ulc_q=_rebase(dbnomics.get_series(DBNOMICS_PATHS["US unit labour costs"]), BASE_QUARTER),
        au_10y_d=_rba_daily(RBA_10Y).rename("Australia"),
        us_10y_d=_fred("US 10-year Treasury yield", "d", "D").rename("United States"),
        au_ocr_m=get_cash_rate().rename("Australia"),
        us_ff_m=_fred("US effective federal funds rate, monthly", "m", "M").rename("United States"),
        au_overnight_d=_rba_daily(RBA_OVERNIGHT),
        us_ff_d=_fred("US effective federal funds rate, daily", "d", "D"),
        au_elec_real=_rebase((_au_electricity_ppi() / au_cpi_q).dropna(), ELEC_BASE),
        us_elec_real=_rebase((us_elec_q / us_cpi_q).dropna(), ELEC_BASE),
        mfg=pd.concat([us_mfg, _au_manufacturing_share()], axis=1).sort_index(),
    )


# --- helpers
def _trend(series: pd.Series, fit_start: pd.Period, fit_end: pd.Period, extrap_end: pd.Period) -> pd.Series:
    """Fit a log-linear trend on [fit_start, fit_end] and extrapolate it to extrap_end."""
    sub = series[(series.index >= fit_start) & (series.index <= fit_end)]
    slope, intercept = np.polyfit(np.arange(len(sub)), np.log(sub.to_numpy()), 1)
    full_index = pd.period_range(fit_start, extrap_end, freq=fit_start.freq)
    return pd.Series(np.exp(intercept + slope * np.arange(len(full_index))), index=full_index)


def _trends(us: pd.Series, au: pd.Series, fit: tuple[pd.Period, pd.Period]) -> tuple[pd.Series, pd.Series]:
    """Fit both trends, extrapolated to the later of the two series' last periods."""
    end = max(us.index[-1], au.index[-1])
    return _trend(us, *fit, end), _trend(au, *fit, end)


def _from[T: (pd.Series, pd.DataFrame)](data: T, start: pd.Period) -> T:
    return data.loc[data.index >= start]


def _trend_frame(us: pd.Series, au: pd.Series, fit: tuple[pd.Period, pd.Period], start: pd.Period) -> pd.DataFrame:
    """Return the actuals and their trends from start, trends first (drawn beneath)."""
    us_trend, au_trend = _trends(us, au, fit)
    return pd.DataFrame(
        {
            "US trend (pre-COVID)": _from(us_trend, start),
            "Australia trend (pre-COVID)": _from(au_trend, start),
            "United States": _from(us, start),
            "Australia": _from(au, start),
        }
    )


def _latest_note(
    au: pd.Series,
    us: pd.Series,
    *,
    unit: str = "",
    date_fmt: str | None = "%d-%b-%Y",
    rounding: int = 2,
    prefix: str = "Latest:",
) -> str:
    """Return right-header text giving each series' latest value and its date (date_fmt None: the period)."""

    def part(label: str, series: pd.Series) -> str:
        last = series.index[-1]
        stamp = last.strftime(date_fmt) if date_fmt is not None and isinstance(last, pd.Period) else str(last)
        return f"{label} {series.iloc[-1]:.{rounding}f}{unit} ({stamp})"

    return f"{prefix}  {part('AU', au)}   {part('US', us)}"


def _two_digit_years(label: str) -> str:
    """Shorten 4-digit years to 2 digits (e.g. 2010 -> 10)."""
    return re.sub(r"\b(?:19|20)(\d{2})\b", r"\1", label)


def _term_spread(long_leg: pd.Series, short_leg: pd.Series) -> pd.Series:
    """Long yield less the overnight rate, on the long leg's trading days."""
    aligned = short_leg.reindex(long_leg.index, method="ffill")
    return _from((long_leg - aligned).dropna(), RATES_START)


def _plot_trend_chart(frame: pd.DataFrame, *, title: str, ylabel: str, source: str, footer: str) -> None:
    mg.line_plot_finalise(
        frame,
        title=title,
        ylabel=ylabel,
        rfooter=source,
        lfooter=footer,
        legend=LEGEND_UL,
        axhline=LINE_100,
        **TREND_STYLE,
    )


# --- charts
def productivity_and_costs(data: Comparison) -> None:
    """Chart productivity (annual and quarterly) and unit labour costs against their pre-COVID trends."""
    rows = (
        ("US whole-economy GDP/hr (annual)", data.us_gdp_a, (A_FIT_START, A_FIT_END), data.au_gdp_a),
        ("US non-farm business productivity", data.us_nfb_q, (Q_FIT_START, Q_FIT_END), data.au_market_q),
        ("US unit labour costs", data.us_ulc_q, (Q_FIT_START, Q_FIT_END), data.au_ulc_q),
    )
    summary = {}
    for label, us, fit, au in rows:
        us_trend, au_trend = _trends(us, au, fit)
        for name, actual, trend in ((label, us, us_trend), (label.replace("US", "AU", 1), au, au_trend)):
            latest = actual.iloc[-1]
            at = trend[trend.index == actual.index[-1]].iloc[0]
            summary[name] = {"latest": latest, "trend": at, "gap_pct": (latest / at - 1) * PERCENT}
    print(pd.DataFrame(summary).T)

    _plot_trend_chart(
        _trend_frame(data.us_gdp_a, data.au_gdp_a, (A_FIT_START, A_FIT_END), A_PLOT_START),
        title="Whole-economy labour productivity (annual): Australia vs United States",
        ylabel="Index, 2019 = 100",
        source=OECD_PDB,
        footer=f"GDP per hour worked. Trend: log-linear fit on 2010{EN_DASH}2019, extrapolated.",
    )
    _plot_trend_chart(
        _trend_frame(data.us_nfb_q, data.au_market_q, (Q_FIT_START, Q_FIT_END), Q_PLOT_START),
        title="Labour productivity (quarterly): Australia vs United States",
        ylabel="Index, 2019-Q3 = 100",
        source="ABS: 5206.0; FRED: OPHNFB",
        footer="Seasonally adjusted. AU: market-sector GVA/hr. US: non-farm business output/hr. "
        f"Trend: log-linear, 2010Q1{EN_DASH}2019Q4.",
    )
    _plot_trend_chart(
        _trend_frame(data.us_ulc_q, data.au_ulc_q, (Q_FIT_START, Q_FIT_END), Q_PLOT_START),
        title="Unit labour costs (quarterly): Australia vs United States",
        ylabel="Index, 2019-Q3 = 100",
        source=OECD_PDB,
        footer="Seasonally adjusted. Employment-based ULC, current prices. "
        f"Trend: log-linear fit on 2010Q1{EN_DASH}2019Q4, extrapolated.",
    )


def productivity_side_by_side(data: Comparison) -> None:
    """Chart whole-economy (annual, left) and market-sector (quarterly, right) productivity in two panels."""
    _fig, (ax_a, ax_q) = plt.subplots(1, 2, figsize=SIDE_BY_SIDE_SIZE)
    mg.line_plot(
        _trend_frame(data.us_gdp_a, data.au_gdp_a, (A_FIT_START, A_FIT_END), A_PLOT_START),
        ax=ax_a,
        tick_relabel=_two_digit_years,
        **TREND_STYLE,
    )
    mg.finalise_plot(
        ax_a,
        axes_only=True,
        title="Whole-economy (annual)",
        ylabel="Index, 2019 = 100",
        legend=LEGEND_UL,
        axhline=LINE_100,
    )
    mg.line_plot(
        _trend_frame(data.us_nfb_q, data.au_market_q, (Q_FIT_START, Q_FIT_END), Q_PLOT_START),
        ax=ax_q,
        tick_relabel=_two_digit_years,
        **TREND_STYLE,
    )
    mg.finalise_plot(
        ax_q,
        title="Market sector (quarterly)",
        ylabel="Index, 2019-Q3 = 100",
        legend=LEGEND_UL,
        axhline=LINE_100,
        suptitle="Labour productivity: Australia vs United States",
        lfooter="Australia. Seasonally adjusted. Trend: log-linear fit on pre-pandemic data, extrapolated.",
        rfooter=f"ABS: 5206.0; {OECD_PDB}; FRED: OPHNFB",
        figsize=SIDE_BY_SIDE_SIZE,
        dpi=SIDE_BY_SIDE_DPI,
    )


def ten_year_yields(data: Comparison) -> None:
    """Chart 10-year government bond yields, daily."""
    mg.line_plot_finalise(
        _from(pd.concat([data.us_10y_d, data.au_10y_d], axis=1).sort_index(), RATES_START),
        color=[US_COLOUR, AU_COLOUR],
        style=["-", "-"],
        annotate=True,
        rounding=2,
        fontsize="small",
        dropna=True,
        title="10-year government bond yields (daily): Australia vs United States",
        ylabel="Per cent per annum",
        rheader=_latest_note(data.au_10y_d, data.us_10y_d, unit="%"),
        rfooter="FRED: DGS10; RBA: F2",
        lfooter="AU: 10-year Australian Government bond yield (interpolated). US: Treasury constant maturity.",
        legend=LEGEND_UR,
    )


def policy_rates(data: Comparison) -> None:
    """Chart central bank policy rates, monthly."""
    frame = pd.concat([data.us_ff_m, data.au_ocr_m], axis=1).sort_index()
    start = max(data.au_ocr_m.index[0], data.us_ff_m.index[0])
    mg.line_plot_finalise(
        _from(frame, start),
        color=[US_COLOUR, AU_COLOUR],
        style=["-", "-"],
        drawstyle="steps-post",
        annotate=True,
        rounding=2,
        fontsize="small",
        dropna=True,
        title="Central bank policy rates (monthly): Australia vs United States",
        ylabel="Per cent",
        rheader=_latest_note(data.au_ocr_m, data.us_ff_m, unit="%", date_fmt="%b-%Y"),
        rfooter="FRED: FEDFUNDS; RBA: A2",
        lfooter="AU: RBA OCR target (steps on RBA decisions). "
        "US: effective FFR, monthly avg (smoothed across change months).",
        legend=LEGEND_UR,
    )


def term_spreads(data: Comparison) -> None:
    """Chart the term spread (10-year bond less the overnight rate), daily."""
    au = _term_spread(data.au_10y_d, data.au_overnight_d).rename("Australia")
    us = _term_spread(data.us_10y_d, data.us_ff_d).rename("United States")
    mg.line_plot_finalise(
        pd.concat([us, au], axis=1).sort_index(),
        color=[US_COLOUR, AU_COLOUR],
        style=["-", "-"],
        annotate=True,
        rounding=2,
        fontsize="small",
        dropna=True,
        y0=True,
        title="Term spread (daily): Australia vs United States",
        ylabel="Percentage points",
        rheader=_latest_note(au, us, unit="pp"),
        rfooter="FRED: DFF, DGS10; RBA: F1, F2",
        lfooter="10-year bond less the overnight policy rate. ",
        legend=LEGEND_LL,
    )


def real_electricity_prices(data: Comparison) -> None:
    """Chart real (CPI-deflated) industrial electricity prices, quarterly."""
    frame = _from(pd.DataFrame({"United States": data.us_elec_real, "Australia": data.au_elec_real}), ELEC_BASE)
    mg.line_plot_finalise(
        frame,
        color=[US_COLOUR, AU_COLOUR],
        annotate=True,
        rounding=0,
        fontsize="small",
        dropna=True,
        title="Real industrial electricity prices (quarterly): Australia vs United States",
        ylabel="Index, 2010-Q1 = 100, real (CPI-deflated)",
        rheader=_latest_note(
            data.au_elec_real,
            data.us_elec_real,
            date_fmt=None,
            rounding=0,
            prefix="Latest (real, 2010-Q1 = 100):",
        ),
        rfooter="ABS: 6401.0, 6427.0; DBnomics: EIA ELEC; FRED: CPIAUCSL",
        lfooter="AU: PPI for electricity inputs to manufacturing. US: EIA industrial retail.",
        legend=LEGEND_UL,
        axhline=LINE_100,
    )


def manufacturing_share(data: Comparison) -> None:
    """Chart manufacturing's share of GDP, quarterly."""
    mg.line_plot_finalise(
        _from(data.mfg, Q_PLOT_START),
        color=[US_COLOUR, AU_COLOUR],
        annotate=True,
        rounding=1,
        fontsize="small",
        dropna=True,
        title="Manufacturing share of GDP (quarterly): Australia vs United States",
        ylabel="Per cent of GDP",
        rfooter="ABS: 5206.0; FRED: VAPGDPMA",
        lfooter="Seasonally adjusted. AU: Mfg GVA / GDP, current prices. US: BEA Value Added by Industry / GDP.",
        legend=LEGEND_UR,
    )


# --- table of contents, in run order
CHARTS = (
    (productivity_and_costs, ()),
    (productivity_side_by_side, ()),
    (ten_year_yields, ()),
    (policy_rates, ()),
    (term_spreads, ()),
    (real_electricity_prices, ()),
    (manufacturing_share, ()),
)
