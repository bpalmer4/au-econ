"""Consumer Price Index, Australia (6401.0): measures, expenditure classes and related series.

The related series bring in other releases: the discontinued monthly indicator 6484.0, PPI,
WPI, deflators, unemployment, nominal GDP, rents, wages and household income.
"""

# --- dependencies
from au_econ.releases.abs.consumer_price_index_6401 import classes, measures, related
from au_econ.sources.abs import AbsRelease, fetch_release

# --- module contract
RELEASE = ("6401", "cpi")
TOPICS = ("prices",)
TITLE = "Consumer Price Index"

# --- constants
CATALOGUE = "6401.0"


# --- data
def fetch() -> AbsRelease:
    """Fetch the whole release once; every chart function receives it."""
    return fetch_release(CATALOGUE)


# --- table of contents, in run order
CHARTS = (*measures.CHARTS, *classes.CHARTS, *related.CHARTS)
