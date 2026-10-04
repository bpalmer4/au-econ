"""Chart helpers for ABS metadata rows: titles from data item descriptions, and one series per row."""

from typing import TYPE_CHECKING

import pandas as pd
import readabs as ra
from readabs import metacol as mc

if TYPE_CHECKING:
    from au_econ.sources.abs import AbsRelease


def abs_title(did: str) -> str:
    """Turn an ABS data item description into a chart title ("Employed total: Persons")."""
    return did.replace(" ;  ", ": ").replace(" ;", "")


def recalibrated_rows(
    release: AbsRelease, selector: dict[str, str], *, regex: bool = False
) -> list[tuple[pd.Series, str, str]]:
    """Return each series the selector finds, recalibrated: (series, units, chart title).

    Each series is named for its type ("Seasonally adjusted series"), for the legend.
    """
    rows = ra.search_abs_meta(release.meta, selector, regex=regex)
    found = []
    for _, row in rows.iterrows():
        series, units = ra.recalibrate(release.data[row[mc.table]][row[mc.id]], row[mc.unit])
        if not isinstance(series, pd.Series):
            raise TypeError(f"recalibrate returned {type(series).__name__} for {row[mc.id]}")
        found.append((series.rename(f"{row[mc.stype].capitalize()} series"), units, abs_title(row[mc.did])))
    return found
