"""National Accounts revisions: how recent prints revised GDP, GDP per capita, market sector GVA and population."""

# --- dependencies
import re
from typing import TYPE_CHECKING, Any

import pandas as pd
import readabs as ra
from mgplot import chart_subdir, revision_plot_finalise
from readabs import metacol as mc

from au_econ.releases.abs.national_accounts_5206.common import (
    AUSTRALIA,
    CVM_NOTE,
    KEY_AGGS,
    SA_NOTE,
    SEASONALLY_ADJUSTED,
)

if TYPE_CHECKING:
    from au_econ.sources.abs import AbsRelease

# --- constants
SUBDIR = "Revisions"
CATALOGUE = "5206.0"
PRINTS = 6  # the latest print and the five before it
GDP_DID = "Gross domestic product: Chain volume measures ;"
GDP_PC_DID = "GDP per capita: Chain volume measures ;"
REVISED = (
    "Gross domestic product: Chain volume measures - Percentage changes ;",
    "GDP per capita: Chain volume measures - Percentage changes ;",
    "Gross value added market sector: Chain volume measures - Percentage changes ;",
    GDP_DID,
    GDP_PC_DID,
    "Gross value added market sector: Chain volume measures ;",
)


# --- helpers
def _prints(did: str, stype: str) -> tuple[pd.DataFrame, str]:
    """Return one series from each of the latest prints of the key aggregates table, newest first."""
    revisions, units = pd.DataFrame(), ""
    history = None
    for _ in range(PRINTS):
        data, meta = ra.read_abs_cat(CATALOGUE, single_excel_only=KEY_AGGS, history=history)
        table, series_id, units = ra.find_abs_id(meta, {did: mc.did, stype: mc.stype})
        last = data[table].index[-1]
        revisions[f"ABS print for {last.strftime('%Y-%b')}"] = data[table][series_id]
        history = (last - 1).strftime("%b-%Y").lower()  # the print a quarter earlier
    return revisions, units


# --- charts
def revisions(release: AbsRelease) -> None:
    """Revisions across the latest six prints, and to the population they imply."""
    stype = SEASONALLY_ADJUSTED
    common: dict[str, Any] = {
        "rfooter": release.source,
        "pre_tag": "revisions",
        "y0": True,
        "lfooter": f"{AUSTRALIA}{SA_NOTE}{CVM_NOTE}",
        "legend": {"loc": "best", "fontsize": 9},
    }
    captured = {}
    with chart_subdir(SUBDIR):
        for did in REVISED:
            prints, units = ra.recalibrate(*_prints(did, stype))
            captured[did] = prints
            suffix = " Q/Q growth" if "Percentage changes" in did else ""
            revision_plot_finalise(
                data=prints,
                ylabel=units,
                title=f"Data revisions: {re.sub(':.*$', '', did)}{suffix}",
                **common,
            )

        population = captured[GDP_DID] / captured[GDP_PC_DID]
        revision_plot_finalise(
            data=population,
            ylabel="Million Persons",
            title="Data revisions: Implied population from National Accounts",
            **common,
        )
        revision_plot_finalise(
            data=population.diff(1),
            ylabel="Million Persons",
            title="Data revisions: Implied quarterly population growth (Nat Acc)",
            **common,
        )


# --- table of contents, in run order
CHARTS = ((revisions, ()),)
