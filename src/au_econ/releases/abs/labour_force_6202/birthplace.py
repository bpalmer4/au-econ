"""Labour Force charts by country of birth, from the LMS4 data cube (was 6291.0.55.001 LM5)."""

# --- dependencies
from typing import TYPE_CHECKING

import pandas as pd
import readabs as ra
from mgplot import bar_plot_finalise

from au_econ.sources.abs import get_pivot_cube

if TYPE_CHECKING:
    from au_econ.sources.abs import AbsRelease

# --- constants
CATALOGUE, CUBE = "6202.0", "LMS4"  # labour force status by age, country of birth group and sex
BIRTH_KEY = "birth"  # in the name of the cube's country of birth column
AUSTRALIA = "Australia (includes External Territories)"
EMPLOYED = ("Employed full-time ('000)", "Employed part-time ('000)")
UNEMPLOYED = ("Unemployed looked for full-time work ('000)", "Unemployed looked for only part-time work ('000)")
NOT_IN_LABOUR_FORCE = "Not in the labour force (NILF) ('000)"
SMOOTHING_MONTHS = 3  # months pooled, to manage sampling noise in the Original series
PRE_TAG = "cob"
BORN_HERE, BORN_OVERSEAS = "Born in Australia", "Born overseas"
BORN_COLOURS = ["darkblue", "darkorange"]
# Australia anchored in grey; overseas groups in a categorical palette
GROUP_COLOURS = [
    "#bbbbbb",
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#17becf",
    "#bcbd22",
]
GROUP_YLIM = (-0.6, 12.6)  # headroom above the 11 age bars (positions 0-10) for the legend
CIVPOP_COLOURS = ("red", "blue")  # all groups; excluding the Australian-born


# --- helpers
def _cube() -> tuple[pd.DataFrame, str, list[pd.Period]]:
    """Return the cube, the name of its country of birth column, and the months pooled."""
    cube = get_pivot_cube(CATALOGUE, CUBE)
    birth = next(str(c) for c in cube.columns if BIRTH_KEY in str(c).lower())
    recent = sorted(cube["Month"].unique())[-SMOOTHING_MONTHS:]
    return cube, birth, recent


def _pretty(group: str) -> str:
    """Tidy a country of birth group name: the cube writes the overseas groups in capitals."""
    return group.title().replace(" And ", " & ") if group.isupper() else "Australia"


def _lfooter(recent: list[pd.Period]) -> str:
    return f"Australia. Original series. Average of {SMOOTHING_MONTHS} months to {recent[-1]}. "


# --- charts
def birthplace_by_age(release: AbsRelease) -> None:
    """Australian-born against overseas-born shares of employed persons, by age group."""
    cube, birth, recent = _cube()
    frame = pd.DataFrame(
        {
            "Month": cube["Month"],
            "Age": cube["Age"],
            "Birthplace": (cube[birth] == AUSTRALIA).map({True: BORN_HERE, False: BORN_OVERSEAS}),
            "Employed": cube[EMPLOYED[0]] + cube[EMPLOYED[1]],
        }
    )
    if not (cube[birth] == AUSTRALIA).any():
        raise ValueError(f"Category {AUSTRALIA!r} not found in {CUBE}")
    snap = frame[frame["Month"].isin(recent)]
    pivot = snap.pivot_table(values="Employed", index="Age", columns="Birthplace", aggfunc="sum")
    pivot = pivot[[BORN_HERE, BORN_OVERSEAS]]
    shares = (pivot.div(pivot.sum(axis=1), axis=0) * 100).iloc[::-1]  # youngest age group at the top
    bar_plot_finalise(
        shares,
        horizontal=True,
        stacked=True,
        annotate=True,
        rounding=0,
        color=BORN_COLOURS,
        title="Employed Persons by Age:\nBorn in Australia v Born Overseas",
        xlabel="Per cent of persons employed",
        xlim=(0.0, 100.0),
        axvline={"x": 50, "color": "darkgrey", "linestyle": "--", "linewidth": 0.75},
        legend={"loc": "center right", "ncol": 1, "fontsize": "x-small"},
        rfooter=release.source,
        lfooter=_lfooter(recent),
        pre_tag=PRE_TAG,
    )


def birth_groups_by_age(release: AbsRelease) -> None:
    """Country of birth group shares by age, of employed persons and of the civilian population 15+."""
    cube, birth, recent = _cube()
    employed = cube[EMPLOYED[0]] + cube[EMPLOYED[1]]
    unemployed = cube[UNEMPLOYED[0]] + cube[UNEMPLOYED[1]]
    cohorts = {
        "Employed Persons": (employed, "persons employed"),
        "Civilian Population": (employed + unemployed + cube[NOT_IN_LABOUR_FORCE], "civilian population 15+"),
    }
    order = None
    for label, (counts, basis) in cohorts.items():
        frame = pd.DataFrame({"Month": cube["Month"], "Age": cube["Age"], "Group": cube[birth], "N": counts})
        snap = frame[frame["Month"].isin(recent)]
        pivot = snap.pivot_table(values="N", index="Age", columns="Group", aggfunc="sum")
        pivot = pivot.rename(columns={c: _pretty(c) for c in pivot.columns})
        if order is None:  # column order from the first basis, so colours match across both charts
            order = pivot.sum().sort_values(ascending=False).index
        shares = (pivot[order].div(pivot[order].sum(axis=1), axis=0) * 100).iloc[::-1]
        xlabel, rfooter, lfooter = f"Per cent of {basis}", release.source, _lfooter(recent)
        bar_plot_finalise(
            shares,
            horizontal=True,
            stacked=True,
            annotate=False,
            color=GROUP_COLOURS,
            title=f"{label} by Age:\nCountry of Birth Group Shares",
            xlim=(0.0, 100.0),
            legend={"loc": "upper center", "ncol": 4, "fontsize": "xx-small"},
            xlabel=xlabel,
            ylim=GROUP_YLIM,
            rfooter=rfooter,
            lfooter=lfooter,
            pre_tag=PRE_TAG,
        )
        # without the Australian-born: still shares of the full basis, so bars no longer reach 100
        bar_plot_finalise(
            shares.drop(columns="Australia"),
            horizontal=True,
            stacked=True,
            annotate=True,
            rounding=0,
            color=GROUP_COLOURS[1:],
            title=f"{label} by Age:\nCountry of Birth Group Shares (excluding Australian-born)",
            legend={"loc": "upper center", "ncol": 3, "fontsize": "xx-small"},
            xlabel=xlabel,
            ylim=GROUP_YLIM,
            rfooter=rfooter,
            lfooter=lfooter,
            pre_tag=PRE_TAG,
        )


def civpop_by_birthplace(release: AbsRelease) -> None:
    """Civilian population 15+ by country of birth group, averaged over the latest months."""
    cube, birth, recent = _cube()
    civpop = cube[EMPLOYED[0]] + cube[EMPLOYED[1]] + cube[UNEMPLOYED[0]] + cube[UNEMPLOYED[1]]
    civpop = civpop + cube[NOT_IN_LABOUR_FORCE]
    frame = pd.DataFrame({"Month": cube["Month"], "Group": cube[birth], "N": civpop})
    snap = frame[frame["Month"].isin(recent)]
    counts = snap.groupby("Group")["N"].sum() / SMOOTHING_MONTHS  # pooled months, so an average level
    counts.index = pd.Index([_pretty(c) for c in counts.index])
    title = "Civilian Population by Country of Birth Group"
    variants = {
        title: (counts, CIVPOP_COLOURS[0]),
        f"{title}\n(excluding Australian-born)": (counts.drop("Australia"), CIVPOP_COLOURS[1]),
    }
    for chart_title, (series, colour) in variants.items():
        levels, units = ra.recalibrate(series, "Thousand Persons")
        if not isinstance(levels, pd.Series):
            raise TypeError(f"recalibrate returned {type(levels).__name__}")
        bar_plot_finalise(
            levels.sort_values(),
            horizontal=True,
            annotate=True,
            above=True,
            color=colour,
            title=chart_title,
            xlabel=units,
            rfooter=release.source,
            lfooter=_lfooter(recent),
            pre_tag=PRE_TAG,
        )


# --- table of contents, in run order
CHARTS = (
    (birthplace_by_age, ()),
    (birth_groups_by_age, ()),
    (civpop_by_birthplace, ()),
)
