"""Australian System of National Accounts (5204.0): annual growth, market-sector productivity, capital stocks.

Financial years ending 30 June.
"""

# --- dependencies
from typing import Any

import mgplot as mg
import pandas as pd
import readabs as ra
from readabs import metacol as mc

from au_econ.sources.abs import AbsRelease, fetch_release

# --- module contract
RELEASE = ("5204", "asna")
TOPICS = ("economy",)
TITLE = "Annual National Accounts"

# --- constants
CATALOGUE = "5204.0"
KEY_AGGREGATES = "5204001_Key_National_Aggregates"
PRODUCTIVITY = "5204013_Productivity"
BALANCE_SHEET = "5204010_National_Balance_Sheet"
LAND = "5204061_Land_Value_By_Use"
FINANCIAL_YEAR = "Financial Year ending 30 June"
GROWTH_DIDS = (
    "GROSS DOMESTIC PRODUCT: Chain volume measures - Percentage changes ;",
    "GDP per capita: Chain volume measures - Percentage changes ;",
    "Gross value added market sector: Chain volume measures - Percentage changes ;",
    "Net domestic product: Chain volume measures - Percentage changes ;",
    "Real gross domestic income: Volume measures - Percentage changes ;",
    "Real gross national income: Volume measures - Percentage changes ;",
    "Real net national disposable income: Volume measures - Percentage changes ;",
    "Real net national disposable income per capita: Volume measures - Percentage changes ;",
)
PRODUCTIVITY_SELECTOR = {PRODUCTIVITY: mc.table, "Percent": mc.unit, "Quality|Capital": mc.did}  # 3 of 5 series
BAR_WIDTH = 0.66
THOUSAND, PERCENT = 1_000.0, 100
LEGEND = {"loc": "best", "fontsize": "x-small"}
RESIDENTIAL = "Residential housing (dwellings + land)"
BUSINESS = "Business capital (non-dwelling + M&E + IPP + bio + comm/rural land)"
BUSINESS_ASSETS = (
    "Non-dwelling construction",
    "Machinery and equipment",
    "Intellectual property products",
    "Cultivated biological resources",
)


# --- data
def fetch() -> AbsRelease:
    """Fetch the release once; every chart function receives it."""
    return fetch_release(CATALOGUE)


# --- helpers
def _series(release: AbsRelease, table: str, did: str) -> pd.Series:
    _table, series_id, _units = ra.find_abs_id(release.meta, {table: mc.table, did: mc.did}, verbose=False)
    return release.data[table][series_id]


def _fixed_assets(release: AbsRelease, name: str) -> pd.Series:
    """One fixed-asset value from the national balance sheet, current prices ($ billions)."""
    return _series(release, BALANCE_SHEET, f"Non-financial - Produced - Fixed assets - {name}: Current prices ;")


def _land(release: AbsRelease, use: str) -> pd.Series:
    """Return the value of land by use ($ billions)."""
    return _series(release, LAND, f"{use} - Australia ;")


# --- charts
def headline_growth(release: AbsRelease) -> None:
    """Chart annual growth in GDP, GDP per capita, market-sector GVA, net domestic product and real incomes."""
    for did in GROWTH_DIDS:
        mg.line_plot_finalise(
            _series(release, KEY_AGGREGATES, did),
            title=did.replace(" - Percentage changes ;", "").replace("GROSS DOMESTIC PRODUCT", "GDP"),
            ylabel="Percentage Change Year on Year",
            xlabel=FINANCIAL_YEAR,
            y0=True,
            annotate=True,
            rounding=1,
            rfooter=release.source,
            lfooter="Australia. Original series. ",
        )


def ms_productivity(release: AbsRelease) -> None:
    """Chart market-sector productivity growth (labour, capital, multifactor) as bars and as lines."""
    rows = ra.search_abs_meta(release.meta, PRODUCTIVITY_SELECTOR, regex=True)
    data = release.data[PRODUCTIVITY][rows[mc.id]]
    data.index.name = "Year"
    data.columns = rows[mc.did].str.replace(": Percentage changes ;", "")
    common: dict[str, Any] = {
        "title": "Productivity Growth in the Market Sector",
        "ylabel": "Percent Change Year on Year",
        "xlabel": FINANCIAL_YEAR,
        "y0": True,
        "rfooter": release.source,
        "lfooter": "Australia. Original series. ",
    }
    mg.bar_plot_finalise(data, tag="bar", width=BAR_WIDTH, **common)
    mg.line_plot_finalise(data, tag="line", **common)


def dwelling_vs_business_capital(release: AbsRelease) -> None:
    """Chart the value of residential housing against business capital: levels, shares, and multiples of GDP.

    Each side combines fixed assets from the national balance sheet (table 10) with the land
    beneath them (table 61), in current prices.
    """
    nominal_gdp = _series(release, KEY_AGGREGATES, "GROSS DOMESTIC PRODUCT: Current prices ;") / THOUSAND
    residential = _fixed_assets(release, "Dwellings") + _land(release, "Residential")
    business = sum(_fixed_assets(release, asset) for asset in BUSINESS_ASSETS) + _land(release, "Commercial")
    business = business + _land(release, "Rural")
    # $ billions -> $ trillions
    levels = pd.DataFrame({RESIDENTIAL: residential, BUSINESS: business}).dropna(how="all") / THOUSAND
    common: dict[str, Any] = {
        "xlabel": FINANCIAL_YEAR,
        "rfooter": release.source,
        "lfooter": "Australia. Original series. Current prices. ",
        "annotate": True,
        "legend": LEGEND,
    }
    mg.line_plot_finalise(
        levels,
        title="Value of residential housing vs business capital stock",
        ylabel="$ Trillions (current prices)",
        rounding=2,
        **common,
    )
    total = levels.sum(axis=1)
    mg.line_plot_finalise(
        pd.DataFrame(
            {RESIDENTIAL: levels[RESIDENTIAL] / total * PERCENT, BUSINESS: levels[BUSINESS] / total * PERCENT}
        ),
        title="Residential housing vs business capital: share of combined total",
        ylabel="Per cent (residential + business)",
        rounding=1,
        **common,
    )
    mg.line_plot_finalise(
        pd.DataFrame({RESIDENTIAL: residential / nominal_gdp, BUSINESS: business / nominal_gdp}).dropna(how="all"),
        title="Residential housing vs business capital: as a multiple of nominal GDP",
        ylabel="Multiple of annual nominal GDP",
        rounding=2,
        **common,
    )


# --- table of contents, in run order
CHARTS = (
    (headline_growth, ()),
    (ms_productivity, ()),
    (dwelling_vs_business_capital, ()),
)
