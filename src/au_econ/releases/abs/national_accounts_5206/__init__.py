"""Australian National Accounts: National Income, Expenditure and Product (5206.0).

Headline charts first; the chart subfolders (deflators, wages and unit labour costs,
revisions, components, GDP composition, savings, industries, consumption, taxes,
benefits, productivity, business investment) join batch by batch.
"""

# --- dependencies
from dataclasses import replace

from readabs import metacol as mc

from au_econ.releases.abs.national_accounts_5206 import (
    business_investment,
    components,
    deflators,
    gdp_composition,
    government_benefits,
    gva_by_industry,
    headline,
    hfce,
    productivity,
    revisions,
    savings,
    taxes,
    wages_ulc,
)
from au_econ.sources.abs import AbsRelease, fetch_release

# --- module contract
RELEASE = ("5206", "gdp")
TOPICS = ("activity", "wages", "prices")
TITLE = "National Accounts"

# --- constants
CATALOGUE = "5206.0"
MOCK_UP = "Mock-up"  # placeholder tables the ABS ships with the release


# --- data
def fetch() -> AbsRelease:
    """Fetch the whole release once, without the mock-up tables; every chart function receives it."""
    release = fetch_release(CATALOGUE)
    return replace(release, meta=release.meta[~release.meta[mc.table].str.contains(MOCK_UP)])


# --- table of contents, in run order
CHARTS = (
    *headline.CHARTS,
    *deflators.CHARTS,
    *wages_ulc.CHARTS,
    *revisions.CHARTS,
    *components.CHARTS,
    *gdp_composition.CHARTS,
    *business_investment.CHARTS,
    *savings.CHARTS,
    *taxes.CHARTS,
    *government_benefits.CHARTS,
    *hfce.CHARTS,
    *gva_by_industry.CHARTS,
    *productivity.CHARTS,
)
