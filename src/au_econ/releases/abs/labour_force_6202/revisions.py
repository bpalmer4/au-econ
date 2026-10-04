"""Labour Force data revisions: the headline series as published in each of the latest releases.

The ABS modernised the release in April 2026, renaming its tables (62020001 was 6202001).
Earlier releases cannot be read under the new names, so the walk back stops at the first
release that does not have the table; from the September 2026 release on, every print
charted is on the new schema.
"""

# --- dependencies
from functools import cache
from typing import TYPE_CHECKING

import pandas as pd
import readabs as ra
from mgplot import revision_plot_finalise
from readabs import metacol as mc
from readabs.download_cache import HttpError

from au_econ.charting.footers import SERIES_TYPE_NOTES
from au_econ.releases.abs.labour_force_6202.common import (
    CIVILIAN_POPULATION,
    EMPLOYED,
    EMPLOYMENT_RATIO,
    HOURS,
    HOURS_WORKED,
    LABOUR_FORCE,
    MAIN,
    ORIGINAL,
    PARTICIPATION_RATE,
    SEASONALLY_ADJUSTED,
    STYPE_SHORT,
    THREE_YEARS,
    TREND,
    UNEMPLOYED,
    UNEMPLOYMENT_RATE,
    did_words,
)

if TYPE_CHECKING:
    from au_econ.sources.abs import AbsRelease

# --- constants
CATALOGUE = "6202.0"
MAX_PRINTS = 6  # releases compared
ROUNDING = 2
SAMPLED = (TREND, SEASONALLY_ADJUSTED)
# (description, series types charted)
REVISED = (
    (EMPLOYMENT_RATIO, SAMPLED),
    (PARTICIPATION_RATE, SAMPLED),
    (EMPLOYED, SAMPLED),
    (UNEMPLOYMENT_RATE, SAMPLED),
    (UNEMPLOYED, SAMPLED),
    (LABOUR_FORCE, SAMPLED),
    (CIVILIAN_POPULATION, (ORIGINAL,)),
    (HOURS_WORKED, SAMPLED),
)


# --- helpers
@cache
def _prints(table: str) -> tuple[tuple[dict[str, pd.DataFrame], pd.DataFrame], ...]:
    """Fetch the table from the latest release and up to MAX_PRINTS - 1 before it, newest first (cached)."""
    prints: list[tuple[dict[str, pd.DataFrame], pd.DataFrame]] = []
    history = None
    for _ in range(MAX_PRINTS):
        try:
            data, meta = ra.read_abs_cat(CATALOGUE, single_excel_only=table, history=history, verbose=False)
        except HttpError:
            break  # a release from before the modernisation: no table under this name
        if table not in data:
            break
        prints.append((data, meta))
        history = (data[table].index[-1] - 1).strftime("%b-%Y").lower()
    if not prints:
        raise ValueError(f"ABS {CATALOGUE}: no release of table {table} found")
    return tuple(prints)


def _history(did: str, stype: str) -> tuple[pd.DataFrame, str]:
    """Return one series as published in each release, a column per release, with its units."""
    table = HOURS if did == HOURS_WORKED else MAIN
    repository, units = pd.DataFrame(), ""
    for data, meta in _prints(table):
        _table, series_id, units = ra.find_abs_id(
            meta, {did: mc.did, stype: mc.stype, table: mc.table}, verbose=False
        )
        repository[f"ABS print for {data[table].index[-1].strftime('%b-%Y')}"] = data[table][series_id]
    return repository, units


# --- charts
def revisions(release: AbsRelease) -> None:
    """Each headline series over the last three years, as published in each of the latest releases."""
    for did, stypes in REVISED:
        for stype in stypes:
            repository, units = _history(did, stype)
            repository, units = ra.recalibrate(repository.iloc[-THREE_YEARS:], units)
            revision_plot_finalise(
                repository,
                ylabel=units,
                title=f"Data Revisions: {did_words(did)} ({STYPE_SHORT[stype]})",
                rfooter=release.source,
                lfooter=f"Australia. {SERIES_TYPE_NOTES[stype]} ",
                legend={"loc": "best", "fontsize": 9},
                rounding=ROUNDING,
            )
            if did == CIVILIAN_POPULATION:
                growth, growth_units = ra.recalibrate(repository.diff(1), units)
                revision_plot_finalise(
                    growth,
                    ylabel=f"{growth_units} Month on Month Growth",
                    title=f"Data Revisions: {did_words(did.replace('  Persons ;', ''))} Growth",
                    rfooter=release.source,
                    lfooter=f"Australia. {SERIES_TYPE_NOTES[stype]} ",
                    legend={"loc": "best", "fontsize": "x-small"},
                    rounding=ROUNDING,
                )


# --- table of contents, in run order
CHARTS = ((revisions, ()),)
