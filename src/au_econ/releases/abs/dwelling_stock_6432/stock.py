"""The dwelling stock: headline value, price and count; states; people per dwelling; stock against population."""

# --- dependencies
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
import readabs as ra
from mgplot import (
    abbreviate_state,
    bar_plot_finalise,
    finalise_plot,
    get_color,
    line_plot,
    line_plot_finalise,
    state_abbrs,
    state_names,
)
from readabs import metacol as mc

from au_econ.releases.abs.dwelling_stock_6432.common import (
    DWELLINGS_CATALOGUE,
    LEGEND_SMALL,
    LFS_SOURCE,
    ORIGINAL,
    PARITY_LINE,
    PERCENT,
    STOCK_TABLE,
    THOUSAND,
    at_period,
    get_adult_pop_21_q,
    get_published_dwellings,
    sources,
)
from au_econ.releases.abs.dwelling_stock_6432.plots import (
    plot_adults_per_dwelling,
    plot_civ_pop_15_per_dwelling,
    plot_dwelling_vs_civ_pop_15_growth,
)
from au_econ.series.population import get_civ15

if TYPE_CHECKING:
    from matplotlib.typing import ColorType

    from au_econ.sources.abs import AbsRelease

# --- constants
HEADLINE = (
    "Value of dwelling stock; Owned by Households ;  Australia ;",
    "Value of dwelling stock; Owned by All Sectors ;  Australia ;",
    "Value of dwelling stock; Owned by Non-Households ;  Australia ;",
    "Mean price of residential dwellings ;  Australia ;",
    "Number of residential dwellings ;  Australia ;",
)
STATE_ITEMS = (  # (description, position of the state in the description)
    ("Mean price of residential dwellings", 1),
    ("Value of dwelling stock; Owned by All Sectors", 2),
    ("Number of residential dwellings", 1),
)
STATE_LEGEND = {"ncol": 2, "loc": "upper left", "fontsize": "x-small"}
LABEL_GAP_SHARE = 0.035  # of the y range, between stacked end labels
LFS_STATE_TABLES = ("62020002", "62020003", "62020004", "62020005", "62020006", "62020007", "62020008", "62020009")
CIV_POP_DID = "Civilian population aged 15 years and over ;  Persons ;"


def _recalibrated[T: (pd.Series, pd.DataFrame)](data: T, units: str) -> tuple[T, str]:
    result, units = ra.recalibrate(data, units)
    if not isinstance(result, type(data)):
        raise TypeError(f"recalibrate returned {type(result).__name__}")
    return result, units


# --- charts
def headline(release: AbsRelease) -> None:
    """Chart the value of the dwelling stock by owner, the mean price, and the number of dwellings."""
    meta = release.meta
    for item in HEADLINE:
        _table, series_id, units = ra.find_abs_id(meta, {item: mc.did})
        series, units = _recalibrated(release.data[STOCK_TABLE][series_id], units)
        stype = meta[meta[mc.id] == series_id][mc.stype].to_numpy()[0]
        line_plot_finalise(
            series,
            title=item.rsplit(";", maxsplit=2)[0],
            ylabel=units,
            rfooter=release.source,
            lfooter=f"Australia. {stype} series. ",
            pre_tag="headline-",
            annotate=True,
        )


def states(release: AbsRelease) -> None:
    """Chart the mean price, the value of the stock and the number of dwellings, by state."""
    data = release.data[STOCK_TABLE]
    for item, offset in STATE_ITEMS:
        rows = ra.search_abs_meta(release.meta, {item: mc.did, STOCK_TABLE: mc.table})[:-1]  # drop Australia
        names = [abbreviate_state(name) for name in rows[mc.did].str.split(";").str[offset].str.strip()]
        frame = data[rows[mc.id]].copy()
        frame.columns = names
        frame, units = _recalibrated(frame, str(rows[mc.unit].to_numpy()[0]))
        line_plot_finalise(
            frame,
            title=item,
            ylabel=units,
            color=[get_color(name) for name in names],
            tag="states",
            rfooter=release.source,
            legend=STATE_LEGEND,
            lfooter=f"Australia. {rows[mc.stype].to_numpy()[0]} series. ",
            annotate=True,
        )


def adults_per_dwelling(release: AbsRelease) -> None:
    """Chart adults (21+) per dwelling, and against its pre-COVID trajectory."""
    plot_adults_per_dwelling(release)


def civ_pop_15_per_dwelling(release: AbsRelease) -> None:
    """Chart civilian population 15+ per dwelling, and against its pre-COVID trajectory."""
    plot_civ_pop_15_per_dwelling(release)


def dwelling_vs_civ_pop_15_growth(release: AbsRelease) -> None:
    """Chart through-the-year growth of the dwelling stock and the civilian population 15+."""
    plot_dwelling_vs_civ_pop_15_growth(release)


def dwelling_vs_civ_pop_15_index(release: AbsRelease) -> None:
    """Chart the dwelling stock, civilian population 15+ and adults 21+, indexed to the first stock quarter.

    End labels are placed by hand, spread vertically so close end-points do not overprint.
    """
    civ_pop_q = ra.monthly_to_qtly(get_civ15()[0], f="mean")
    adults_q = get_adult_pop_21_q()
    dwellings = get_published_dwellings(release)
    base = dwellings.index[0]
    civ_pop_q = civ_pop_q[civ_pop_q.index >= base]
    adults_q = adults_q[adults_q.index >= base]
    index = pd.DataFrame(
        {
            "Dwelling stock": dwellings / dwellings.loc[base] * PERCENT,
            "Civilian population 15+": civ_pop_q / civ_pop_q.loc[base] * PERCENT,
            "Adults 21+": adults_q / adults_q.loc[base] * PERCENT,
        }
    ).dropna(how="all")
    axes = line_plot(index, annotate=False, plot_from=base)

    endpoints: list[tuple[ColorType, float, float]] = []
    for line in axes.get_lines():  # mgplot plots periods at integer positions, so read the ends back
        xdata, ydata = np.asarray(line.get_xdata()), np.asarray(line.get_ydata())
        if len(ydata) == 0:
            continue
        endpoints.append((line.get_color(), float(xdata[-1]), float(ydata[-1])))
    endpoints.sort(key=lambda end: end[2], reverse=True)
    y_low, y_high = axes.get_ylim()
    gap = (y_high - y_low) * LABEL_GAP_SHARE
    previous_y = None
    for color, x, y in endpoints:
        place_y = y if previous_y is None else min(y, previous_y - gap)
        previous_y = place_y
        axes.annotate(
            f" {y:.1f}",
            xy=(x, place_y),
            xytext=(3, 0),
            textcoords="offset points",
            ha="left",
            va="center",
            fontsize="small",
            color=color,
        )
    finalise_plot(
        axes,
        title="Index: Dwelling stock vs population 15+ and 21+",
        ylabel=f"Index ({base} = 100)",
        rfooter=sources(DWELLINGS_CATALOGUE, "6202.0", "3101.0"),
        lfooter=f"Australia. Original series. Indexed to {base} = 100. "
        "Population aggregated from monthly to quarterly mean. ",
        legend=LEGEND_SMALL,
        axhline=PARITY_LINE,
    )


def adults_per_dwelling_by_state(release: AbsRelease) -> None:
    """Chart civilian population 15+ per dwelling, by state (horizontal bars)."""
    dwellings, dwell_period = {}, None
    for state in state_names:
        _table, series_id, _units = ra.find_abs_id(
            release.meta, {f"Number of residential dwellings ;  {state} ;": mc.did, STOCK_TABLE: mc.table}
        )
        series = release.data[STOCK_TABLE][series_id].dropna() * THOUSAND
        dwellings[state], dwell_period = series.iloc[-1], series.index[-1]
    if not isinstance(dwell_period, pd.Period):
        raise TypeError("Expected a quarterly Period")

    lf_data, lf_meta = ra.read_abs_cat("6202.0", selected_excel=LFS_STATE_TABLES)
    state_tables = {}
    for table, row in lf_meta.drop_duplicates("Table").set_index("Table").iterrows():
        if str(table).endswith("a"):
            continue
        description = str(row["Table Description"])
        for state in state_names:
            if f", {state} -" in description:
                state_tables[state] = str(table)
                break
    adult_period = dwell_period.asfreq("M", how="end")  # the last month of the dwellings quarter
    adults = {}
    for state in state_names:
        table = state_tables[state]
        _table, series_id, _units = ra.find_abs_id(
            lf_meta, {CIV_POP_DID: mc.did, table: mc.table, ORIGINAL: mc.stype}
        )
        adults[state] = at_period(lf_data[table][series_id].dropna() * THOUSAND, adult_period)

    ratio = pd.Series(adults) / pd.Series(dwellings)
    by_state = ratio.rename(index=dict(zip(state_names, state_abbrs, strict=True))).sort_values()
    bar_plot_finalise(
        by_state,
        horizontal=True,
        color=[get_color(name) for name in by_state.index],
        annotate=True,
        above=True,
        rounding=2,
        title="Adults (15+) per Dwelling by State",
        xlabel=f"Civilian population aged 15+ per dwelling (dwellings {dwell_period}, population {adult_period})",
        rfooter=LFS_SOURCE,
        lfooter="Australia. Original series. ",
    )


# --- table of contents, in run order
CHARTS = (
    (headline, ()),
    (states, ()),
    (adults_per_dwelling, ()),
    (civ_pop_15_per_dwelling, ()),
    (dwelling_vs_civ_pop_15_growth, ()),
    (dwelling_vs_civ_pop_15_index, ()),
    (adults_per_dwelling_by_state, ()),
)
