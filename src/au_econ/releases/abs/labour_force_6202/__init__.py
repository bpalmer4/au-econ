"""Labour Force, Australia (6202.0): the monthly labour force survey.

Headline, unemployment, growth, breakeven, state, gender and revisions charts, and the
monthly detail that moved here from the ceased 6291.0.55.001 in April 2026: age groups,
capital cities and country of birth (the last two from the LMS data cubes). Only four
tables are read up front (see common.TABLES): the whole release is huge and slow to load.
"""

# --- dependencies
from au_econ.releases.abs.labour_force_6202 import (
    age,
    birthplace,
    breakeven,
    gender,
    growth,
    headline,
    regions,
    revisions,
    states,
    unemployment,
)
from au_econ.releases.abs.labour_force_6202.common import TABLES
from au_econ.sources.abs import AbsRelease, fetch_release

# --- module contract
RELEASE = ("6202", "lfs")
TOPICS = ("jobs",)
TITLE = "Labour Force"

# --- constants
CATALOGUE = "6202.0"


# --- data
def fetch() -> AbsRelease:
    """Fetch the three tables once; every chart function receives them."""
    return fetch_release(CATALOGUE, selected_excel=TABLES)


# --- table of contents, in run order
CHARTS = (
    *headline.CHARTS,
    *unemployment.CHARTS,
    *growth.CHARTS,
    *breakeven.CHARTS,
    *states.CHARTS,
    *gender.CHARTS,
    *age.CHARTS,
    *regions.CHARTS,
    *birthplace.CHARTS,
    *revisions.CHARTS,
)
