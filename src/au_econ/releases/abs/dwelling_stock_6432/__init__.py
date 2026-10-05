"""Total Value of Dwellings (6432.0): the dwelling stock, its value, and housing against population.

The stock, its value and mean price; people per dwelling; breakeven dwellings (national,
by state, extended back to 1981 from completions, and in 21+ terms); completions against
net additions; revisions; and dwelling values against earnings, prices and loan repayments.
"""

# --- dependencies
from au_econ.releases.abs.dwelling_stock_6432 import breakeven, revisions, stock, value
from au_econ.sources.abs import AbsRelease, fetch_release

# --- module contract
RELEASE = ("6432", "dwellings")
TOPICS = ("building",)
TITLE = "Dwelling Stock"

# --- constants
CATALOGUE = "6432.0"


# --- data
def fetch() -> AbsRelease:
    """Fetch the release once; every chart function receives it."""
    return fetch_release(CATALOGUE)


# --- table of contents, in run order
CHARTS = (
    *stock.CHARTS,
    *breakeven.CHARTS,
    *revisions.CHARTS,
    *value.CHARTS,
)
