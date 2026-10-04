"""Labour Account charts against other sources: the Labour Force Survey and the Job Vacancies Survey."""

# --- dependencies
from typing import TYPE_CHECKING, Any

import pandas as pd
import readabs as ra
from mgplot import line_plot_finalise, multi_start
from readabs import metacol as mc

from au_econ.charting.windows import quarterly_plot_times
from au_econ.releases.abs.labour_account_6150.common import (
    DETAIL_TABLE,
    JVS_CATALOGUE,
    LA_FILLED_JOBS,
    LA_LABOUR_FORCE,
    LA_VACANCIES,
    LFS_CATALOGUE,
    LFS_EMPLOYED,
    LFS_LABOUR_FORCE,
    SUMMARY_TABLE,
    TOTAL,
    LabourAccountData,
    jvs_vacancies,
    la_series,
    la_series_ids,
    lfs_quarterly_mean,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

# --- constants
LA_EMPLOYED = f"Persons; Labour Account employed persons {TOTAL}"
LA_MAIN_JOB_HOLDERS = f"Persons; Labour Account main job holders {TOTAL}"
SA_LFOOTER = "Australia. Seasonally adjusted. "


# --- helpers
def _versus_lfs(
    data: LabourAccountData, stems: Sequence[str], lfs_series: pd.Series, title: str, **kwargs: Any
) -> None:
    """Plot seasonally adjusted Labour Account series against a Labour Force Survey comparator."""
    meta = data.account.meta
    series_ids = la_series_ids(data, list(stems))
    names = {k: meta.loc[meta[mc.id] == k, mc.did].iloc[0] for k in series_ids}
    frame = pd.concat(
        [data.account.data[DETAIL_TABLE][series_ids].rename(columns=names), lfs_series], axis=1
    ).sort_index()
    frame, units = ra.recalibrate(frame, "Thousands")
    multi_start(
        frame,
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title=title,
        ylabel=units,
        rfooter=f"{data.account.source}, {LFS_CATALOGUE}",
        lfooter=SA_LFOOTER,
        **kwargs,
    )


# --- charts
def filled_jobs_v_employed(data: LabourAccountData) -> None:
    """Labour Account filled jobs, employed persons and main job holders against LFS employed persons."""
    _versus_lfs(
        data,
        (LA_FILLED_JOBS, LA_EMPLOYED, LA_MAIN_JOB_HOLDERS),
        lfs_quarterly_mean(data, LFS_EMPLOYED),
        "Filled Jobs v Employed Persons",
    )


def labour_force_la_v_lfs(data: LabourAccountData) -> None:
    """Labour Account labour force against the Labour Force Survey labour force."""
    _versus_lfs(
        data,
        (LA_LABOUR_FORCE,),
        lfs_quarterly_mean(data, LFS_LABOUR_FORCE),
        "Labour Force: Labour Account v Labour Force Survey",
        dropna=True,
    )


def workforce_gap(data: LabourAccountData) -> None:
    """Labour Account labour force less the Labour Force Survey labour force, both in '000.

    Approximates the non-ERP component of the labour force: mainly non-residents working in
    Australia, net of residents temporarily overseas.
    """
    gap = (
        (la_series(data, LA_LABOUR_FORCE) - lfs_quarterly_mean(data, LFS_LABOUR_FORCE))
        .dropna()
        .to_frame(name="Workforce gap (LA labour force - LFS labour force)")
    )
    gap, units = ra.recalibrate(gap, "Thousands")
    line_plot_finalise(
        gap,
        title="Workforce gap: Labour Account minus LFS labour force",
        ylabel=units,
        rfooter=f"{data.account.source}, {LFS_CATALOGUE}",
        # abbreviated: the full wording runs into the rfooter
        lfooter="Australia. Seas adj. Approx. non-ERP labour force: mostly non-residents working here, "
        "net of residents overseas.",
        legend=False,
    )


def job_vacancies_comparison(data: LabourAccountData) -> None:
    """Job vacancies: the Job Vacancies Survey against the Labour Account."""
    meta = data.account.meta
    la_id = meta.loc[(meta[mc.table] == SUMMARY_TABLE) & (meta[mc.did] == LA_VACANCIES), mc.id].iloc[0]
    frame = pd.DataFrame(
        {"Job Vacancies Survey": jvs_vacancies(data), "Labour Account": data.account.data[SUMMARY_TABLE][la_id]}
    )
    index = frame.index
    if not isinstance(index, pd.PeriodIndex):
        raise TypeError(f"Expected a PeriodIndex, got {type(index).__name__}")
    frame = frame.reindex(pd.period_range(index.min(), index.max(), freq=index.freqstr))
    multi_start(
        frame,
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title="ABS Job Vacancies Survey v Labour Account",
        ylabel="Job Vacancies, Thousands",
        rfooter=f"{data.account.source}, {JVS_CATALOGUE}",
        lfooter=SA_LFOOTER + "Note: ABS Job Vacancies Survey data mapped from quarter ending Nov "
        "to quarter ending Dec.",
    )


# --- table of contents, in run order
CHARTS = (
    (job_vacancies_comparison, ()),
    (filled_jobs_v_employed, ()),
    (labour_force_la_v_lfs, ()),
    (workforce_gap, ()),
)
