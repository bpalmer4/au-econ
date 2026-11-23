"""Labour Force charts of recent employment change by industry and by occupation.

Industry division (ANZSIC) and occupation major group (OSCA) of main job, from the monthly tables
62020021_MTH and 62020023_MTH; industry by state and sex, and by occupation and sex, from the
IAO1 and IAO5 data cubes.
"""

# --- dependencies
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from mgplot import abbreviate_state, bar_plot_finalise, finalise_plot
from readabs import metacol as mc

from au_econ.charting.footers import SERIES_TYPE_NOTES
from au_econ.releases.abs.labour_force_6202.common import INDUSTRY, OCCUPATION, ORIGINAL, STATES
from au_econ.sources.abs import get_pivot_cube
lazy from au_econ.sources.abs import AbsRelease

# --- constants
INDUSTRY_EMPLOYED = r"^Australia ;  (.+) ;  Employed total ;"  # the industry is the captured group
OCCUPATION_EMPLOYED = r"^(.+) ;  Employed total ;  Persons ;"  # the occupation is the captured group
INDUSTRY_COUNT = 19  # ANZSIC divisions
OCCUPATION_COUNT = 8  # OSCA major groups
CHANGE_MONTHS = 2  # the latest two monthly reports
ZERO_LINE = {"x": 0, "color": "black", "linewidth": 0.75}
LABEL_ROOM = 0.15  # share of the data range added at each end, for the value labels past the bars

# heat maps from the IAO data cubes: employed by industry and sex, and by GCCSA (IAO1) or occupation (IAO5)
CATALOGUE, STATE_CUBE, OCCUPATION_CUBE = "6202.0", "IAO1", "IAO5"
REGION_KEY, INDUSTRY_KEY, OCCUPATION_KEY = "GCCSA", "Industry division", "Occupation major group"  # column names
SEX = "Sex"
CUBE_EMPLOYED = ("Employed full-time ('000)", "Employed part-time ('000)")
SEX_HEADINGS = {"Males": "M", "Females": "F"}
REGION_STATES = {
    "Greater Sydney": "New South Wales",
    "Rest of NSW": "New South Wales",
    "Greater Melbourne": "Victoria",
    "Rest of Vic.": "Victoria",
    "Greater Brisbane": "Queensland",
    "Rest of Qld": "Queensland",
    "Greater Adelaide": "South Australia",
    "Rest of SA": "South Australia",
    "Greater Perth": "Western Australia",
    "Rest of WA": "Western Australia",
    "Greater Hobart": "Tasmania",
    "Rest of Tas.": "Tasmania",
    "Northern Territory": "Northern Territory",
    "Australian Capital Territory": "Australian Capital Territory",
}
OCCUPATION_HEADINGS = {  # OSCA major groups, in published order
    "Managers": "Managers",
    "Professionals": "Professionals",
    "Technicians and Trades Workers": "Technicians\n& Trades",
    "Community and Personal Service Workers": "Community\n& Personal",
    "Clerical and Administrative Workers": "Clerical\n& Admin",
    "Sales Workers": "Sales",
    "Machinery Operators and Drivers": "Machinery\n& Drivers",
    "Labourers": "Labourers",
}
MINIMUM_BASE = 1.0  # '000 persons: a cell with fewer employed in the base month is left blank
HEATMAP_COLOURS = "coolwarm_r"  # red for losses, blue for gains
COLOUR_CAP_QUANTILE = 0.95  # colours saturate at this quantile of the absolute changes
WHITE_TEXT_SHARE = 0.6  # cell text turns white beyond this share of the colour cap
CELL_FONTSIZE = 6
HEADING_PAD = 12  # points between the group headings and the sex headings below them
GROUP_DIVIDER = {"color": "white", "linewidth": 2}
HEATMAP_SIZE = (9.0, 7.5)


# --- helpers
def _change_by_group(release: AbsRelease, table: str, pattern: str, count: int, group: str) -> None:
    """Chart the change in employed persons by group over the latest two months, in thousands and per cent."""
    meta = release.meta
    rows = meta[meta[mc.table] == table]
    groups = rows[mc.did].str.extract(pattern, expand=False).dropna()
    if len(groups) != count:
        raise ValueError(f"{table}: expected {count} groups, found {len(groups)}")
    series_ids = rows.loc[groups.index, mc.id]
    employed = pd.DataFrame(
        {name: release.data[table][series_id] for name, series_id in zip(groups, series_ids, strict=True)}
    ).dropna(how="all")
    if len(employed) <= CHANGE_MONTHS or employed.iloc[-CHANGE_MONTHS - 1 :].isna().any().any():
        raise ValueError(f"{table}: fewer than {CHANGE_MONTHS + 1} complete months")
    base, latest = employed.iloc[-CHANGE_MONTHS - 1], employed.iloc[-1]
    start, end = employed.index[-CHANGE_MONTHS - 1], employed.index[-1]
    changes = {
        "Thousand Persons": latest - base,
        "Per cent": (latest / base - 1) * 100,
    }
    for xlabel, change in changes.items():
        room = (change.max() - change.min()) * LABEL_ROOM
        bar_plot_finalise(
            change.sort_values(),
            horizontal=True,
            annotate=True,
            above=True,
            rounding=1,
            title=f"Change in Employment by {group}:\n{start.strftime('%b %Y')} to {end.strftime('%b %Y')}",
            xlabel=xlabel,
            xlim=(min(change.min(), 0) - room, max(change.max(), 0) + room),
            axvline=ZERO_LINE,
            lfooter=f"Australia. {SERIES_TYPE_NOTES[ORIGINAL]} {group} of main job. ",
            rfooter=release.source,
            tag=xlabel,
        )


def _change_heatmaps(
    release: AbsRelease,
    cube: pd.DataFrame,
    *,
    cube_name: str,
    group: str,
    headings: dict[str, str],
    heading_fontsize: str,
    subject: str,
    note: str,
) -> None:
    """Heat maps of the change in employed persons by industry, group and sex over the latest two months.

    One map in thousands and one in per cent: industries down the side; across the top, the
    values of the cube's group column in the order of headings, each split by sex. A cell with
    fewer than MINIMUM_BASE thousand employed in the base month is blank.
    """
    period = cube.columns[0]
    industry = next(str(c) for c in cube.columns if INDUSTRY_KEY in str(c))
    if set(cube[SEX]) != set(SEX_HEADINGS):
        raise ValueError(f"ABS {cube_name}: unexpected sexes {sorted(set(cube[SEX]))}")
    industries = list(dict.fromkeys(cube[industry]))  # ANZSIC order, as published
    if len(industries) != INDUSTRY_COUNT:
        raise ValueError(f"ABS {cube_name}: expected {INDUSTRY_COUNT} industries, found {len(industries)}")
    months = sorted(cube[period].unique())
    if len(months) <= CHANGE_MONTHS:
        raise ValueError(f"ABS {cube_name}: fewer than {CHANGE_MONTHS + 1} months")
    start, end = months[-CHANGE_MONTHS - 1], months[-1]

    employed = cube.assign(Employed=cube[list(CUBE_EMPLOYED)].sum(axis=1))
    columns = pd.MultiIndex.from_product([list(headings), list(SEX_HEADINGS)])
    base, latest = (
        employed[employed[period] == month]
        .pivot_table(index=industry, columns=[group, SEX], values="Employed", aggfunc="sum")
        .reindex(index=industries, columns=columns)
        for month in (start, end)
    )
    shown = base >= MINIMUM_BASE
    changes = {
        "Thousand Persons": (latest - base).where(shown),
        "Per cent": ((latest / base - 1) * 100).where(shown),
    }

    for unit, change in changes.items():
        values = change.to_numpy(dtype=float)
        cap = float(np.nanquantile(np.abs(values), COLOUR_CAP_QUANTILE))
        _, ax = plt.subplots()
        ax.imshow(values, cmap=HEATMAP_COLOURS, vmin=-cap, vmax=cap, aspect="auto")
        ax.grid(visible=False)
        for (row, col), value in np.ndenumerate(values):
            if not np.isnan(value):
                colour = "white" if abs(value) > WHITE_TEXT_SHARE * cap else "black"
                ax.text(col, row, f"{value:.1f}", ha="center", va="center", fontsize=CELL_FONTSIZE, color=colour)
        ax.set_yticks(range(len(industries)), industries, fontsize="x-small")
        ax.set_xticks(range(len(columns)), [SEX_HEADINGS[sex] for _, sex in columns], fontsize="x-small")
        ax.tick_params(length=0, top=True, labeltop=True, bottom=False, labelbottom=False)
        group_axis = ax.secondary_xaxis("top")
        group_axis.set_xticks(
            [len(SEX_HEADINGS) * i + (len(SEX_HEADINGS) - 1) / 2 for i in range(len(headings))],
            list(headings.values()),
            fontsize=heading_fontsize,
        )
        group_axis.tick_params(length=0, pad=HEADING_PAD)
        group_axis.spines["top"].set_visible(False)
        finalise_plot(
            ax,
            title=f"Change in Employment by {subject}:\n{start.strftime('%b %Y')} to {end.strftime('%b %Y')}",
            xlabel=unit,
            axvline=[{"x": len(SEX_HEADINGS) * i - 0.5, **GROUP_DIVIDER} for i in range(1, len(headings))],
            preserve_lims=True,
            figsize=HEATMAP_SIZE,
            lfooter=f"Australia. {SERIES_TYPE_NOTES[ORIGINAL]} {note} "
            f"Blank: under {MINIMUM_BASE * 1000:,.0f} employed in {start.strftime('%b %Y')}. ",
            rfooter=release.source,
            tag=unit,
        )


# --- charts
def industry_change(release: AbsRelease) -> None:
    """Change in employed persons by industry over the latest two months, in thousands and per cent."""
    _change_by_group(release, INDUSTRY, INDUSTRY_EMPLOYED, INDUSTRY_COUNT, "Industry")


def occupation_change(release: AbsRelease) -> None:
    """Change in employed persons by occupation over the latest two months, in thousands and per cent."""
    _change_by_group(release, OCCUPATION, OCCUPATION_EMPLOYED, OCCUPATION_COUNT, "Occupation")


def industry_state_gender_change(release: AbsRelease) -> None:
    """Heat maps of the change in employed persons by industry, state and sex over the latest two months."""
    cube = get_pivot_cube(CATALOGUE, STATE_CUBE)
    region = next(str(c) for c in cube.columns if REGION_KEY in str(c))
    if set(cube[region]) != set(REGION_STATES):
        raise ValueError(f"ABS {STATE_CUBE}: unexpected regions {sorted(set(cube[region]) ^ set(REGION_STATES))}")
    _change_heatmaps(
        release,
        cube.assign(State=cube[region].map(REGION_STATES)),
        cube_name=STATE_CUBE,
        group="State",
        headings={state: abbreviate_state(state) for state in STATES},
        heading_fontsize="small",
        subject="Industry, State and Gender",
        note="Industry of main job.",
    )


def industry_occupation_gender_change(release: AbsRelease) -> None:
    """Heat maps of the change in employed persons by industry, occupation and sex over the latest two months."""
    cube = get_pivot_cube(CATALOGUE, OCCUPATION_CUBE)
    occupation = next(str(c) for c in cube.columns if OCCUPATION_KEY in str(c))
    unexpected = set(cube[occupation]) ^ set(OCCUPATION_HEADINGS)
    if unexpected:
        raise ValueError(f"ABS {OCCUPATION_CUBE}: unexpected occupations {sorted(unexpected)}")
    _change_heatmaps(
        release,
        cube,
        cube_name=OCCUPATION_CUBE,
        group=occupation,
        headings=OCCUPATION_HEADINGS,
        heading_fontsize="x-small",
        subject="Industry, Occupation\nand Gender",
        note="Industry and occupation of main job.",
    )


# --- table of contents, in run order
CHARTS = (
    (industry_change, ()),
    (occupation_change, ()),
    (industry_state_gender_change, ()),
    (industry_occupation_gender_change, ()),
)
