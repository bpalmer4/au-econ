"""Monthly Household Spending Indicator (5682.0): household spending, monthly and quarterly, and per adult.

The headline aggregates (monthly, current prices) and the quarterly chain volume measures;
spending by category and by state, and per person by state; real spending per adult
against National Accounts consumption.
"""

# --- dependencies
from au_econ.releases.abs.household_spending_5682 import categories, headline, per_adult
from au_econ.releases.abs.household_spending_5682.common import HouseholdSpending, load

# --- module contract
RELEASE = ("5682", "hsi")
TOPICS = ("economy",)
TITLE = "Household Spending"


# --- data
def fetch() -> HouseholdSpending:
    """Fetch the release once; every chart function receives it."""
    return load()


# --- table of contents, in run order
CHARTS = (
    *headline.CHARTS,
    *categories.CHARTS,
    *per_adult.CHARTS,
)
