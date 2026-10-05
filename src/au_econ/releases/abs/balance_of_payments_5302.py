"""Balance of Payments and International Investment Position, Australia (5302.0), quarterly.

The current account and its parts, portfolio debt flows and stocks, and net exports: the
balance of payments is published a day or so before the National Accounts, so its net
exports preview the trade contribution to GDP growth.
"""

# --- dependencies
import pandas as pd
import readabs as ra
from mgplot import bar_plot_finalise, line_plot_finalise, multi_start, scatter_plot_finalise
from readabs import metacol as mc
from readabs.download_cache import CacheError, HttpError

from au_econ.charting.footers import SERIES_TYPE_NOTES
from au_econ.charting.windows import quarterly_plot_times
from au_econ.series.gdp import get_gdp, get_table
from au_econ.sources.abs import AbsRelease, fetch_release

# --- module contract
RELEASE = ("5302", "bop")
TOPICS = ("trade",)
TITLE = "Balance of Payments"

# --- constants
CATALOGUE = "5302.0"
QUARTERS_PER_YEAR = 4
PERCENT = 100
SA, ORIGINAL = "Seasonally Adjusted", "Original"
LEGEND = {"loc": "best", "fontsize": "small"}
SCATTER_LEGEND = {"loc": "upper left", "fontsize": 9}
WITH_GDP_SOURCE = "ABS: 5206.0, 5302.0"  # charts that use the National Accounts

# headline current account (table 530204)
HEADLINE_TABLE = "530204"
HEADLINE = {
    "Current Account Balance": "Current account ;",
    "Balance of Trade in Goods and Services": "Goods and Services ;",
    "Net Primary Income": "Primary income ;",
    "Net Secondary Income": "Secondary income ;",
}
SA_NOTE = SERIES_TYPE_NOTES[SA]
HEADLINE_LFOOTER = f"Australia. {SA_NOTE} Current prices. "

# portfolio debt: flows (5302013) and end-of-period positions (5302015)
FLOW_TABLE, STOCK_TABLE = "5302013", "5302015"
EOP = "Position at end of period ;  "
DEBT_FLOWS = {
    "Total": "PORTFOLIO INVESTMENT, Liabilities, Debt securities ;",
    "General government": "PORTFOLIO INVESTMENT, Liabilities, Debt securities, General government ;",
    "Banks": (
        "PORTFOLIO INVESTMENT, Liabilities, Debt securities, "
        "Deposit-taking corporations, except the central bank ;"
    ),
    "Other sectors": "PORTFOLIO INVESTMENT, Liabilities, Debt securities, Other sectors ;",
}
DEBT_STOCKS = {
    "Total": f"{EOP}PORTFOLIO INVESTMENT, Debt securities ;",
    "General government": f"{EOP}PORTFOLIO INVESTMENT, Debt securities, General government ;",
    "Banks": f"{EOP}PORTFOLIO INVESTMENT, Debt securities, Deposit-taking corporations, except the central bank ;",
    "Other sectors": f"{EOP}PORTFOLIO INVESTMENT, Debt securities, Other sectors ;",
}

# net exports
GS_TABLE = "530205"  # chain volume goods and services account: credits, debits and balance
CREDITS_CVM = "Chain Volume Measures ;  Goods and Services credits ;"
DEBITS_CVM = "Chain Volume Measures ;  Goods and Services debits ;"  # debits are stored negative
CREDITS_CP = "Goods and Services credits ;"
NA_VOLUMES = "5206002_Expenditure_Volume_Measures"
NA_EXPORTS, NA_IMPORTS = "Exports of goods and services ;", "Imports of goods and services ;"
QUARTER_END_MONTHS = {1: "mar", 2: "jun", 3: "sep", 4: "dec"}  # for an ABS vintage tag, e.g. "jun-2026"
DOWN_WEIGHT_TOLERANCE = 1e-3  # a factor this close to 1 is no down-weight


# --- data
def fetch() -> AbsRelease:
    """Fetch the release once; every chart function receives it."""
    return fetch_release(CATALOGUE)


# --- helpers
def _select(release: AbsRelease, table: str, did: str, stype: str) -> tuple[pd.Series, str]:
    """One series by table, exact data item description and series type, with its units."""
    selector = {stype: mc.stype, did: mc.did, table: mc.table}
    _table, series_id, units = ra.find_abs_id(release.meta, selector, exact_match=True)
    return release.data[table][series_id], units


def _by_did(release: AbsRelease, did: str) -> pd.Series:
    """Return the seasonally adjusted series whose description is exactly did."""
    meta = release.meta
    row = meta[(meta[mc.did] == did) & (meta[mc.stype] == SA)].iloc[0]
    return release.data[row[mc.table]][row[mc.id]].dropna()


def _net_exports_row(release: AbsRelease) -> pd.Series:
    """Return the metadata row of the chain volume goods and services balance (not credits, debits or states)."""
    meta = release.meta
    mask = (
        (meta[mc.stype] == SA)
        & meta[mc.did].str.contains("Chain Volume Measures", na=False)
        & meta[mc.did].str.contains("Goods and Services ;", na=False)
        & ~meta[mc.did].str.contains("credits|debits|,", na=False, regex=True)
    )
    return meta[mask].iloc[0]


def _recalibrated[T: (pd.Series, pd.DataFrame)](data: T, units: str) -> tuple[T, str]:
    """Recalibrate to readable units."""
    result, units = ra.recalibrate(data, units)
    if not isinstance(result, type(data)):
        raise TypeError(f"recalibrate returned {type(result).__name__}")
    return result, units


def _yoy(series: pd.Series) -> pd.Series:
    return (series / series.shift(QUARTERS_PER_YEAR) - 1) * PERCENT


def _headline_chart(series: pd.Series, title: str, units: str, rfooter: str) -> None:
    multi_start(
        series,
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title=title,
        ylabel=units,
        annotate=True,
        y0=True,
        rfooter=rfooter,
        lfooter=HEADLINE_LFOOTER,
    )


def _debt_charts(
    release: AbsRelease,
    table: str,
    wanted: dict[str, str],
    gdp: pd.Series,
    *,
    title: str,
    lfooters: tuple[str, str],
    flow: bool,
) -> None:
    """Chart portfolio debt by sector: the level (a flow per quarter, or a stock), and as a share of GDP."""
    box = {}
    units = ""
    for label, did in wanted.items():
        box[label], units = _select(release, table, did, ORIGINAL)
    frame, units = _recalibrated(pd.DataFrame(box), units)
    if flow:
        units = f"{units}/Quarter"
    level_lfooter, share_lfooter = lfooters
    multi_start(
        frame,
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title=title,
        ylabel=units,
        y0=True,
        rfooter=release.source,
        lfooter=level_lfooter,
        legend=LEGEND,
    )
    shares = pd.DataFrame(box)  # unscaled
    for column in shares.columns:
        shares[column] = shares[column] / gdp * PERCENT
    multi_start(
        shares.dropna(),
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title=f"{title} (% GDP)",
        ylabel="Per cent of GDP",
        y0=True,
        rfooter=WITH_GDP_SOURCE,
        lfooter=share_lfooter,
        legend=LEGEND,
    )


# --- charts
def headline(release: AbsRelease) -> None:
    """Chart the current account and its parts: levels, shares of GDP, and net income."""
    box = {title: _select(release, HEADLINE_TABLE, did, SA) for title, did in HEADLINE.items()}
    source, with_gdp = release.source, WITH_GDP_SOURCE
    gdp, _gdp_units = get_gdp("CP", "SA")  # GDP comes out a day to a week after the balance of payments
    for title, (series, units) in box.items():
        recal_series, recal_units = _recalibrated(series, units)
        _headline_chart(recal_series, title, f"{recal_units}/Quarter", source)
        _headline_chart(series / gdp * PERCENT, f"{title} as a % of GDP", "Per cent", with_gdp)

    current_account = box["Current Account Balance"][0]
    _headline_chart(
        (
            current_account.rolling(QUARTERS_PER_YEAR).sum() / gdp.rolling(QUARTERS_PER_YEAR).sum() * PERCENT
        ).dropna(),
        "Current Account Balance as a % of GDP: 4Q rolling sum",
        "Per cent",
        with_gdp,
    )

    net_income = box["Net Primary Income"][0] + box["Net Secondary Income"][0]
    recal_net_income, recal_units = _recalibrated(net_income, box["Net Primary Income"][1])
    _headline_chart(recal_net_income, "Net Income", f"{recal_units}/Quarter", source)
    _headline_chart(net_income / gdp * PERCENT, "Net Income as % of GDP", "Per cent", with_gdp)


def portfolio_debt_liabilities(release: AbsRelease) -> None:
    """Chart portfolio debt securities sold overseas (financial account flows) by sector."""
    gdp, _ = get_gdp("CP", "O")
    _debt_charts(
        release,
        FLOW_TABLE,
        DEBT_FLOWS,
        gdp,
        title="Portfolio debt sold overseas by sector",
        lfooters=(
            "Australia. Original series. Quarterly financial account flows.",
            "Australia. Original series. Quarterly financial account flows / quarterly GDP.",
        ),
        flow=True,
    )


def net_exports_bop_vs_na(release: AbsRelease) -> None:
    """Scatter net exports (CVM) from the balance of payments against the National Accounts.

    The National Accounts net exports are sourced from the same balance of payments data,
    so the points should sit on the 45-degree line.
    """
    row = _net_exports_row(release)
    bop = release.data[row[mc.table]][row[mc.id]].dropna()
    na_data, na_meta = get_table(NA_VOLUMES)

    def na(did: str) -> pd.Series:
        r = na_meta[(na_meta[mc.did] == did) & (na_meta[mc.stype] == SA)].iloc[0]
        return na_data[NA_VOLUMES][r[mc.id]].dropna()

    net = (na(NA_EXPORTS) - na(NA_IMPORTS)).dropna()
    frame = pd.DataFrame({"na": net, "bop": bop}).dropna()
    corr = frame["na"].corr(frame["bop"])
    scatter_plot_finalise(
        frame,
        label="Quarterly",
        diagonal=True,
        title="Net Exports: Balance of Payments vs National Accounts",
        xlabel="National Accounts net exports (5206), $m",
        ylabel="Balance of Payments:\nGoods & Services balance (5302), $m",
        legend=SCATTER_LEGEND,
        rfooter=WITH_GDP_SOURCE,
        lfooter=(
            f"Australia. {SA_NOTE} Chain volume measures. "
            f"BoP G&S balance vs NA exports - imports. R²={corr**2:.3f}, n={len(frame)}. "
        ),
    )


def net_exports_bars(release: AbsRelease) -> None:
    """Chart net exports of goods and services (CVM) as quarterly bars: above zero a surplus."""
    row = _net_exports_row(release)
    net, units = _recalibrated(release.data[row[mc.table]][row[mc.id]].dropna(), str(row[mc.unit]))
    net.name = "Net exports"
    multi_start(
        net,
        function=bar_plot_finalise,
        starts=quarterly_plot_times,
        title="Net Exports of Goods and Services",
        ylabel=f"{units}/Quarter",
        annotate=True,
        rounding=1,
        rfooter=release.source,
        lfooter=f"Australia. {SA_NOTE} Chain volume measures. BoP G&S balance = NA net exports. ",
    )


def _history_factors(gdp_tag: str, exports: pd.Series, imports: pd.Series) -> tuple[float, float]:
    """Return factors putting exports and imports on the reference basis of the vintage with the latest GDP."""
    data, meta = ra.read_abs_cat(CATALOGUE, single_excel_only=GS_TABLE, history=gdp_tag, verbose=False)

    def hist(did: str) -> pd.Series:
        r = meta[(meta[mc.did] == did) & (meta[mc.stype] == SA)].iloc[0]
        return data[GS_TABLE][r[mc.id]].dropna()

    past_exports, past_imports = hist(CREDITS_CVM), hist(DEBITS_CVM)
    on_exports = exports.index.intersection(past_exports.index)
    on_imports = imports.index.intersection(past_imports.index)
    return (
        float((exports.loc[on_exports] / past_exports.loc[on_exports]).median()),
        float((imports.loc[on_imports] / past_imports.loc[on_imports]).median()),
    )


def net_exports_contribution(release: AbsRelease) -> None:
    """Chart the estimated net exports contribution to quarterly GDP growth (percentage points).

    contribution = (net exports - last quarter's) / last quarter's real GDP * 100, which can
    be computed the day before the National Accounts. In the annual re-referencing quarter
    the balance of payments is on the new reference year while the latest GDP is on the old
    one; net exports is a small balance of two large aggregates, so that gap is leveraged.
    Exports and imports are then scaled back onto the GDP vintage's basis by the median
    ratio of the current series to the vintage published with the latest GDP. Otherwise
    both factors are 1 and the extra fetch is skipped.
    """
    exports, imports = _by_did(release, CREDITS_CVM), _by_did(release, DEBITS_CVM)
    gdp_all, _units = get_gdp("CVM", "SA")
    gdp = gdp_all.dropna()
    last = gdp.index[-1]
    if not isinstance(last, pd.Period):
        raise TypeError("Expected a quarterly PeriodIndex for GDP")
    gdp_tag = f"{QUARTER_END_MONTHS[last.quarter]}-{last.year}"

    f_exp = f_imp = 1.0
    if gdp.index[-1] < exports.index[-1]:
        try:
            f_exp, f_imp = _history_factors(gdp_tag, exports, imports)
        except (HttpError, CacheError, OSError, ValueError, KeyError, IndexError) as error:  # chart without it
            print(f"Re-referencing down-weight skipped: {error}")

    net = (exports / f_exp + imports / f_imp).dropna()  # debits negative -> net exports
    gdp_lag = gdp.copy()
    gdp_lag.index = gdp_lag.index + 1  # by index, so the leading quarter divides by the last published GDP
    contribution = ((net - net.shift(1)) / gdp_lag * PERCENT).dropna()
    contribution.name = "Net exports contribution"
    tolerance = DOWN_WEIGHT_TOLERANCE
    down_weight = (
        "none"
        if abs(f_exp - 1) < tolerance and abs(f_imp - 1) < tolerance
        else f"exp x{f_exp:.3f}, imp x{f_imp:.3f}"
    )
    multi_start(
        contribution,
        function=bar_plot_finalise,
        starts=quarterly_plot_times,
        title="Estimated Net Exports Contribution to GDP Growth",
        ylabel="Percentage points (quarterly)",
        annotate=True,
        rounding=1,
        y0=True,
        rfooter=WITH_GDP_SOURCE,
        lfooter=f"Australia. {SA_NOTE} Net exports change / lagged GDP, CVM. Down-weight: {down_weight}. ",
    )


def gdp_deflator_from_bop(release: AbsRelease) -> None:
    """Scatter the GDP deflator (YoY) against the balance of payments export price deflator (YoY).

    The export deflator (goods and services credits, CP / CVM) is a trade price, not the
    GDP deflator: the balance of payments carries only exports and imports, so this shows
    how much of the GDP deflator's movement the trade-price signal captures.
    """
    nominal, _ = get_gdp("CP", "SA")
    real, _ = get_gdp("CVM", "SA")
    gdp_deflator = nominal.dropna() / real.dropna() * PERCENT
    export_deflator = _by_did(release, CREDITS_CP) / _by_did(release, CREDITS_CVM) * PERCENT
    frame = pd.DataFrame({"gdp": _yoy(gdp_deflator), "bop": _yoy(export_deflator)}).dropna()
    corr = frame["gdp"].corr(frame["bop"])
    scatter_plot_finalise(
        frame[["bop", "gdp"]],  # x first: the export deflator against the GDP deflator
        label="Quarterly (YoY)",
        title="GDP Deflator vs BoP Export Price Deflator",
        xlabel="BoP export price deflator, YoY growth (5302)",
        ylabel="GDP deflator,\nYoY growth (5206)",
        legend=SCATTER_LEGEND,
        rfooter=WITH_GDP_SOURCE,
        lfooter=(
            f"Australia. {SA_NOTE} Export deflator = G&S credits CP / CVM. R²={corr**2:.2f}, n={len(frame)}. "
        ),
    )


def portfolio_debt_stock(release: AbsRelease) -> None:
    """Chart the outstanding stock of portfolio debt held overseas, by sector."""
    gdp, _ = get_gdp("CP", "O")
    _debt_charts(
        release,
        STOCK_TABLE,
        DEBT_STOCKS,
        gdp.rolling(QUARTERS_PER_YEAR, min_periods=QUARTERS_PER_YEAR).sum(),
        title="Portfolio debt held overseas by sector",
        lfooters=(
            "Australia. Original series. International investment position, end of period.",
            "Australia. Original series. IIP end of period / GDP 4Q rolling sum.",
        ),
        flow=False,
    )


# --- table of contents, in run order
CHARTS = (
    (headline, ()),
    (portfolio_debt_liabilities, ()),
    (net_exports_bop_vs_na, ()),
    (net_exports_bars, ()),
    (net_exports_contribution, ()),
    (gdp_deflator_from_bop, ()),
    (portfolio_debt_stock, ()),
)
