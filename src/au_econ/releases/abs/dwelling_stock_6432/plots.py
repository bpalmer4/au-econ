"""Plotting helpers shared by the Dwelling Stock chart files: per-dwelling ratios, growth, and breakeven charts."""

# --- dependencies
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd
import readabs as ra
from mgplot import (
    abbreviate_state,
    bar_plot,
    finalise_plot,
    line_plot,
    line_plot_finalise,
    postcovid_plot_finalise,
)
from mgplot.utilities import get_color_list

from au_econ.analysis.henderson import hma
from au_econ.charting.windows import quarterly_plot_times
from au_econ.releases.abs.dwelling_stock_6432.common import (
    BE_DEFINITION,
    BE_FORMULA,
    DWELLINGS_CATALOGUE,
    LEGEND_SMALL,
    NATIONAL,
    PERCENT,
    QUARTERS_PER_YEAR,
    THOUSAND,
    ComponentsFn,
    breakeven_components,
    get_adult_pop_21_q,
    get_civ_pop_15_m,
    get_dwellings_count,
    get_published_dwellings,
    sources,
)
from au_econ.series.population import get_civ15

if TYPE_CHECKING:
    from au_econ.sources.abs import AbsRelease

# --- constants
GROWTH_FROM = pd.Period("2012Q1", freq="Q-DEC")
SHADE_HMA_TERMS = 9
SHADE_ALPHA = 0.20
LABEL_PAD_SHARE = 0.04  # of the y range, above the upper line for each year's label
ROTATED_HEADROOM, FLAT_HEADROOM = 6, 2  # multiples of the label pad left above the top label
STANDARD_STARTS = quarterly_plot_times
WINDOW_TAGS = ("complete", "recent")


def plot_adults_per_dwelling(
    release: AbsRelease,
    dwellings: pd.Series | None = None,
    *,
    pre_tag: str = "",
    with_postcovid: bool = True,
    lfooter: str | None = None,
    rfooter_extra: tuple[str, ...] = (),
) -> None:
    """Plot adults (21+) per dwelling, against the pre-COVID trajectory too unless with_postcovid is False."""
    dwellings = get_dwellings_count(release) if dwellings is None else dwellings
    ratio = (get_adult_pop_21_q() / dwellings).dropna()
    common: dict[str, Any] = {
        "ylabel": "Persons aged 21+ per dwelling",
        "rfooter": sources(DWELLINGS_CATALOGUE, "6202.0", "3101.0", *rfooter_extra),
        "lfooter": lfooter or "Australia. Original series. Adults defined as persons aged 21 years and over. ",
        "annotate": True,
        "rounding": 3,
        "pre_tag": pre_tag,
    }
    line_plot_finalise(ratio, title="Adults per Dwelling", **common)
    if with_postcovid:
        postcovid_plot_finalise(ratio, title="Adults per Dwelling vs pre-COVID trajectory", **common)


def plot_civ_pop_15_per_dwelling(
    release: AbsRelease,
    dwellings: pd.Series | None = None,
    *,
    pre_tag: str = "",
    with_postcovid: bool = True,
    lfooter: str | None = None,
    rfooter_extra: tuple[str, ...] = (),
) -> None:
    """Plot civilian population 15+ per dwelling, and (unless with_postcovid is False) its pre-COVID trajectory."""
    civ_pop_q = ra.monthly_to_qtly(get_civ_pop_15_m(), f="mean")
    dwellings = get_dwellings_count(release) if dwellings is None else dwellings
    ratio = (civ_pop_q / dwellings).dropna()
    common: dict[str, Any] = {
        "ylabel": "Persons aged 15+ per dwelling",
        "rfooter": sources(DWELLINGS_CATALOGUE, "6202.0", *rfooter_extra),
        "lfooter": lfooter or "Australia. Original series. Civilian population aged 15 years and over. ",
        "annotate": True,
        "rounding": 3,
        "pre_tag": pre_tag,
    }
    line_plot_finalise(ratio, title="Civilian Population 15+ per Dwelling", **common)
    if with_postcovid:
        postcovid_plot_finalise(
            ratio, title="Civilian Population 15+ per Dwelling vs pre-COVID trajectory", **common
        )


def _growth_chart(
    growth: pd.DataFrame, *, title: str, rfooter: str, lfooter: str, plot_from: pd.Period | None, pre_tag: str
) -> None:
    line_plot_finalise(
        growth,
        title=title,
        ylabel="Through-the-year growth (%)",
        rfooter=rfooter,
        lfooter=lfooter,
        annotate=True,
        rounding=2,
        y0=True,
        plot_from=plot_from,
        pre_tag=pre_tag,
    )


def plot_dwelling_vs_civ_pop_15_growth(
    release: AbsRelease,
    dwellings: pd.Series | None = None,
    *,
    pre_tag: str = "",
    plot_from: pd.Period | None = GROWTH_FROM,
    lfooter: str | None = None,
    rfooter_extra: tuple[str, ...] = (),
) -> None:
    """Plot through-the-year growth of the dwelling stock against the civilian population 15+."""
    civ_pop_q = ra.monthly_to_qtly(get_civ15()[0], f="mean")
    dwellings = get_published_dwellings(release) if dwellings is None else dwellings
    growth = pd.DataFrame(
        {
            "Dwelling stock": dwellings.pct_change(QUARTERS_PER_YEAR) * PERCENT,
            "Civilian population 15+": civ_pop_q.pct_change(QUARTERS_PER_YEAR) * PERCENT,
        }
    ).dropna(how="all")
    _growth_chart(
        growth,
        title="Annual growth: Dwelling stock vs Civilian population 15+",
        rfooter=sources(DWELLINGS_CATALOGUE, "6202.0", *rfooter_extra),
        lfooter=lfooter
        or (
            "Australia. Original series. Through-the-year (4-quarter) growth. "
            "Civilian population 15+ aggregated from monthly to quarterly mean. "
        ),
        plot_from=plot_from,
        pre_tag=pre_tag,
    )


def plot_dwelling_vs_adults_21_growth(
    release: AbsRelease,
    dwellings: pd.Series | None = None,
    *,
    pre_tag: str = "",
    plot_from: pd.Period | None = GROWTH_FROM,
    lfooter: str | None = None,
    rfooter_extra: tuple[str, ...] = (),
) -> None:
    """Plot through-the-year growth of the dwelling stock against adults 21+."""
    adults_q = get_adult_pop_21_q()
    dwellings = get_published_dwellings(release) if dwellings is None else dwellings
    growth = pd.DataFrame(
        {
            "Dwelling stock": dwellings.pct_change(QUARTERS_PER_YEAR) * PERCENT,
            "Adults 21+": adults_q.pct_change(QUARTERS_PER_YEAR) * PERCENT,
        }
    ).dropna(how="all")
    _growth_chart(
        growth,
        title="Annual growth: Dwelling stock vs Adults 21+",
        rfooter=sources(DWELLINGS_CATALOGUE, "6202.0", "3101.0", *rfooter_extra),
        lfooter=lfooter
        or (
            "Australia. Original series. Through-the-year (4-quarter) growth. "
            "Adults 21+: total resident 21+, estimated from civ pop 15+. "
        ),
        plot_from=plot_from,
        pre_tag=pre_tag,
    )


def plot_net_new_vs_breakeven(
    net_new: pd.Series,
    breakeven: pd.Series,
    *,
    be_header: str,
    be_pre_tag: str,
    starts: tuple[int, ...] = STANDARD_STARTS,
    lfooter_note: str = BE_FORMULA,
    rfooter_extra: tuple[str, ...] = (),
    pop_sources: tuple[str, ...] = ("6202.0",),
    pop_label: str = "15+",
    geo: str = NATIONAL,
) -> None:
    """Plot net new dwellings (bars) with the breakeven line, from each start."""
    frame = pd.DataFrame({"Net new dwellings": net_new, "Breakeven new dwellings": breakeven}).dropna()
    frame_plot, units = ra.recalibrate(frame.copy(), "Number")
    if not isinstance(frame_plot, pd.DataFrame):
        raise TypeError("recalibrate returned a Series")
    for start, tag in zip(starts, WINDOW_TAGS, strict=False):
        window = frame_plot.iloc[start:]
        line_color, bar_color = get_color_list(2)  # mgplot's palette: the line first, the bars second
        axes = bar_plot(window["Net new dwellings"], color=bar_color, annotate=False, label_series=True)
        line_plot(
            window["Breakeven new dwellings"], ax=axes, color=[line_color], width=2.5, annotate=True, rounding=1
        )
        finalise_plot(
            axes,
            title=f"Net new dwellings vs breakeven ({pop_label})"
            + ("" if geo == NATIONAL else f": {abbreviate_state(geo)}"),
            ylabel=f"Dwellings per quarter ({units.lower()}s)",
            rfooter=sources(DWELLINGS_CATALOGUE, *pop_sources, *rfooter_extra),
            lfooter="Australia. Original series. " + lfooter_note,
            lheader=be_header,
            rheader=f"Breakeven: {frame.iloc[-1, 1]:,.0f}/qtr;  net new: {frame.iloc[-1, 0]:,.0f}/qtr",
            legend=LEGEND_SMALL,
            y0=True,
            pre_tag=be_pre_tag,
            tag=tag,
        )


def plot_breakeven_shaded(
    release: AbsRelease,
    *,
    start: int = 0,
    hma_terms: int = SHADE_HMA_TERMS,
    drop_last: int = 1,
    be_pre_tag: str = "be-shade-",
    dwellings: pd.Series | None = None,
    label_rotation: int = 0,
    lfooter_extra: str = "",
    rfooter_extra: tuple[str, ...] = (),
    components_fn: ComponentsFn = breakeven_components,
    be_definition: str = BE_DEFINITION,
    pop_sources: tuple[str, ...] = ("6202.0",),
    pop_label: str = "15+",
    geo: str = NATIONAL,
    label_round: int = 0,
) -> None:
    """Plot breakeven against Henderson-smoothed net new dwellings, the gap shaded, with each year's balance.

    The annual figure is the sum over a completed calendar year's four quarters of
    (smoothed net new - breakeven): the shaded area the eye integrates.
    """
    net_new, breakeven, _smooth, _raw = components_fn(release, dwellings, drop_last=drop_last)
    raw = pd.DataFrame({"breakeven": breakeven, "net": net_new}).dropna()
    raw["net_hma"] = hma(raw["net"], hma_terms)
    raw = raw.iloc[start:]
    plot_df, units = ra.recalibrate(
        raw[["net_hma", "breakeven"]]
        .rename(columns={"net_hma": "Trend net new dwellings", "breakeven": "Breakeven new dwellings"})
        .copy(),
        "Number",
    )
    if not isinstance(plot_df, pd.DataFrame):
        raise TypeError("recalibrate returned a Series")
    axes = line_plot(
        plot_df,
        style=["-", "-"],
        label_series=True,
        annotate=[True, True],
        rounding=1,
    )
    ordinals = np.array([period.ordinal for period in plot_df.index])
    lower = plot_df["Breakeven new dwellings"].to_numpy()
    upper = plot_df["Trend net new dwellings"].to_numpy()
    for where, color, label in (
        (upper >= lower, "seagreen", "Above breakeven"),
        (upper < lower, "darkred", "Below breakeven"),
    ):
        axes.fill_between(
            ordinals,
            lower,
            upper,
            where=where,
            interpolate=True,
            color=color,
            alpha=SHADE_ALPHA,
            linewidth=0,
            label=label,
        )

    years = np.array([period.year for period in raw.index])
    raw_ordinals = np.array([period.ordinal for period in raw.index])
    tops = plot_df.max(axis=1).to_numpy()
    gaps = (raw["net_hma"] - raw["breakeven"]).to_numpy()
    y_low, y_high = axes.get_ylim()
    pad = (y_high - y_low) * LABEL_PAD_SHARE
    label_top = y_high
    for year in np.unique(years):
        mask = years == year
        if mask.sum() != QUARTERS_PER_YEAR:  # completed calendar years only
            continue
        total = gaps[mask].sum()
        y_text = tops[mask].max() + pad
        label_top = max(label_top, y_text)
        axes.text(
            raw_ordinals[mask].mean(),
            y_text,
            f"{total / THOUSAND:+,.{label_round}f}k",
            ha="center",
            va="bottom",
            rotation=label_rotation,
            fontsize="x-small",
            fontweight="bold",
            color="seagreen" if total >= 0 else "darkred",
        )
    top_pad = pad * (ROTATED_HEADROOM if label_rotation else FLAT_HEADROOM)  # rotated labels need more room
    finalise_plot(
        axes,
        title=f"Quarterly net new dwellings vs breakeven: annual balance ({pop_label})"
        + ("" if geo == NATIONAL else f": {abbreviate_state(geo)}"),
        ylabel=f"Dwellings per quarter ({units.lower()}s)",
        ylim=(y_low, label_top + top_pad),
        rfooter=sources(DWELLINGS_CATALOGUE, *pop_sources, *rfooter_extra),
        lfooter=f"Australia. Original series. Net new: {hma_terms}-term Henderson MA. " + lfooter_extra,
        lheader=be_definition + (" Latest quarter excluded." if drop_last else ""),
        legend=LEGEND_SMALL,
        y0=True,
        pre_tag=be_pre_tag,
    )


def plot_adults_vs_civpop_per_dwelling(
    dwellings: pd.Series,
    *,
    pre_tag: str = "",
    lfooter: str | None = None,
    rfooter_extra: tuple[str, ...] = (),
) -> None:
    """Plot adults (21+) and civilian population (15+) per dwelling as two lines."""
    ratios = pd.DataFrame(
        {
            "Adults (21+) per dwelling": get_adult_pop_21_q() / dwellings,
            "Civilian population (15+) per dwelling": ra.monthly_to_qtly(get_civ_pop_15_m(), f="mean") / dwellings,
        }
    ).dropna(how="all")
    line_plot_finalise(
        ratios,
        title="Persons per dwelling: adults (21+) vs civilian population (15+)",
        ylabel="Persons per dwelling",
        annotate=True,
        rounding=3,
        rfooter=sources(DWELLINGS_CATALOGUE, "6202.0", "3101.0", *rfooter_extra),
        lfooter=lfooter
        or "Australia. Original series. Adults: persons aged 21+ (ERP); civilian population: persons aged 15+. ",
        legend=LEGEND_SMALL,
        pre_tag=pre_tag,
    )
