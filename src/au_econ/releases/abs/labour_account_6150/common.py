"""Shared pieces of the Labour Account module: the data, tables, descriptions and comparator series."""

# --- dependencies
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pandas as pd
import readabs as ra
from readabs import metacol as mc

if TYPE_CHECKING:
    from au_econ.sources.abs import AbsRelease

# --- tables and descriptions
DETAIL_TABLE = "6150055003DO001"  # total all industries: trend, seasonally adjusted and original
SUMMARY_TABLE = "Industry summary table"  # by industry division, seasonally adjusted
LFS_CATALOGUE, LFS_TABLE = "6202.0", "62020001"
JVS_CATALOGUE, JVS_TABLE = "6354.0", "6354001"
SEASONALLY_ADJUSTED, THOUSANDS = "Seasonally Adjusted", "000"
TOTAL = ";  Australia ;  Total all industries ;"  # ends each all-industries description
LA_LABOUR_FORCE = f"Persons; Labour Account labour force {TOTAL}"
LA_UNEMPLOYED = f"Persons; Labour Force Survey unemployed persons {TOTAL}"
LA_VACANCIES = f"Jobs; Job vacancies {TOTAL}"
LA_FILLED_JOBS = f"Jobs; Filled jobs {TOTAL}"
LA_TOTAL_JOBS = f"Jobs; Total jobs {TOTAL}"
LFS_LABOUR_FORCE = "Labour force total ;  Persons ;"
LFS_EMPLOYED = "Employed total ;  Persons ;"
LFS_UNEMPLOYED = "Unemployed total ;  Persons ;"
JVS_VACANCIES = "Job Vacancies ;  Australia ;"
PER_CENT = 100


# --- data
@dataclass(frozen=True)
class LabourAccountData:
    """The Labour Account, and the releases it is compared with."""

    account: AbsRelease
    labour_force: AbsRelease  # 6202.0 table 1
    vacancies: AbsRelease  # 6354.0 table 1


# --- helpers
def lfs_quarterly_mean(data: LabourAccountData, did: str) -> pd.Series:
    """One seasonally adjusted Labour Force Survey series, as a quarterly mean."""
    release = data.labour_force
    table, series_id, _units = ra.find_abs_id(
        release.meta, {LFS_TABLE: mc.table, did: mc.did, SEASONALLY_ADJUSTED: mc.stype}, verbose=False
    )
    series = ra.monthly_to_qtly(release.data[table][series_id], f="mean")
    series.name = f"{did} (Labour Force Survey, quarterly mean)"
    return series


def jvs_vacancies(data: LabourAccountData) -> pd.Series:
    """Seasonally adjusted job vacancies from the vacancy survey, moved onto December-ending quarters.

    The survey's quarters end in November; relabelling them puts them on the Labour
    Account's quarters, so the series share an index.
    """
    release = data.vacancies
    table, series_id, _units = ra.find_abs_id(
        release.meta, {JVS_TABLE: mc.table, JVS_VACANCIES: mc.did, SEASONALLY_ADJUSTED: mc.stype}, verbose=False
    )
    series = release.data[table][series_id].copy()
    if series.dropna().empty:
        raise ValueError(f"No job vacancies data found in {JVS_CATALOGUE} {JVS_TABLE}")
    series.index = pd.PeriodIndex(series.index, freq="Q-DEC")
    return series


def la_series_ids(data: LabourAccountData, stems: list[str]) -> pd.Series:
    """Seasonally adjusted all-industries Labour Account series IDs ('000) for the given descriptions."""
    meta = data.account.meta
    return meta[
        (meta[mc.table] == DETAIL_TABLE)
        & (meta[mc.did].isin(stems))
        & (meta[mc.stype] == SEASONALLY_ADJUSTED)
        & (meta[mc.unit] == THOUSANDS)
    ][mc.id]


def la_series(data: LabourAccountData, did: str) -> pd.Series:
    """One seasonally adjusted all-industries Labour Account series ('000)."""
    return data.account.data[DETAIL_TABLE][la_series_ids(data, [did]).iloc[0]]
