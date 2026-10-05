"""Australian economic outcomes by Commonwealth government, from Menzies to Albanese.

Prices, labour, incomes, fiscal policy and interest rates, and population, each measured
government by government: averages, changes over the term, compound annual growth, and
levels indexed to each election. The epoch table and the epoch maths are in
analysis.epochs; election markers in charting.epochs.
"""

# --- dependencies
from typing import TYPE_CHECKING

from au_econ.analysis.epochs import get_governments
from au_econ.topics.political import incomes, labour, policy, population, prices

if TYPE_CHECKING:
    from pandas import DataFrame

# --- module contract
RELEASE = ("political",)
TOPICS = ("economy",)
TITLE = "Political"


# --- data
def fetch() -> DataFrame:
    """Return the government epochs; each chart function fetches its own (cached) series."""
    return get_governments()


# --- table of contents, in run order
CHARTS = (
    *prices.CHARTS,
    *labour.CHARTS,
    *incomes.CHARTS,
    *policy.CHARTS,
    *population.CHARTS,
)
