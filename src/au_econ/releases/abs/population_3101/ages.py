"""Age profiles (3101.0): distributions and median ages by jurisdiction and sex, and cohort age transitions."""

# --- dependencies
from functools import cache
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import readabs as ra
from mgplot import abbreviate_state, finalise_plot, get_color, line_plot, line_plot_finalise
from readabs import metacol as mc

from au_econ.analysis.henderson import hma
from au_econ.releases.abs.population_3101.common import (
    AGE_TABLES,
    AUSTRALIA_AGE_TABLE,
    GROUPS,
    HMA_SMOOTHER,
    LINESTYLES,
    PERCENT,
    SOURCE_3101,
    SOURCE_LIFE_TABLES,
    STATE_COLORS,
    PopulationData,
    recalibrated,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

# --- constants
HALF = 0.5
AGE_LEGEND = {"loc": "best", "fontsize": "small", "ncols": 3}
GENDER_COLORS = ["hotpink", "cornflowerblue"]
OPEN_AGE, OPEN_AGE_TEXT = "100", "100 and over"

# cohort transitions
END_YEARS = (2023, 2024, 2025)
MAX_AGE = 99  # 100 is the open "100 and over" bucket, not a clean cohort
AGE_TICKS: list[float | int | pd.Period] = [float(age) for age in range(0, 101, 10)]
RESIDUAL_AGE = 70  # above it true net migration is about zero: the line is residual noise
TRANSITION_WIDTHS = [2, 1.5, 1.5]
LIFE_TABLE_PAGE = "https://www.abs.gov.au/statistics/people/population/life-expectancy/latest-release"
LIFE_TABLE_CUBE = "3302055001DO001"
LIFE_TABLE_SHEET = "Table 9"  # Australia
MALE_QX_COLUMN, FEMALE_QX_COLUMN = 2, 6  # col 0 age; males lx qx Lx ex in 1-4; females in 5-8
BOX_QUANTILES = (0.10, 0.25, 0.50, 0.75, 0.90)
TRANSITION_LFOOTER = (
    f"Australia. Persons. Mean of cohort transitions ending June {END_YEARS[0]}-{END_YEARS[-1]}. "
    f"Ages 1-{MAX_AGE}. "
)


# --- helpers
def age_data(data: PopulationData, table: str, group: str) -> tuple[str, pd.DataFrame]:
    """Return a table's age distribution for one group (Female, Male, Persons), with the abbreviated state."""
    meta = data.age_meta
    relevant = meta[(meta[mc.table] == table) & meta[mc.did].str.contains(group)]
    state = abbreviate_state(str(relevant["Table Description"].iloc[0]).split(",")[-1].strip())
    ages = relevant[mc.did].str.rsplit(";", n=2).str[-2].str.replace(OPEN_AGE_TEXT, OPEN_AGE).astype(int)
    frame = data.age_data[table][relevant[mc.id]]
    return state, pd.DataFrame(frame.to_numpy(), columns=ages, index=frame.index)


def _medians(frame: pd.DataFrame) -> pd.Series:
    """Return the interpolated median age of each row of an age distribution."""
    cumulative = frame.div(frame.sum(axis=1), axis=0).cumsum(axis=1)
    whole = cumulative.gt(HALF).idxmax(axis=1) - 1
    low = pd.Series(
        {row: cumulative.loc[row, age] for row, age in zip(whole.index, whole.to_numpy(), strict=True)}
    )
    high = pd.Series(
        {row: cumulative.loc[row, age + 1] for row, age in zip(whole.index, whole.to_numpy(), strict=True)}
    )
    return whole + (HALF - low) / (high - low)


@cache
def _life_table_qx() -> pd.DataFrame:
    """Fetch the probability of dying within the year (qx) by single year of age, Australia, by sex.

    The life-table cube is not in the ABS time series directory, so it is read from the
    Life expectancy release page; Table 9 is Australia.
    """
    grabbed = ra.grab_abs_url(url=LIFE_TABLE_PAGE, single_excel_only=LIFE_TABLE_CUBE)
    key = next(k for k in grabbed if "DO001" in k and k.rsplit("---", 1)[-1].strip() == LIFE_TABLE_SHEET)
    raw = grabbed[key]
    age = pd.to_numeric(raw.iloc[:, 0], errors="coerce")
    body = raw[age.notna()]  # header and unit rows carry a non-numeric age
    qx = pd.DataFrame(
        {
            "Male": pd.to_numeric(body.iloc[:, MALE_QX_COLUMN]).to_numpy(),
            "Female": pd.to_numeric(body.iloc[:, FEMALE_QX_COLUMN]).to_numpy(),
        },
        index=age.dropna().astype(int).to_numpy(),
    )
    qx.index.name = "Age"
    return qx


def _weighted_age_quantiles(weights: pd.Series, quantiles: Sequence[float]) -> np.ndarray:
    """Return the ages at cumulative-weight quantiles of a non-negative, age-indexed series."""
    clipped = weights.clip(lower=0).sort_index()
    cumulative = (clipped.cumsum() - HALF * clipped) / clipped.sum()
    return np.interp(quantiles, cumulative.to_numpy(), clipped.index.to_numpy(dtype=float))


def _australia(data: PopulationData, group: str) -> pd.DataFrame:
    return age_data(data, AUSTRALIA_AGE_TABLE, group)[1].sort_index(axis=1)


def _june(year: int) -> pd.Period:
    """Return the year to June, the reference period of the single-year-of-age tables."""
    return pd.Period(str(year), freq="Y-JUN")


def _june_row(frame: pd.DataFrame, period: pd.Period) -> pd.Series:
    """Return one year's age distribution; raise if the year is missing."""
    rows = frame[frame.index == period]
    if rows.empty:
        raise ValueError(f"No age distribution for {period}")
    return rows.iloc[0]


def _by_age(frame: pd.DataFrame) -> pd.DataFrame:
    """Return the frame on a RangeIndex of age, which mgplot can plot; the ages must be contiguous."""
    ages = range(int(frame.index.min()), int(frame.index.max()) + 1)
    if list(frame.index) != list(ages):
        raise ValueError("Expected contiguous ages in order")
    return frame.set_axis(pd.RangeIndex(ages.start, ages.stop), axis=0)


# --- charts
def state_age_profiles(data: PopulationData) -> None:
    """Chart the latest population distribution by age for each jurisdiction (Female, Male, Persons)."""
    for group in GROUPS:
        compositions = {}
        period = None
        for table in AGE_TABLES:
            state, frame = age_data(data, table, group)
            period = frame.index[-1]
            latest = frame.iloc[-1]
            compositions[state] = hma(latest / latest.sum() * PERCENT, HMA_SMOOTHER)
        profiles = _by_age(pd.DataFrame(compositions))
        axes = line_plot(
            profiles,
            color=[STATE_COLORS[state] for state in profiles.columns],
            style=LINESTYLES[: len(profiles.columns)],
        )
        finalise_plot(
            axes,
            title=f"Population distribution by Age and Jurisdiction ({group})",
            ylabel="Kernel Density Estimate (%)",
            xlabel="Age in whole years",
            legend=AGE_LEGEND,
            tag=group,
            lfooter=f"Australia. {period}",
            rfooter=SOURCE_3101,
            pre_tag="erp",
        )


def median_age_by_state(data: PopulationData) -> None:
    """Chart median age over time by jurisdiction (Female, Male, Persons)."""
    for group in GROUPS:
        medians = {}
        for table in AGE_TABLES:
            state, frame = age_data(data, table, group)
            medians[state] = _medians(frame)
        frame = pd.DataFrame(medians)
        line_plot_finalise(
            frame,
            color=[get_color(state) for state in frame.columns],
            style=LINESTYLES,
            title=f"Median Population Age by Jurisdiction ({group})",
            ylabel="Years",
            xlabel=None,
            legend=AGE_LEGEND,
            lfooter="Australia. ",
            rfooter=SOURCE_3101,
            pre_tag="erp",
        )


def age_gender_profiles(data: PopulationData) -> None:
    """Chart median age by sex for each state and territory."""
    for table in AGE_TABLES:
        medians = {}
        state = ""
        for group in GROUPS[0:2]:  # Female, Male (Persons is last)
            state, frame = age_data(data, table, group)
            medians[group] = _medians(frame)
        line_plot_finalise(
            pd.DataFrame(medians),
            color=GENDER_COLORS,
            title=f"Median Population Age by Gender for {state}",
            ylabel="Years",
            rfooter=SOURCE_3101,
            lfooter="Australia. ",
            annotate=True,
            pre_tag="erp",
        )


def age_transition_profile(data: PopulationData) -> None:
    """Chart the average annual cohort change by age: ERP(a, June t) less ERP(a-1, June t-1).

    For a cohort aged one or more, the only sources of change are net migration and deaths,
    so positive means net migration exceeds deaths.
    """
    persons = _australia(data, "Persons")
    transitions = {}
    for year in END_YEARS:
        end = _june(year)
        current, previous = _june_row(persons, end), _june_row(persons, end - 1)
        transitions[year] = pd.Series({age: current[age] - previous[age - 1] for age in range(1, MAX_AGE + 1)})
    average = pd.DataFrame(transitions).mean(axis=1)
    average.index.name = "Age in whole years"
    average.name = "Average annual cohort change"
    average, units = recalibrated(average, "Number Persons")
    line_plot_finalise(
        average,
        title="Average Annual Age Transitions: Net Migration vs Deaths",
        ylabel=f"{units} per year",
        xlabel="Age in whole years",
        y0=True,
        xticks=AGE_TICKS,
        lheader="Positive: net migration > deaths.  Negative: deaths > net migration. ",
        lfooter=TRANSITION_LFOOTER,
        rfooter=SOURCE_3101,
        pre_tag="erp",
    )


def age_transition_decomposition(data: PopulationData) -> None:
    """Split the average annual age transition into net migration and modelled deaths.

    For the cohort aged a-1 to a: deaths(a) = qx(a-1) x ERP(a-1, t-1), by sex and summed; net
    migration(a) = transition(a) + deaths(a), the residual. Deaths are modelled (the latest
    life-table rates by start-of-year population), not registered counts.
    """
    persons, males, females = (_australia(data, group) for group in ("Persons", "Male", "Female"))
    qx = _life_table_qx()
    ages = range(1, MAX_AGE + 1)
    transition_columns, death_columns = [], []
    for year in END_YEARS:
        end = _june(year)
        current = _june_row(persons, end)
        previous, previous_male, previous_female = (
            _june_row(frame, end - 1) for frame in (persons, males, females)
        )
        transition_columns.append(pd.Series({age: current[age] - previous[age - 1] for age in ages}))
        death_columns.append(
            pd.Series(
                {
                    age: qx.loc[age - 1, "Male"] * previous_male[age - 1]
                    + qx.loc[age - 1, "Female"] * previous_female[age - 1]
                    for age in ages
                }
            )
        )
    transition = pd.concat(transition_columns, axis=1).mean(axis=1)
    deaths = pd.concat(death_columns, axis=1).mean(axis=1)
    frame = pd.DataFrame(
        {"Net change": transition, "Net migration": transition + deaths, "Deaths": -deaths}  # deaths: a negative
    )
    frame.index.name = "Age in whole years"
    frame, units = recalibrated(frame, "Number Persons")

    axes = line_plot(frame, width=TRANSITION_WIDTHS, annotate=False)
    axes.text(
        34,
        19,
        "Net migration is net of all movements,\nincluding Australian citizens returning home.",
        fontsize="small",
        color="dimgray",
        va="center",
        ha="left",
    )
    axes.text(
        RESIDUAL_AGE + 1,
        14,
        "Above age 70 net migration is residual\n(true migration ~ 0); the wobble is ERP\n"
        "revision noise in later years, not migration.",
        fontsize="small",
        color="dimgray",
        va="center",
        ha="left",
    )

    def age_box(weights: pd.Series, face: str, edge: str, label: str) -> None:
        """Draw where a component sits by age: box the middle 50%, whiskers the middle 80%, tick the median."""
        p10, p25, p50, p75, p90 = _weighted_age_quantiles(weights, BOX_QUANTILES)
        axes.bxp(
            [{"med": p50, "q1": p25, "q3": p75, "whislo": p10, "whishi": p90, "fliers": []}],
            positions=[1.0],
            widths=0.9,
            orientation="horizontal",
            manage_ticks=False,
            patch_artist=True,
            boxprops={"facecolor": face, "alpha": 0.35, "edgecolor": edge},
            medianprops={"color": "black"},
            whiskerprops={"color": edge},
            capprops={"color": edge},
        )
        axes.text((p25 + p75) / 2, 1.7, label, fontsize=7, color=edge, va="bottom", ha="center")

    death_color = axes.get_lines()[2].get_color()  # match the Deaths line
    if not isinstance(death_color, str):
        raise TypeError(f"Expected a named colour for the Deaths line, got {death_color!r}")
    age_box(frame["Net migration"], "orange", "darkorange", "Net migration:\nmiddle 50% / 80% by age")
    age_box(-frame["Deaths"], death_color, death_color, "Deaths:\nmiddle 50% / 80% by age")
    finalise_plot(
        axes,
        title="Population Annual Age Transitions: Net Migration and Deaths",
        ylabel=f"{units} per year",
        xlabel="Age in whole years",
        y0=True,
        xticks=AGE_TICKS,
        legend={"loc": "upper left", "fontsize": "small"},
        axvspan={"xmin": RESIDUAL_AGE, "xmax": MAX_AGE, "color": "gray", "alpha": 0.07},
        lheader="Net migration + deaths = net change. ",
        rheader="Deaths modelled from ABS life-table rates x start-year population. ",
        lfooter=TRANSITION_LFOOTER,
        rfooter=SOURCE_LIFE_TABLES,
        pre_tag="erp",
    )


# --- table of contents, in run order
CHARTS = (
    (state_age_profiles, ()),
    (median_age_by_state, ()),
    (age_gender_profiles, ()),
    (age_transition_profile, ()),
    (age_transition_decomposition, ()),
)
