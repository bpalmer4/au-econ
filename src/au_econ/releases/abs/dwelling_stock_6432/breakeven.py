"""Breakeven dwellings: new dwellings needed to hold people per dwelling constant, against those added.

National and by state; the shortfall against the 2021Q4 ratio; the stock extended back to
1981 from completions; the gross requirement against gross builds; and the 21+ versions.
"""

# --- dependencies
from functools import partial
from typing import TYPE_CHECKING, Any

import pandas as pd
import readabs as ra
from mgplot import bar_plot_finalise, chart_subdir, line_plot_finalise, multi_start, state_abbrs, state_names
from mgplot.utilities import get_color_list

from au_econ.releases.abs.dwelling_stock_6432.common import (
    BE_DEFINITION,
    BE_DEFINITION_21,
    BE_FORMULA,
    DWELLINGS_CATALOGUE,
    EXT_LFOOTER,
    EXT_SOURCES,
    LEGEND_SMALL,
    LFS_SOURCE,
    PERCENT,
    QUARTERS_PER_YEAR,
    at_period,
    breakeven_components,
    breakeven_components_21,
    census_retention,
    get_civ_pop_15_m,
    get_completions,
    get_dwellings_count,
    get_extended_dwellings_count,
    sources,
)
from au_econ.releases.abs.dwelling_stock_6432.plots import (
    STANDARD_STARTS,
    plot_adults_per_dwelling,
    plot_adults_vs_civpop_per_dwelling,
    plot_breakeven_shaded,
    plot_civ_pop_15_per_dwelling,
    plot_dwelling_vs_adults_21_growth,
    plot_dwelling_vs_civ_pop_15_growth,
    plot_net_new_vs_breakeven,
)

if TYPE_CHECKING:
    from au_econ.sources.abs import AbsRelease

# --- constants
LATEST_EXCLUDED = " Latest quarter excluded."
SAFE_PRE_TAG = "be-safe-"
RESTORE_BASE = "2021Q4"  # the last quarter at or above breakeven
GROSS_PLOT_FROM = -44
EXTENDED_PRE_TAG, EXTENDED21_PRE_TAG = "extended-", "extended21-"
EXTENDED_ROTATION = 90  # the long history's yearly labels would overlap if flat
POP_21_SOURCES = ("6202.0", "3101.0")  # the 21+ population: civilian 15+ and ERP by age
STATE_LABEL_ROUND = 1
WINDOW_TAGS = ("complete", "recent")


def _population_and_dwelling_colors() -> list[str]:
    """Return mgplot's palette for smoothed and raw population growth (one colour), breakeven, and net new."""
    population, breakeven, net_new = get_color_list(3)
    return [population, population, breakeven, net_new]


def _extended(release: AbsRelease) -> tuple[pd.Series, pd.Series]:
    """Return the extended dwelling stock, and the same without its provisional latest quarter."""
    extended = get_extended_dwellings_count(release)
    return extended, extended.iloc[:-1]


# --- charts
def breakeven_dwellings(release: AbsRelease) -> None:
    """Chart net new dwellings against breakeven, the gap above or below it, and population growth against both.

    The latest net-new print is provisional and reliably revised down, so it is left out
    (the "be-safe-" set), as the left header says.
    """
    drop_last = 1
    be_header = BE_DEFINITION + LATEST_EXCLUDED
    net_new, breakeven, smooth_incr, raw_incr = breakeven_components(release, drop_last=drop_last)
    plot_net_new_vs_breakeven(net_new, breakeven, be_header=be_header, be_pre_tag=SAFE_PRE_TAG)

    gap = (net_new - breakeven).dropna()
    gap_plot, gap_units = ra.recalibrate(
        pd.DataFrame({"Above breakeven": gap.clip(lower=0), "Below breakeven": gap.clip(upper=0)}).copy(), "Number"
    )
    if not isinstance(gap_plot, pd.DataFrame):
        raise TypeError("recalibrate returned a Series")
    for start, tag in zip(STANDARD_STARTS, WINDOW_TAGS, strict=True):
        bar_plot_finalise(
            gap_plot.iloc[start:],
            stacked=True,
            color=["seagreen", "darkred"],
            annotate=False,
            title="Net new dwellings: above/below breakeven (15+)",
            ylabel=f"Dwellings per quarter ({gap_units.lower()}s)",
            rfooter=LFS_SOURCE,
            lfooter="Australia. Original series. " + BE_FORMULA,
            lheader=be_header,
            rheader=f"Latest gap: {gap.iloc[-1]:+,.0f}/qtr",
            legend=LEGEND_SMALL,
            y0=True,
            pre_tag=SAFE_PRE_TAG,
            tag=tag,
        )

    population = pd.DataFrame(
        {
            "Smoothed civ. pop. 15+ growth": smooth_incr,
            "Civ pop 15+ growth (raw)": raw_incr,
            "Breakeven new dwellings": breakeven,
            "Net new dwellings": net_new,
        }
    ).dropna()
    last = population.iloc[-1]
    population_plot, units = ra.recalibrate(population.copy(), "Number")
    multi_start(
        population_plot,
        function=line_plot_finalise,
        starts=STANDARD_STARTS,
        title="Population growth vs new dwellings: breakeven and actual (15+)",
        ylabel=f"Per quarter ({units.lower()}s)",
        color=_population_and_dwelling_colors(),  # the raw population line shares the smoothed one's colour
        width=[2, 0.75, 2, 1.75],
        style=["-", "-", "-", "-"],
        annotate=[True, False, False, True],
        rounding=1,
        rfooter=LFS_SOURCE,
        lfooter="Australia. Original series. Population: persons; breakeven & net new: dwellings. ",
        lheader=be_header,
        rheader=f"Net new: {last['Net new dwellings']:,.0f}/qtr;  "
        f"breakeven: {last['Breakeven new dwellings']:,.0f}/qtr",
        legend=LEGEND_SMALL,
        y0=True,
        pre_tag=SAFE_PRE_TAG,
    )


def breakeven_shaded(release: AbsRelease) -> None:
    """Chart smoothed net new dwellings against breakeven, the gap shaded, with each year's balance."""
    plot_breakeven_shaded(release)


def breakeven_by_state(release: AbsRelease) -> None:
    """Chart net new dwellings against breakeven, and the shaded annual balance, for each state (in states/)."""
    drop_last = 1
    be_header = BE_DEFINITION + LATEST_EXCLUDED
    with chart_subdir("states", clear=True):
        for state, abbreviation in zip(state_names, state_abbrs, strict=True):
            tag = abbreviation.lower().replace(".", "").replace(" ", "")
            net_new, breakeven, *_ = breakeven_components(release, drop_last=drop_last, state=state)
            plot_net_new_vs_breakeven(net_new, breakeven, be_header=be_header, be_pre_tag=f"be-{tag}-", geo=state)
            plot_breakeven_shaded(
                release,
                be_pre_tag=f"be-shade-{tag}-",
                geo=state,
                drop_last=drop_last,
                label_round=STATE_LABEL_ROUND,
                components_fn=partial(breakeven_components, state=state),
            )


def restore_ratio_deficit(release: AbsRelease) -> None:
    """Chart the homes needed to restore the 2021Q4 dwellings-to-civ-pop-15+ ratio, in dwellings and per cent.

    shortfall(t) = civ_pop15(t) / ratio_base - dwellings(t), with ratio_base = civ_pop15 /
    dwellings at 2021Q4, the last quarter at or above breakeven. The provisional latest
    quarter is left out.
    """
    drop_last = 1
    frame = pd.DataFrame(
        {"dw": get_dwellings_count(release), "pop": ra.monthly_to_qtly(get_civ_pop_15_m(), f="mean")}
    ).dropna()
    frame = frame.iloc[:-drop_last]
    base = pd.Period(RESTORE_BASE, freq="Q-DEC")
    ratio_base = at_period(frame["pop"], base) / at_period(frame["dw"], base)
    shortfall = frame["pop"] / ratio_base - frame["dw"]
    shortfall = shortfall[shortfall.index >= base]
    share = shortfall / frame["dw"].reindex(shortfall.index) * PERCENT
    common: dict[str, Any] = {
        "annotate": True,
        "above": False,
        "rfooter": LFS_SOURCE,
        "lheader": f"{RESTORE_BASE} ratio: {ratio_base:.3f} persons (15+) per dwelling. Latest quarter excluded.",
        "y0": True,
        "pre_tag": SAFE_PRE_TAG,
    }
    shortfall_plot, units = ra.recalibrate(shortfall.copy(), "Number")
    bar_plot_finalise(
        shortfall_plot,
        rounding=0,
        title=f"Homes needed to restore the {RESTORE_BASE} dwellings-to-population ratio",
        ylabel=f"Dwelling shortfall ({units.lower()}s)",
        lfooter="Australia. Original series. Shortfall = dwellings needed to "
        f"restore the {RESTORE_BASE} dwellings-to-civ-pop-15+ ratio. ",
        rheader=f"{shortfall.index[-1]}: {shortfall.iloc[-1]:,.0f} dwellings short",
        tag="restore-ratio",
        **common,
    )
    bar_plot_finalise(
        share,
        rounding=2,
        title=f"Dwelling shortfall vs {RESTORE_BASE} ratio: share of the dwelling stock",
        ylabel="Per cent of dwelling stock",
        lfooter="Australia. Original series. Shortfall (dwellings needed to "
        f"restore the {RESTORE_BASE} ratio) as a share of the dwelling stock. ",
        rheader=f"{share.index[-1]}: {share.iloc[-1]:.1f}% of the dwelling stock",
        tag="restore-ratio-pct",
        **common,
    )


def extended_history(release: AbsRelease) -> None:
    """Chart breakeven, the shaded balance, people per dwelling and growth on the stock extended back to 1981."""
    extended, extended_safe = _extended(release)
    net_new, breakeven, *_ = breakeven_components(release, extended, drop_last=1)
    plot_net_new_vs_breakeven(
        net_new,
        breakeven,
        be_header=BE_DEFINITION + LATEST_EXCLUDED,
        be_pre_tag=EXTENDED_PRE_TAG,
        starts=(0,),
        lfooter_note=EXT_LFOOTER,
        rfooter_extra=EXT_SOURCES,
    )
    plot_breakeven_shaded(
        release,
        drop_last=1,
        be_pre_tag=EXTENDED_PRE_TAG,
        dwellings=extended,
        label_rotation=EXTENDED_ROTATION,
        lfooter_extra=EXT_LFOOTER,
        rfooter_extra=EXT_SOURCES,
    )
    plot_civ_pop_15_per_dwelling(
        release,
        extended_safe,
        pre_tag=EXTENDED_PRE_TAG,
        with_postcovid=False,  # a pre-COVID trajectory means nothing over 40+ years
        lfooter="Australia. Original series. Civilian population aged 15+. " + EXT_LFOOTER,
        rfooter_extra=EXT_SOURCES,
    )
    plot_dwelling_vs_civ_pop_15_growth(
        release,
        extended_safe,
        pre_tag=EXTENDED_PRE_TAG,
        plot_from=extended_safe.pct_change(QUARTERS_PER_YEAR).dropna().index[0],
        lfooter="Australia. Original series. Through-the-year growth. " + EXT_LFOOTER,
        rfooter_extra=EXT_SOURCES,
    )


def gross_dwelling_requirement(release: AbsRelease) -> None:
    """Chart the gross housing requirement (population need plus demolitions) against gross completions.

    Need is the breakeven; demolitions are completions x (1 - r), the census-calibrated
    knock-down rate. All annualised (4-quarter sums); the provisional latest quarter is left out.
    """
    _net_new, need, *_ = breakeven_components(release, drop_last=1)
    completions = get_completions()
    r_for = census_retention(completions)
    demolitions_by_quarter: dict[pd.Period, float] = {}
    for quarter in completions.index:
        if not isinstance(quarter, pd.Period):
            raise TypeError("Expected a quarterly PeriodIndex for completions")
        r = r_for(quarter)
        if r is not None:
            demolitions_by_quarter[quarter] = at_period(completions, quarter) * (1 - r)
    demolitions = pd.Series(demolitions_by_quarter)
    requirement = (need + demolitions).dropna()
    frame = pd.DataFrame(
        {
            "Housing requirement (need + demolitions)": requirement.rolling(QUARTERS_PER_YEAR).sum(),
            "Housing demolitions": demolitions.rolling(QUARTERS_PER_YEAR).sum(),
            "Gross builds": completions.rolling(QUARTERS_PER_YEAR).sum(),
        }
    ).dropna()
    frame, units = ra.recalibrate(frame, "Number")
    line_plot_finalise(
        frame,
        plot_from=GROSS_PLOT_FROM,
        annotate=True,
        rounding=1,
        title="Dwelling requirement vs builds: gross basis (15+)",
        ylabel=f"Dwellings per year ({units.lower()}s)",
        legend=LEGEND_SMALL,
        lheader="Requirement = civ15 growth rate x dwelling stock + demolitions. ",
        rheader="Demolitions = completions x (1-r), census-calibrated. ",
        lfooter="Australia. Original series. Civilian population aged 15+. ",
        rfooter=sources(DWELLINGS_CATALOGUE, "6202.0", *EXT_SOURCES),
        pre_tag="be-",
        tag="gross",
    )


def extended_adults_vs_civpop(release: AbsRelease) -> None:
    """Chart adults (21+) and civilian population (15+) per dwelling over the extended history."""
    _extended_stock, extended_safe = _extended(release)
    plot_adults_vs_civpop_per_dwelling(
        extended_safe,
        pre_tag=EXTENDED_PRE_TAG,
        lfooter="Australia. Original series. " + EXT_LFOOTER,
        rfooter_extra=EXT_SOURCES,
    )


def extended_21(release: AbsRelease) -> None:
    """Chart breakeven, the shaded balance, adults per dwelling and 21+ growth, over the extended history."""
    extended, extended_safe = _extended(release)
    net_new, breakeven, *_ = breakeven_components_21(release, extended, drop_last=1)
    plot_net_new_vs_breakeven(
        net_new,
        breakeven,
        be_header=BE_DEFINITION_21 + LATEST_EXCLUDED,
        be_pre_tag=EXTENDED21_PRE_TAG,
        starts=(0,),
        lfooter_note=EXT_LFOOTER,
        rfooter_extra=EXT_SOURCES,
        pop_sources=POP_21_SOURCES,
        pop_label="21+",
    )
    plot_breakeven_shaded(
        release,
        drop_last=1,
        be_pre_tag=EXTENDED21_PRE_TAG,
        dwellings=extended,
        label_rotation=EXTENDED_ROTATION,
        lfooter_extra=EXT_LFOOTER,
        rfooter_extra=EXT_SOURCES,
        components_fn=breakeven_components_21,
        be_definition=BE_DEFINITION_21,
        pop_sources=POP_21_SOURCES,
        pop_label="21+",
    )
    plot_adults_per_dwelling(
        release,
        extended_safe,
        pre_tag=EXTENDED21_PRE_TAG,
        with_postcovid=False,
        lfooter="Australia. Original series. Adults aged 21+ (ERP). " + EXT_LFOOTER,
        rfooter_extra=EXT_SOURCES,
    )
    plot_dwelling_vs_adults_21_growth(
        release,
        extended_safe,
        pre_tag=EXTENDED21_PRE_TAG,
        plot_from=extended_safe.pct_change(QUARTERS_PER_YEAR).dropna().index[0],
        lfooter="Australia. Original series. Through-the-year growth. " + EXT_LFOOTER,
        rfooter_extra=EXT_SOURCES,
    )


# --- table of contents, in run order
CHARTS = (
    (breakeven_dwellings, ()),
    (breakeven_shaded, ()),
    (breakeven_by_state, ()),
    (restore_ratio_deficit, ()),
    (extended_history, ()),
    (gross_dwelling_requirement, ()),
    (extended_adults_vs_civpop, ()),
    (extended_21, ()),
)
