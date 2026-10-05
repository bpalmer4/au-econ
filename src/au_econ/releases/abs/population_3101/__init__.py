"""National, State and Territory Population (3101.0): the official Estimated Resident Population.

ERP and its components (births, deaths, natural increase, overseas migration), the states,
age profiles and cohort transitions, and population growth against two other estimates
(the civilian population aged 15+ from 6202.0, the National Accounts population) and
against the 3401.0 border-movement proxies for migration.
"""

# --- dependencies
from au_econ.releases.abs.population_3101 import ages, erp, growth
from au_econ.releases.abs.population_3101.common import PopulationData, load

# --- module contract
RELEASE = ("3101", "erp")
TOPICS = ("migration",)
TITLE = "Population"


# --- data
def fetch() -> PopulationData:
    """Fetch the tables once and derive the growth measures; every chart function receives them."""
    return load()


# --- table of contents, in run order
CHARTS = (
    *erp.CHARTS,
    *ages.CHARTS,
    *growth.CHARTS,
)
