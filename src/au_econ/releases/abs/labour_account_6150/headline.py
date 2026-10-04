"""Labour Account headline charts: each series against its pre-COVID trend, growth by industry, industry shares."""

# --- dependencies
import pandas as pd
import readabs as ra
from mgplot import chart_subdir, line_plot_finalise, postcovid_plot_finalise, summary_plot_finalise
from readabs import metacol as mc

from au_econ.releases.abs.labour_account_6150.common import (
    DETAIL_TABLE,
    PER_CENT,
    SEASONALLY_ADJUSTED,
    SUMMARY_TABLE,
    LabourAccountData,
)

# --- constants
TREND_START, TREND_END = pd.Period("2009Q4"), pd.Period("2019Q4")  # pre-COVID trend
PERCENT = "Percent"  # rates are left out of the headline charts
# (title, search term) for the growth summaries
SUMMARIES = (
    ("# Total Jobs", "Jobs; Total jobs ;  Australia ;"),
    ("# Job Vacancies", "Jobs; Job vacancies ;  Australia ;"),
    ("# Filled Jobs", "Jobs; Filled jobs ;  Australia ;"),
    ("# Hours worked", "Volume; Labour Account hours actually worked in all jobs ;"),
)
ALL_INDUSTRIES = "Total all industries"
MIN_JOB_SERIES = 2  # the total and at least one industry
INDUSTRY_SHARE_SUBDIR = "Industry share of filled jobs"
# description stem: (chart title label, y-axis label)
JOB_MEASURES = {
    "Jobs; Filled jobs ;  Australia ;  ": ("Filled Jobs", "Per cent of all filled jobs"),
    "Jobs; Total jobs ;  Australia ;  ": (
        "Total Jobs (Filled and Vacant)",
        "Per cent of all jobs (filled and vacant)",
    ),
}


# --- helpers
def _headline_title(did: str) -> str:
    """Shorten an all-industries description into a chart title."""
    return (
        did.replace(" ;  Australia ;  Total all industries ;", "")
        .replace(" per Labour Account", "\nper Labour Account")
        .replace(" ; ", ", ")
        .replace("; ", ": ")
    )


def _jobs_by_industry(data: LabourAccountData, stem: str) -> dict[str, pd.Series]:
    """Seasonally adjusted jobs ('000) for one measure, keyed by industry, plus the total."""
    meta = data.account.meta
    rows = meta[
        (meta[mc.table] == SUMMARY_TABLE)
        & meta[mc.did].str.startswith(stem)
        & (meta[mc.stype] == SEASONALLY_ADJUSTED)
    ]
    jobs = {
        did.removeprefix(stem).removesuffix(" ;"): data.account.data[SUMMARY_TABLE][sid].dropna()
        for sid, did in zip(rows[mc.id], rows[mc.did], strict=True)
    }
    if ALL_INDUSTRIES not in jobs or len(jobs) < MIN_JOB_SERIES:
        raise ValueError(f"{stem!r} by industry not found in {SUMMARY_TABLE}")
    empty = [name for name, series in jobs.items() if series.empty]
    if empty:
        raise ValueError(f"No {stem!r} data for: {empty}")
    return jobs


# --- charts
def headline(data: LabourAccountData) -> None:
    """Every all-industries series (other than rates) against its 2009Q4-2019Q4 trend."""
    meta = data.account.meta
    rows = meta[
        (meta[mc.table] == DETAIL_TABLE) & (meta[mc.stype] == SEASONALLY_ADJUSTED) & (meta[mc.unit] != PERCENT)
    ]
    for _, row in rows.iterrows():
        series, units = ra.recalibrate(data.account.data[DETAIL_TABLE][row[mc.id]], row[mc.unit])
        if not isinstance(series, pd.Series):
            raise TypeError(f"recalibrate returned {type(series).__name__}")
        series = series.rename(f"{SEASONALLY_ADJUSTED.capitalize()} series")
        if series.dropna().index[0] > TREND_START:  # too short for the trend
            continue
        postcovid_plot_finalise(
            series,
            title=_headline_title(row[mc.did]),
            tag="covid",
            ylabel=units,
            start_r=TREND_START,
            end_r=TREND_END,
            rfooter=data.account.source,
            lfooter="Australia. All industries. ",
        )


def growth_summary(data: LabourAccountData) -> None:
    """Quarterly growth by industry, as z-scores and z-scaled: total jobs, vacancies, filled jobs and hours."""
    meta, table = data.account.meta, data.account.data[SUMMARY_TABLE]
    for title, search_term in SUMMARIES:
        found = ra.search_abs_meta(meta, {SUMMARY_TABLE: mc.table, search_term: mc.did})
        labels = found[mc.did].str.rsplit(pat=" ;  ", n=1).str[-1].str.replace(" ;", "")
        summary = pd.DataFrame()
        for label, series_id in zip(labels, labels.index, strict=True):
            summary[label] = table[series_id].pct_change(periods=1, fill_method=None) * 100
        summary_plot_finalise(
            summary,
            title=f"Q/Q Growth {title} {table.index[-1]}",
            rfooter=data.account.source,
            lfooter="Australia. Seasonally adjusted. All data is Q/Q percentage growth. ",
        )


def industry_shares(data: LabourAccountData) -> None:
    """Each industry's share of all filled jobs, and of all jobs (filled and vacant), in a subfolder."""
    with chart_subdir(INDUSTRY_SHARE_SUBDIR):
        for stem, (label, ylabel) in JOB_MEASURES.items():
            jobs = _jobs_by_industry(data, stem)
            total = jobs.pop(ALL_INDUSTRIES)
            for industry, industry_jobs in jobs.items():
                line_plot_finalise(
                    (industry_jobs / total * PER_CENT).dropna().rename(industry),
                    title=f"Share of {label}: {industry}",
                    ylabel=ylabel,
                    annotate=True,
                    legend=False,
                    lfooter="Australia. Seasonally adjusted. ",
                    rfooter=data.account.source,
                )


# --- table of contents, in run order
CHARTS = (
    (growth_summary, ()),
    (industry_shares, ()),
    (headline, ()),
)
