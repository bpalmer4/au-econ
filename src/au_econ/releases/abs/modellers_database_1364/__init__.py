"""Modellers' Database (1364.0.15.003): the fuller productivity assessment.

Released a few days after the National Accounts, so it builds on 5206.0 as well: labour and
multifactor productivity with the official capital stock, growth accounting, capital deepening,
business investment, capex, credit and lending, and Okun's law. 5206 keeps its own earlier,
rougher productivity charts.
"""

# --- dependencies
from readabs import metacol as mc

from au_econ.releases.abs.modellers_database_1364 import capital, investment, okun, productivity
from au_econ.releases.abs.modellers_database_1364.common import ModellersData, used_often
from au_econ.sources.abs import fetch_release

# --- module contract
RELEASE = ("1364", "mdb")
TOPICS = ("economy",)
TITLE = "Modellers' Database"

# --- constants
NATIONAL_ACCOUNTS = "5206.0"
MOCK_UP = "Mock-up"  # placeholder tables the ABS ships with the National Accounts


# --- data
def fetch() -> ModellersData:
    """Fetch the National Accounts (without the mock-up tables) and the series several charts share."""
    release = fetch_release(NATIONAL_ACCOUNTS)
    meta = release.meta[~release.meta[mc.table].str.contains(MOCK_UP)]
    return ModellersData(data=release.data, meta=meta, source=release.source, used=used_often(release.data, meta))


# --- table of contents, in run order
CHARTS = (*productivity.CHARTS, *capital.CHARTS, *investment.CHARTS, *okun.CHARTS)
