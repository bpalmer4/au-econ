"""National Accounts implicit price deflators: growth in every published deflator."""

# --- dependencies
import textwrap
from typing import TYPE_CHECKING, Any

from mgplot import calc_growth, chart_subdir, line_plot_finalise, series_growth_plot_finalise
from readabs import metacol as mc

from au_econ.charting.targets import ANNUAL_CPI_TARGET_RANGE, QUARTERLY_CPI_TARGET
from au_econ.charting.windows import quarterly_plot_times
from au_econ.releases.abs.national_accounts_5206.common import AUSTRALIA, DEFLATORS, SA_NOTE, data_to

if TYPE_CHECKING:
    import pandas as pd

    from au_econ.sources.abs import AbsRelease

# --- constants
SUBDIR = "Deflators"
TITLE_WIDTH = 66
PERCENTAGE_CHANGES = "Percentage changes"  # the published growth duplicates: growth is calculated here
HEADLINE = (  # also drawn in the main folder
    "GROSS DOMESTIC PRODUCT ;",
    "Gross national expenditure ;",
    "Households ;  Final consumption expenditure ;",
)
GROWTH_FROM = quarterly_plot_times[1]


# --- helpers
def _title(did: str) -> str:
    """Return the chart title for a deflator ("Private: Gross fixed capital formation")."""
    name = did.rstrip(" ;").replace(" ;  ", ": ")
    if name.isupper():
        name = name.title()
    return f"Growth in {name} Implicit Price Deflator"


def _growth_chart(series: pd.Series, title: str, common: dict[str, Any]) -> None:
    """Draw quarterly growth bars with the annual growth line, against the inflation target."""
    series_growth_plot_finalise(
        series,
        axhspan=ANNUAL_CPI_TARGET_RANGE,
        axhline=QUARTERLY_CPI_TARGET,
        title=textwrap.fill(title, width=TITLE_WIDTH),
        plot_from=GROWTH_FROM,
        tag="deflators-growth",
        zero_y=True,
        **common,
    )


# --- charts
def deflators(release: AbsRelease) -> None:
    """Quarterly and annual growth in every published deflator; the headline three also in the main folder."""
    meta = release.meta
    rows = meta[(meta[mc.table] == DEFLATORS) & ~meta[mc.did].str.contains(PERCENTAGE_CHANGES)]
    headline = []
    with chart_subdir(SUBDIR):
        for _, row in rows.iterrows():
            series = release.data[DEFLATORS][row[mc.id]].dropna()
            if series.empty:
                continue
            common: dict[str, Any] = {
                "rfooter": release.source,
                "lfooter": f"{AUSTRALIA}{SA_NOTE}{data_to(series)}",
                "legend": {"loc": "best", "fontsize": "xx-small"},
                "pre_tag": "deflators-",
            }
            title = _title(row[mc.did])
            _growth_chart(series, title, common)
            if row[mc.did] in HEADLINE:
                headline.append((series, title, common))

            growth = calc_growth(series)
            line_plot_finalise(
                growth[growth.columns[0]].rename(title),
                axhspan=ANNUAL_CPI_TARGET_RANGE,
                title=textwrap.fill(f"Annual {title}", width=TITLE_WIDTH),
                ylabel="Per cent growth",
                tag="deflators-growth-annual",
                annotate=True,
                y0=True,
                **common,
            )
    for series, title, common in headline:
        _growth_chart(series, title, common)


# --- table of contents, in run order
CHARTS = ((deflators, ()),)
