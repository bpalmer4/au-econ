"""National Accounts government benefits: social assistance payments, and benefits plus government consumption."""

# --- dependencies
from typing import TYPE_CHECKING

import pandas as pd
import readabs as ra
from mgplot import chart_subdir, line_plot_finalise
from readabs import metacol as mc

from au_econ.analysis.henderson import hma
from au_econ.releases.abs.national_accounts_5206.common import (
    AUSTRALIA,
    CP_NOTE,
    EXPENDITURE_CP,
    ORIGINAL,
    ORIGINAL_NOTE,
    data_to,
)
from au_econ.series.gdp import get_gdp

if TYPE_CHECKING:
    from au_econ.sources.abs import AbsRelease

# --- constants
SUBDIR = "Government-benefits"
PERCENT = 100
BENEFITS_TABLE = "5206023_Social_Assistance_Benefits"
CONTINUING_FROM = pd.Period("2006Q1", freq="Q")  # many series end here: chart only those still published
BENEFITS_FROM = -50  # about twelve years: payments shown since the series that continue past 2006
HENDERSON_TERMS = 13
TITLE_PREFIXES = (  # (published, title)
    ("General government - National ;  ", "Federal Govt: "),
    ("General government - State and local ;  ", "State or Local Govt: "),
    ("General government ;  ", "All Govt: "),
)
LEVELS = (  # (description prefix, chart label)
    ("General government - State and local ;  ", "State and Local Govt"),
    ("General government - National ;  ", "Federal Govt"),
    ("General government ;  ", "All Govt"),
)
CONSUMPTION = "Final consumption expenditure ;"
BENEFITS = "Total personal benefits payments ;"


# --- helpers
def _benefits_title(description: str) -> str:
    """Shorten a social assistance description for a chart title."""
    for published, short in TITLE_PREFIXES:
        description = description.replace(published, short)
    return description.replace(" ;", "")


def _with_trend(data: pd.Series, title: str, source: str) -> None:
    """Draw a per cent of GDP series with its Henderson trend."""
    line_plot_finalise(
        pd.DataFrame({"Series": data, f"HMA({HENDERSON_TERMS})": hma(data, HENDERSON_TERMS)}),
        title=title,
        ylabel="Per cent of GDP",
        rfooter=source,
        width=(1, 3),
        lfooter=f"{AUSTRALIA}{ORIGINAL_NOTE}{CP_NOTE}{data_to(data)}",
        pre_tag="govt-benefits-consumption-",
        annotate=(True, False),
    )


# --- charts
def benefits(release: AbsRelease) -> None:
    """Each social assistance benefit still published: level, and as a per cent of GDP."""
    meta = release.meta
    rows = meta[(meta[mc.table] == BENEFITS_TABLE) & (meta[mc.stype] == ORIGINAL)]
    gdp, gdp_units = get_gdp("CP", "SA")
    lfooter = f"{AUSTRALIA}{ORIGINAL_NOTE}{CP_NOTE}"
    with chart_subdir(SUBDIR):
        for _, row in rows.iterrows():
            if row[mc.unit].strip().lower() != gdp_units.strip().lower():
                raise ValueError(f"Benefit units {row[mc.unit]} do not match GDP units {gdp_units}")
            series = release.data[BENEFITS_TABLE][row[mc.id]]
            if CONTINUING_FROM not in series.index or pd.isna(series.loc[CONTINUING_FROM]):
                continue
            series = series.dropna()
            share = series / gdp * PERCENT
            series, units = ra.recalibrate(series, f"{row[mc.unit]} / Quarter")
            title = _benefits_title(row[mc.did])
            line_plot_finalise(
                series,
                plot_from=BENEFITS_FROM,
                title=title,
                pre_tag="payments-",
                ylabel=units,
                rfooter=release.source,
                lfooter=f"{lfooter}{data_to(series)}",
                annotate=True,
            )
            line_plot_finalise(
                share,
                title=title + " as a % GDP",
                pre_tag="payments-",
                ylabel="Per cent",
                rfooter=release.source,
                lfooter=f"{lfooter}{data_to(share)}",
                annotate=True,
            )


def benefits_plus_consumption(release: AbsRelease) -> None:
    """Social benefits, government consumption, and the two together, as a per cent of GDP, by level."""
    gdp, gdp_units = get_gdp("CP", "O")

    def original(table: str, did: str) -> pd.Series:
        _table, series_id, units = ra.find_abs_id(
            release.meta, {table: mc.table, ORIGINAL: mc.stype, did: mc.did, "$": mc.unit}, verbose=False
        )
        if units.strip().lower() != gdp_units.strip().lower():
            raise ValueError(f"{did} units {units} do not match GDP units {gdp_units}")
        return release.data[table][series_id].dropna()

    with chart_subdir(SUBDIR):
        for prefix, label in LEVELS:
            consumption = original(EXPENDITURE_CP, f"{prefix}{CONSUMPTION}")
            payments = original(BENEFITS_TABLE, f"{prefix}{BENEFITS}")
            source = release.source
            _with_trend(payments / gdp * PERCENT, f"{label}: social benefits (% of GDP)", source)
            _with_trend(consumption / gdp * PERCENT, f"{label}: government consumption (% of GDP)", source)
            _with_trend(
                payments.add(consumption, fill_value=0) / gdp * PERCENT,
                f"{label}: social benefits plus govt. consumption (% of GDP)",
                source,
            )


# --- table of contents, in run order
CHARTS = (
    (benefits, ()),
    (benefits_plus_consumption, ()),
)
