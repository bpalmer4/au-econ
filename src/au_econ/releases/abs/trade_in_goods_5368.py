"""International Trade in Goods (5368.0): the goods trade balance, and the make-up of goods exports."""

# --- dependencies
import pandas as pd
import readabs as ra
from mgplot import fill_between_plot, finalise_plot, multi_start, seastrend_plot_finalise
from mgplot.utilities import get_color_list
from readabs import metacol as mc

from au_econ.sources.abs import AbsRelease, fetch_release

# --- module contract
RELEASE = ("5368", "goods")
TOPICS = ("trade",)
TITLE = "International Trade in Goods"

# --- constants
CATALOGUE = "5368.0"
plot_times = 0, (4 * -12 - 1)  # full history and the last four years
SUMMARY_TABLE = "536801"
SUMMARY_UNITS = "$ Millions"
EXP_TABLE = "5368012a"
MONTHS_PER_QUARTER = 3
MILLIONS_PER_BILLION = 1000.0
PERCENT = 100
SITC_GROUPS = {
    "Food, bev., oils (SITC 0+1+4)": ["0", "1", "4"],
    "Crude materials (SITC 2)": ["2"],
    "Mineral fuels (SITC 3)": ["3"],
    "Manufactures (SITC 5+6+7+8)": ["5", "6", "7", "8"],
    "Other incl. gold (SITC 9)": ["9"],
}
STACK_LEGEND = {"loc": "upper left", "fontsize": "x-small"}


# --- data
def fetch() -> AbsRelease:
    """Fetch the release once; every chart function receives it."""
    return fetch_release(CATALOGUE)


def _exports_by_group(release: AbsRelease) -> pd.DataFrame:
    """Quarterly merchandise exports, summed into the SITC narrative buckets."""
    meta = release.meta
    meta_t = meta[meta[mc.table] == EXP_TABLE].copy()
    meta_t["sitc"] = meta_t[mc.did].str.extract(r"^(\d) ", expand=False)
    meta_t = meta_t[meta_t["sitc"].notna()]
    monthly = pd.concat(
        {row["sitc"]: release.data[EXP_TABLE][row[mc.id]] for _, row in meta_t.iterrows()},
        axis=1,
    ).sort_index(axis=1)
    if not isinstance(monthly.index, pd.PeriodIndex):
        raise TypeError("Expected a monthly PeriodIndex on the export table")
    # monthly $ millions -> quarterly sums (flow data)
    quarterly = monthly.groupby(monthly.index.asfreq("Q-DEC")).sum(min_count=MONTHS_PER_QUARTER).dropna()
    return pd.concat({name: quarterly[codes].sum(axis=1) for name, codes in SITC_GROUPS.items()}, axis=1)


def _stack(frame: pd.DataFrame, source: str, *, ylabel: str, title: str, tag: str) -> None:
    """Draw the columns as stacked bands, bottom to top in column order."""
    ax = None
    cumulative = pd.Series(0.0, index=frame.index)
    for column, color in zip(frame.columns, get_color_list(len(frame.columns)), strict=True):
        band = pd.DataFrame({"lower": cumulative, "upper": cumulative + frame[column]})
        ax = fill_between_plot(band, ax=ax, color=color, alpha=1.0, label=column)
        cumulative = cumulative + frame[column]
    if ax is None:
        raise ValueError("Nothing to stack")
    finalise_plot(
        ax,
        title=title,
        ylabel=ylabel,
        rfooter=source,
        lfooter="Australia. Original series. Merchandise exports, FOB, quarterly sums. "
        "SITC = Standard International Trade Classification.",
        legend=STACK_LEGEND,
        tag=tag,
    )


# --- charts
def trade_balance(release: AbsRelease) -> None:
    """Chart the balance on goods: seasonally adjusted against trend."""
    meta = release.meta
    subset = meta[meta[mc.did].str.contains("Balance on goods")]
    seas = subset[subset[mc.stype].str.contains("Seasonally")].index[0]
    trend = subset[subset[mc.stype].str.contains("Trend")].index[0]
    data = release.data[SUMMARY_TABLE][[seas, trend]].rename(columns={seas: "Seasonally adjusted", trend: "Trend"})
    data, units = ra.recalibrate(data, SUMMARY_UNITS)
    multi_start(
        data,
        function=seastrend_plot_finalise,
        starts=plot_times,
        title="Trade balance on Goods",
        ylabel=units,
        y0=True,
        lfooter="Australia. Current prices. ",
        rfooter=release.source,
    )


def export_composition(release: AbsRelease) -> None:
    """Chart goods export composition by SITC group: as a share of the total, and in $ billions a quarter."""
    grouped = _exports_by_group(release)
    _stack(
        grouped.div(grouped.sum(axis=1), axis=0) * PERCENT,
        release.source,
        ylabel="Per cent of total goods exports",
        title="Australia goods export composition (SITC, share)",
        tag="share",
    )
    _stack(
        grouped / MILLIONS_PER_BILLION,
        release.source,
        ylabel="A$ billions per quarter",
        title="Australia goods export composition (SITC, A$bn)",
        tag="levels",
    )


# --- table of contents, in run order
CHARTS = (
    (trade_balance, ()),
    (export_composition, ()),
)
