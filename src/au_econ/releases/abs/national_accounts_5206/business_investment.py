"""National Accounts business investment: one sector's contribution to growth in new private business investment.

The national accounts publish no quarterly industry split of investment, so each sector comes
from the private new capital expenditure survey (5625.0), as a contribution to that survey's
total, set against year-ended growth in 5206 new private business investment (the mixed-base
construction of the published Westpac chart).
"""

# --- dependencies
from typing import TYPE_CHECKING

import mgplot as mg
import pandas as pd
import readabs as ra
from mgplot import chart_subdir
from readabs import metacol as mc

from au_econ.releases.abs.national_accounts_5206.common import (
    AUSTRALIA,
    CVM_NOTE,
    EXPENDITURE_VOLUME,
    QUARTERS_PER_YEAR,
    SA_NOTE,
    SEASONALLY_ADJUSTED,
    data_to,
)

if TYPE_CHECKING:
    from au_econ.sources.abs import AbsRelease

# --- constants
SUBDIR = "Business-investment"
PERCENT = 100
CAPEX_CATALOGUE = "5625.0"
CAPEX_TABLE = "07_volume_measures_seasonally_adjusted_capex"
CAPEX_ALL_ASSETS = "Total (Type of Asset - Detailed Level)"
CAPEX_TOTAL = "Total, including Education and Health"
GFCF = "Private ;  Gross fixed capital formation - "
RECENT_FROM = "2019Q4"  # the span of the published chart
SECTORS = {  # sector: (capex survey description fragment, lfooter note)
    "IT": (
        "Information Media and Telecommunications",
        "IT = Information Media & Telecoms (capex survey). ",
    ),
    "Mining": (
        "Measures ;  Mining ;",  # avoids matching "Non-Mining, including ..."
        "Mining industry from the capex survey. ",
    ),
    "Transport": (
        "Transport, Postal and Warehousing",
        "Transport incl. postal & warehousing (capex survey). ",
    ),
    "Manufacturing": ("Manufacturing", "Manufacturing industry from the capex survey. "),
    "Electricity": (
        "Electricity, Gas, Water and Waste Services",
        "Electricity incl. gas, water & waste (capex survey). ",
    ),
}


# --- helpers
def _quarterly(series: pd.Series) -> pd.Series:
    """Return a series without gaps, on a Q-DEC index."""
    series = series.dropna()
    series.index = pd.PeriodIndex(series.index, freq="Q-DEC")
    return series


def _new_investment(release: AbsRelease) -> pd.Series:
    """Return new private business investment: total less net purchases of second-hand assets (CVM, SA)."""

    def series(did: str) -> pd.Series:
        _, series_id, _ = ra.find_abs_id(
            release.meta, {EXPENDITURE_VOLUME: mc.table, did: mc.did, SEASONALLY_ADJUSTED: mc.stype}
        )
        return _quarterly(release.data[EXPENDITURE_VOLUME][series_id])

    return (
        series(f"{GFCF}Total private business investment ;")
        - series(f"{GFCF}Non-dwelling construction - Net purchase of second hand assets ;")
        - series(f"{GFCF}Machinery and equipment - Net purchase of second hand assets ;")
    )


def _capex() -> tuple[pd.Series, dict[str, pd.Series]]:
    """Return the capex survey total and one series per sector (5625.0, CVM, SA)."""
    data, meta = ra.read_abs_cat(CAPEX_CATALOGUE, single_excel_only=CAPEX_TABLE, verbose=False)

    def series(industry: str) -> pd.Series:
        _, series_id, _ = ra.find_abs_id(meta, {CAPEX_TABLE: mc.table, CAPEX_ALL_ASSETS: mc.did, industry: mc.did})
        return _quarterly(data[CAPEX_TABLE][series_id])

    return series(CAPEX_TOTAL), {sector: series(fragment) for sector, (fragment, _) in SECTORS.items()}


# --- charts
def business_investment(release: AbsRelease) -> None:
    """Each sector's contribution against all other industries, full history and since 2019Q4."""
    total = _new_investment(release)
    capex_total, sectors = _capex()
    full_growth = (total.pct_change(QUARTERS_PER_YEAR) * PERCENT).dropna()
    full_growth.name = "Total"
    with chart_subdir(SUBDIR):
        for sector, series in sectors.items():
            sector_contribution = (
                (series - series.shift(QUARTERS_PER_YEAR)) / capex_total.shift(QUARTERS_PER_YEAR) * PERCENT
            ).reindex(full_growth.index)
            contributions = pd.DataFrame(
                {
                    f"{sector} sector": sector_contribution,
                    "Other industries": full_growth - sector_contribution,
                }
            ).dropna()
            growth = full_growth.reindex(contributions.index)
            for start, tag in ((None, ""), (RECENT_FROM, "recent")):
                bars, line = (
                    (contributions, growth) if start is None else (contributions.loc[start:], growth.loc[start:])
                )
                ax = mg.bar_plot(bars, stacked=True)
                mg.line_plot(line, ax=ax, color="navy", annotate=True, rounding=1)
                mg.finalise_plot(
                    ax,
                    title=f"New Private Business Investment: {sector} Sector Contribution",
                    ylabel="Year-ended growth (%, ppt)",
                    y0=True,
                    legend={"loc": "best", "fontsize": 9},
                    tag=tag,
                    rfooter=f"{release.source}, {CAPEX_CATALOGUE}",
                    lfooter=f"{AUSTRALIA}{SA_NOTE}{CVM_NOTE}{SECTORS[sector][1]}{data_to(bars)}",
                )


# --- table of contents, in run order
CHARTS = ((business_investment, ()),)
