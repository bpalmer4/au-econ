"""Shared pieces of the Labour Force module: tables, descriptions, windows and series lookup."""

# --- dependencies
from typing import TYPE_CHECKING

import readabs as ra
from readabs import metacol as mc

if TYPE_CHECKING:
    import pandas as pd

    from au_econ.sources.abs import AbsRelease

# --- tables: the whole release is huge and slow to load, so only these are read
MAIN = "62020001"  # labour force status by sex, Australia
HOURS = "62020017"  # hours worked by state and sex
UNDERUTILISED = "62020X28"  # underutilised persons by state and sex; also the state employment series
AGE = "62020011"  # labour force status by age and sex, Original (was 6291.0.55.001 table 1)
TABLES = (MAIN, HOURS, UNDERUTILISED, AGE)

# --- series types and units
TREND, SEASONALLY_ADJUSTED, ORIGINAL = "Trend", "Seasonally Adjusted", "Original"
THOUSANDS, PERCENT = "000", "Percent"
STYPE_SHORT = {SEASONALLY_ADJUSTED: "Seas Adj", TREND: "Trend", ORIGINAL: "Orig"}  # for titles

# --- data item descriptions
EMPLOYED = "Employed total ;  Persons ;"
UNEMPLOYED = "Unemployed total ;  Persons ;"
LABOUR_FORCE = "Labour force total ;  Persons ;"
CIVILIAN_POPULATION = "Civilian population aged 15 years and over ;  Persons ;"
UNEMPLOYMENT_RATE = "Unemployment rate ;  Persons ;"
PARTICIPATION_RATE = "Participation rate ;  Persons ;"
HOURS_WORKED = "Monthly hours worked in all jobs ;  Persons ;"
EMPLOYMENT_RATIO = "Employment to population ratio ;  Persons ;"
UNDEREMPLOYED = "Underemployed total ;  Persons ;"
UNDEREMPLOYMENT_RATIO = "Underemployment ratio (proportion of employed) ;  Persons ;"
UNDERUTILISATION_RATE = "Underutilisation rate ;  Persons ;"

STATES = (
    "New South Wales",
    "Victoria",
    "Queensland",
    "South Australia",
    "Western Australia",
    "Tasmania",
    "Northern Territory",
    "Australian Capital Territory",
)

# --- chart windows
line_starts = 0, -40  # four years and a bit
THREE_YEARS = 37  # months shown by the short charts: three years plus the month growth starts from


def get_series(
    release: AbsRelease,
    table: str,
    did: str,
    stype: str,
    *,
    exact_match: bool = False,
) -> tuple[pd.Series, str]:
    """Return one series from the release, selected by table, description and series type, with its units."""
    _table, series_id, units = ra.find_abs_id(
        release.meta,
        {table: mc.table, did: mc.did, stype: mc.stype},
        exact_match=exact_match,
        verbose=False,
    )
    return release.data[table][series_id], units


MINOR_WORDS = frozenset(  # left lower case in titles, except as the first word
    {"a", "an", "and", "as", "at", "by", "for", "in", "of", "on", "or", "over", "the", "to", "vs"}
)


def title_case(text: str) -> str:
    """Capitalise each word except minor ones (after the first), leaving the rest of each word as is."""
    words = text.split(" ")
    return " ".join(
        word if (i and word.lower() in MINOR_WORDS) or not word else word[0].upper() + word[1:]
        for i, word in enumerate(words)
    )


def did_words(did: str) -> str:
    """Turn an ABS data item description into plain title words ("Employed Total Persons")."""
    return title_case(did.replace(" ;", "").replace("  ", " ").strip())
