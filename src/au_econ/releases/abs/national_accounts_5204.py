"""Australian System of National Accounts (5204.0): annual growth and market-sector productivity.

Financial years ending 30 June.
"""

# --- dependencies
from typing import Any

import mgplot as mg
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


# --- data
def fetch() -> AbsRelease:
    """Fetch the release once; every chart function receives it."""
    return fetch_release(CATALOGUE)


# --- charts
def headline_growth(release: AbsRelease) -> None:
    """Chart annual growth in GDP, GDP per capita, market-sector GVA, net domestic product and real incomes."""
    for did in GROWTH_DIDS:
        _table, series_id, _units = ra.find_abs_id(
            release.meta, {KEY_AGGREGATES: mc.table, did: mc.did}, verbose=False
        )
        mg.line_plot_finalise(
            release.data[KEY_AGGREGATES][series_id],
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


# --- table of contents, in run order
CHARTS = (
    (headline_growth, ()),
    (ms_productivity, ()),
)
