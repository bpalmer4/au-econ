"""Labour Account, Australia (6150.0.55.003): jobs, persons, hours and payments, quarterly.

Headline series against their pre-COVID trend, growth by industry, industry shares of jobs,
comparisons with the Labour Force Survey and the Job Vacancies Survey, the efficient
unemployment rate, and labour productivity.
"""

# --- dependencies
from readabs import metacol as mc

from au_econ.releases.abs.labour_account_6150 import comparisons, efficiency, headline, productivity
from au_econ.releases.abs.labour_account_6150.common import (
    JVS_CATALOGUE,
    JVS_TABLE,
    LA_FILLED_JOBS,
    LA_TOTAL_JOBS,
    LA_VACANCIES,
    LFS_CATALOGUE,
    LFS_TABLE,
    SUMMARY_TABLE,
    LabourAccountData,
)
from au_econ.sources.abs import AbsRelease, fetch_release

# --- module contract
RELEASE = ("6150", "la")
TOPICS = ("jobs",)
TITLE = "Labour Account"

# --- constants
CATALOGUE = "6150.0.55.003"
IDENTITY_TOLERANCE = 0.0001  # '000 jobs


# --- data
def _check_jobs_identity(account: AbsRelease) -> None:
    """Check filled jobs plus job vacancies equals total jobs, every quarter."""
    meta = account.meta
    parts = {}
    for did in (LA_FILLED_JOBS, LA_VACANCIES, LA_TOTAL_JOBS):
        series_id = meta.loc[(meta[mc.table] == SUMMARY_TABLE) & (meta[mc.did] == did), mc.id].iloc[0]
        parts[did] = account.data[SUMMARY_TABLE][series_id]
    gap = parts[LA_FILLED_JOBS] + parts[LA_VACANCIES] - parts[LA_TOTAL_JOBS]
    misses = int((gap.abs() > IDENTITY_TOLERANCE).sum())
    if misses:
        raise ValueError(f"ABS {CATALOGUE}: filled jobs + vacancies != total jobs in {misses} quarters")


def fetch() -> LabourAccountData:
    """Fetch the Labour Account, check its jobs identity, and fetch its comparators."""
    account = fetch_release(CATALOGUE)
    _check_jobs_identity(account)
    return LabourAccountData(
        account=account,
        labour_force=fetch_release(LFS_CATALOGUE, single_excel_only=LFS_TABLE),
        vacancies=fetch_release(JVS_CATALOGUE, single_excel_only=JVS_TABLE),
    )


# --- table of contents, in run order
CHARTS = (
    *comparisons.CHARTS,
    *efficiency.CHARTS,
    *headline.CHARTS,
    *productivity.CHARTS,
)
