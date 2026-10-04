"""Job Vacancies, Australia (6354.0): vacancies and the vacancy rate, and the Beveridge curve.

Vacancies in total and by sector, industry and state. Quarterly, for the quarters ending
February, May, August and November. Vacancies by industry as a share of industry
employment are not here yet: industry employment came from 6291.0.55.001, which ceased at
2026Q1, and returns in 6202.0 later in 2026.
"""

# --- dependencies
from dataclasses import dataclass
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import readabs as ra
from mgplot import (
    bar_plot_finalise,
    finalise_plot,
    line_plot_finalise,
    postcovid_plot_finalise,
    series_growth_plot_finalise,
)
from readabs import metacol as mc

from au_econ.charting.abs_rows import recalibrated_rows
from au_econ.charting.footers import SERIES_TYPE_NOTES
from au_econ.charting.windows import quarterly_plot_times
from au_econ.sources.abs import AbsRelease, fetch_release

if TYPE_CHECKING:
    from matplotlib.axes import Axes

# --- module contract
RELEASE = ("6354", "jv")
TOPICS = ("jobs",)
TITLE = "Job Vacancies"

# --- constants
CATALOGUE = "6354.0"
HEADLINE_TABLE, INDUSTRY_TABLE = "6354001", "6354004"
LFS_CATALOGUE, LFS_TABLE = "6202.0", "62020001"
SEASONALLY_ADJUSTED, ORIGINAL = "Seasonally Adjusted", "Original"
VACANCIES_DID = "Job Vacancies ;  Australia ;"
LABOUR_FORCE_DID = "Labour force total ;  Persons ;"
UNEMPLOYMENT_RATE_DID = "Unemployment rate ;  Persons ;"
QUARTER_ENDING = "NOV"  # the survey's quarters end in February, May, August and November
PRE_COVID = (pd.Period("2009Q4", freq="Q"), pd.Period("2019Q4", freq="Q"))  # trend fitting period
NON_MARKET = ("Public Administration and Safety", "Education and Training", "Health Care and Social Assistance")
ALL_INDUSTRIES = "Total All Industries"
ROWS_SELECTOR = {ORIGINAL: mc.stype, "^Job Vacancies": mc.did}  # with a table, every vacancy series in it
INDUSTRY_TREND_FROM = pd.Period("2000Q1", freq="Q-NOV")
STATE_TREND = (pd.Period("2000Q1", freq="Q"), pd.Period("2019Q4", freq="Q"))
COMBINED_SOURCE = "ABS: 6202.0, 6354.0"  # for anything taken against the labour force
BEVERIDGE_FROM = "2010Q2"
CURVE_COLOUR, CURVE_WIDTH = "royalblue", 2
LABEL_EVERY = 4  # quarters between labelled points on the curve
POST_COVID_FIT = ("2020Q3", "2022Q2")
PRE_COVID_FIT = ("2020Q2", "2023Q3")  # fitted before the first and from the second
FIT_POINTS = 50
FIT_DEGREE = 2
# era label: (first quarter, last quarter or None for latest, colour)
BEVERIDGE_ERAS: dict[str, tuple[str, str | None, str]] = {
    "1990-2008": ("1990Q1", "2008Q4", "royalblue"),
    "2009-2019": ("2009Q1", "2019Q4", "darkorange"),
    "2020-now": ("2020Q1", None, "darkred"),
}
ERA_LINE_WIDTH = 1.5


# --- data
@dataclass(frozen=True)
class VacancyData:
    """The job vacancy release, and the Labour Force table its rates are taken against."""

    vacancies: AbsRelease
    labour_force: AbsRelease


def fetch() -> VacancyData:
    """Fetch the release, and Labour Force table 1 for the labour force and unemployment rate."""
    return VacancyData(
        vacancies=fetch_release(CATALOGUE),
        labour_force=fetch_release(LFS_CATALOGUE, single_excel_only=LFS_TABLE),
    )


# --- helpers
def _quarterly_lfs(data: VacancyData, did: str) -> pd.Series:
    """One seasonally adjusted Labour Force series, averaged over the survey's quarters."""
    release = data.labour_force
    _table, series_id, _units = ra.find_abs_id(
        release.meta,
        {LFS_TABLE: mc.table, did: mc.did, SEASONALLY_ADJUSTED: mc.stype},
        exact_match=True,
        verbose=False,
    )
    return ra.monthly_to_qtly(release.data[LFS_TABLE][series_id], q_ending=QUARTER_ENDING, f="mean")


def _vacancies(data: VacancyData) -> pd.Series:
    """Seasonally adjusted job vacancies, Australia."""
    release = data.vacancies
    table, series_id, _units = ra.find_abs_id(
        release.meta,
        {SEASONALLY_ADJUSTED: mc.stype, HEADLINE_TABLE: mc.table, VACANCIES_DID: mc.did},
        verbose=False,
    )
    return release.data[table][series_id]


def _industry_vacancies(release: AbsRelease) -> pd.DataFrame:
    """Vacancies by industry (Original), one column per industry, standard errors left out."""
    meta = release.meta
    rows = meta[(meta[mc.table] == INDUSTRY_TABLE) & (~meta[mc.did].str.contains("Standard Error"))]
    frame = release.data[INDUSTRY_TABLE][rows[mc.id]]
    frame.columns = pd.Index(rows[mc.did].str.split(";").str[1].str.strip())
    return frame


def _beveridge_frame(data: VacancyData) -> pd.DataFrame:
    """Quarterly unemployment rate and job vacancy rate, every quarter both exist."""
    unemployment = _quarterly_lfs(data, UNEMPLOYMENT_RATE_DID)
    vacancy_rate = _vacancies(data) / _quarterly_lfs(data, LABOUR_FORCE_DID) * 100
    return pd.DataFrame({"Unemployment Rate": unemployment, "Job Vacancy Rate": vacancy_rate}).dropna()


def _fit(ax: Axes, frame: pd.DataFrame, label: str, *, colour: str, linestyle: str) -> None:
    """Draw a quadratic fitted to the frame's (x, y) columns across their x range."""
    x, y = frame[frame.columns[0]], frame[frame.columns[1]]
    model = np.poly1d(np.polyfit(x, y, FIT_DEGREE))
    line = np.linspace(x.min(), x.max(), FIT_POINTS)
    ax.plot(line, model(line), color=colour, linestyle=linestyle, lw=0.75, label=label)


# --- charts
def headline(data: VacancyData) -> None:
    """Job vacancies and the job vacancy rate, each also against the pre-COVID trend."""
    labour_force = _quarterly_lfs(data, LABOUR_FORCE_DID)
    vacancies = _vacancies(data)
    vacancies = vacancies.reindex(pd.period_range(start=vacancies.index[0], end=labour_force.index[-1]))
    rate = vacancies / labour_force * 100
    lfooter = f"Australia. {SERIES_TYPE_NOTES[SEASONALLY_ADJUSTED]} "
    for series, ylabel, title, note, source in (
        (
            rate,
            "Job Vacancy Rate (%)",
            "Job Vacancy Rate",
            "Job Vacancy Rate = Job Vacancies / Labour Force. ",
            COMBINED_SOURCE,
        ),
        (vacancies, "Thousands", "Job Vacancies", "", data.vacancies.source),
    ):
        line_plot_finalise(
            series, dropna=False, rfooter=source, lfooter=lfooter + note, ylabel=ylabel, title=title
        )
        postcovid_plot_finalise(
            series,
            start_r=PRE_COVID[0],
            end_r=PRE_COVID[1],
            tag="-covid",
            rfooter=source,
            lfooter=lfooter + note,
            ylabel=ylabel,
            title=title,
        )


def sector_growth(data: VacancyData) -> None:
    """Growth in job vacancies: all sectors, the market sector and the non-market sector."""
    industries = _industry_vacancies(data.vacancies)
    non_market = list(NON_MARKET)
    sectors = {
        "All Sectors": industries[ALL_INDUSTRIES],
        "Market Sector": industries.loc[:, ~industries.columns.isin([*non_market, ALL_INDUSTRIES])].sum(axis=1),
        "Non-market Sector": industries[non_market].sum(axis=1),
    }
    for label, series in sectors.items():
        series_growth_plot_finalise(
            series,
            title=f"Growth in Job Vacancies: {label}",
            plot_from=quarterly_plot_times[-1],
            rfooter=data.vacancies.source,
            lfooter=f"Australia. {ORIGINAL} series. ",
            ylabel="Per cent",
        )


def industry_vacancies(data: VacancyData) -> None:
    """Job vacancies in each industry in the latest quarter."""
    industries = _industry_vacancies(data.vacancies)
    latest = industries.iloc[-1].drop(index=ALL_INDUSTRIES).sort_values(ascending=True)
    bar_plot_finalise(
        latest,
        horizontal=True,
        annotate=True,
        above=True,
        rounding=1,
        title="Job Vacancies by Industry Sector",
        xlabel="Thousands of Job Vacancies",
        lfooter=f"Australia. {SERIES_TYPE_NOTES[ORIGINAL]} Data for {industries.index[-1]}. ",
        rfooter=data.vacancies.source,
    )


def industry_recovery(data: VacancyData) -> None:
    """Vacancies in each industry against its trend from 2000."""
    for series, units, title in recalibrated_rows(
        data.vacancies, {**ROWS_SELECTOR, INDUSTRY_TABLE: mc.table}, regex=True
    ):
        postcovid_plot_finalise(
            series,
            title=title,
            ylabel=units,
            tag="Covid Recovery long run",
            start_r=INDUSTRY_TREND_FROM,
            rfooter=data.vacancies.source,
            lfooter=f"Australia. {ORIGINAL.capitalize()} series. ",
        )


def state_recovery(data: VacancyData) -> None:
    """Vacancies in each state, and Australia, against the 2000-2019 trend."""
    for series, units, title in recalibrated_rows(
        data.vacancies, {**ROWS_SELECTOR, HEADLINE_TABLE: mc.table}, regex=True
    ):
        postcovid_plot_finalise(
            series,
            title=title,
            ylabel=units,
            tag="Covid Recovery",
            start_r=STATE_TREND[0],
            end_r=STATE_TREND[1],
            rfooter=data.vacancies.source,
            lfooter=f"Australia. {ORIGINAL.capitalize()} series. ",
        )


def beveridge_curve(data: VacancyData) -> None:
    """Unemployment rate against the job vacancy rate from 2010, with stylised pre- and post-COVID curves.

    The pre-COVID curve also takes the quarters from 2023Q3, assuming the economy has
    returned to its pre-COVID equilibrium.
    """
    frame = _beveridge_frame(data).loc[lambda x: x.index >= BEVERIDGE_FROM]
    _fig, ax = plt.subplots()
    ax.plot(
        frame[frame.columns[0]],
        frame[frame.columns[1]],
        lw=CURVE_WIDTH,
        color=CURVE_COLOUR,
        label="Beveridge curve",
    )
    xs, ys = frame.iloc[:, 0].to_numpy(dtype=float), frame.iloc[:, 1].to_numpy(dtype=float)
    for n in [k for k in range(-1, -len(frame), -LABEL_EVERY) if k > -len(frame)]:
        ax.text(xs[n], ys[n], f"{frame.index[n]} ", fontsize="x-small", ha="right")
    before, after = PRE_COVID_FIT
    points = frame.loc[lambda x: x.index < before].index.union(frame.loc[lambda x: x.index >= after].index)
    _fit(ax, frame.loc[points], "Pre-COVID Beveridge curve (stylised)", colour="darkred", linestyle="--")
    first, last = POST_COVID_FIT
    points = frame.loc[lambda x: (x.index >= first) & (x.index <= last)].index
    _fit(
        ax,
        frame.loc[points],
        "Immediate post-COVID Beveridge curve (stylised)",
        colour="darkgreen",
        linestyle="-.",
    )
    finalise_plot(
        ax,
        title="Beveridge Curve: Unemployment Rate vs Job Vacancy Rate",
        ylabel="Job Vacancy Rate (%)",
        xlabel="Unemployment Rate (%)",
        lfooter="Australia. Seasonally adjusted. Unemployment rate is quarterly mean "
        "(quarters ending Feb, May, Aug, Nov).",
        rfooter=COMBINED_SOURCE,
        legend=True,
    )


def beveridge_eras(data: VacancyData) -> None:
    """Draw the Beveridge curve as a connected path, one colour per era.

    mgplot has no connected x-y line, so each era is drawn with matplotlib and the chart is
    finished with mgplot. The 2008Q3-2009Q3 survey suspension leaves a break between the
    first two eras.
    """
    frame = _beveridge_frame(data)
    index = frame.index
    if not isinstance(index, pd.PeriodIndex):
        raise TypeError(f"Expected a PeriodIndex, got {type(index).__name__}")
    freq = index.freqstr
    _fig, ax = plt.subplots()
    for label, (start, end, colour) in BEVERIDGE_ERAS.items():
        # compare as Periods: a string .loc slice on a Q-NOV index reads the string as a
        # calendar quarter and picks up the quarter before
        in_era = frame.index >= pd.Period(start, freq=freq)
        if end is not None:
            in_era &= frame.index <= pd.Period(end, freq=freq)
        era = frame.loc[in_era]
        ax.plot(
            era["Unemployment Rate"], era["Job Vacancy Rate"], color=colour, linewidth=ERA_LINE_WIDTH, label=label
        )
        for n in (0, -1):  # label each era's first and last quarter
            ax.text(
                era["Unemployment Rate"].iloc[n],
                era["Job Vacancy Rate"].iloc[n],
                f"{era.index[n]} ",
                fontsize="x-small",
                color=colour,
                ha="right",
            )
    finalise_plot(
        ax,
        title="Beveridge Curve: Three Eras",
        ylabel="Job Vacancy Rate (%)",
        xlabel="Unemployment Rate (%)",
        lfooter="Australia. Seasonally adjusted. Quarters ending Feb, May, Aug, Nov. "
        "No vacancy survey 2008Q3-2009Q3. ",
        rfooter=COMBINED_SOURCE,
        legend=True,
    )


# --- table of contents, in run order
CHARTS = (
    (headline, ()),
    (sector_growth, ()),
    (industry_vacancies, ()),
    (industry_recovery, ()),
    (state_recovery, ()),
    (beveridge_curve, ()),
    (beveridge_eras, ()),
)
