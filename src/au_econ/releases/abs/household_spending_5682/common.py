"""Shared pieces of the Household Spending module: the release and its quarterly table."""

# --- dependencies
from dataclasses import dataclass

import pandas as pd
import readabs as ra
from readabs import metacol as mc

from au_econ.sources.abs import AbsRelease, fetch_release

# --- constants
CATALOGUE = "5682.0"
QUARTERLY_TABLE = "5682015"
MONTH, QUARTER = "Month", "Quarter"
SA = "Seasonally Adjusted"
TOTAL = "Total (Household Spending Categories)"


def category(did: str) -> str:
    """Return the spending category in a data item description ("Total" for the total)."""
    name = did.split(";")[1].strip()
    return "Total" if name == TOTAL else name


@dataclass(frozen=True)
class HouseholdSpending:
    """The monthly release, and the quarterly tables (empty when no quarterly release could be found)."""

    release: AbsRelease
    q_data: dict[str, pd.DataFrame]
    q_meta: pd.DataFrame


def load() -> HouseholdSpending:
    """Fetch the release; take the quarterly table from the latest quarter-end release.

    The quarterly tables only ship with the catalogue when the monthly release lands on a
    quarter-end month; otherwise they come from the previous quarter-end release.
    """
    release = fetch_release(CATALOGUE)
    meta = release.meta
    monthly_end = meta[meta[mc.freq] == MONTH][mc.end]
    print(f"Monthly to: {monthly_end.iloc[0].strftime('%B-%Y')}")
    if QUARTER in meta[mc.freq].to_numpy():
        q_data, q_meta = release.data, meta
    else:
        prev_q_end = pd.Period(monthly_end.max(), freq="M").asfreq("Q") - 1
        history = prev_q_end.asfreq("M", how="end").strftime("%b-%Y").lower()
        q_data, q_meta = ra.read_abs_cat(CATALOGUE, history=history, single_excel_only=QUARTERLY_TABLE)
    if QUARTER in q_meta[mc.freq].to_numpy():
        print(f"Quarterly to: {q_meta[q_meta[mc.freq] == QUARTER].iloc[0][mc.end].strftime('%B-%Y')}")
    else:
        q_data, q_meta = {}, pd.DataFrame()
    return HouseholdSpending(release=release, q_data=q_data, q_meta=q_meta)
