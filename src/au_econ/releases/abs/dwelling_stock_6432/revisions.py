"""Completions against net additions to the stock (implied knock-downs), and revisions to net new dwellings."""

# --- dependencies
from typing import TYPE_CHECKING

import pandas as pd
import readabs as ra
from mgplot import bar_plot_finalise, line_plot_finalise, multi_start, revision_plot_finalise
from readabs import metacol as mc
from readabs.download_cache import CacheError, HttpError

from au_econ.charting.windows import quarterly_plot_times
from au_econ.releases.abs.dwelling_stock_6432.common import (
    COMPLETIONS_CATALOGUE,
    DWELLINGS_CATALOGUE,
    DWELLINGS_DID,
    LEGEND_SMALL,
    PERCENT,
    QUARTERS_PER_YEAR,
    STOCK_TABLE,
    THOUSAND,
    THOUSAND_UNITS,
    get_completions,
    get_dwellings_count,
    sources,
)

if TYPE_CHECKING:
    from au_econ.sources.abs import AbsRelease

# --- constants
CATALOGUE = "6432.0"
REVISION_QUARTERS = 13
REVISION_VINTAGES = 6
SEASONALITY_VINTAGES = 20
REVISION_LEGEND = {"loc": "best", "fontsize": 9}


def capture_dwelling_revisions(did: str, how_far_back: int = REVISION_VINTAGES) -> tuple[pd.DataFrame, str]:
    """Return up to how_far_back ABS vintages of a 6432.0 series, newest first, with its units.

    6432.0 names its past releases "<mon>-quarter-<year>", so the history string is built in
    that form; the loop stops once no older release can be read.
    """
    revisions, units, history = pd.DataFrame(), "", None
    for _ in range(how_far_back):
        try:
            data, meta = ra.read_abs_cat(CATALOGUE, single_excel_only=STOCK_TABLE, history=history)
        except HttpError, CacheError:  # no older release at that address
            break
        _table, series_id, units = ra.find_abs_id(meta, {did: mc.did, STOCK_TABLE: mc.table})
        last = data[STOCK_TABLE].index[-1]
        revisions[f"ABS print for {last.strftime('%Y-%b')}"] = data[STOCK_TABLE][series_id]
        previous = last - 1
        history = f"{previous.strftime('%b').lower()}-quarter-{previous.year}"
    return revisions, units


# --- charts
def completions_vs_net_additions(release: AbsRelease) -> None:
    """Chart completions against net new dwellings (4-quarter sums), and the implied knock-downs between them."""
    completions = get_completions()
    net_new = get_dwellings_count(release).diff(1).dropna()
    frame = pd.DataFrame(
        {
            "Building completions": completions.rolling(QUARTERS_PER_YEAR).sum(),
            "Net new dwellings": net_new.rolling(QUARTERS_PER_YEAR).sum(),
        }
    ).dropna()
    frame["Implied knock-downs"] = frame["Building completions"] - frame["Net new dwellings"]
    frame_plot, units = ra.recalibrate(frame.copy(), "Number")
    multi_start(
        frame_plot,
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title="Building completions vs net new dwellings",
        ylabel=f"Dwellings per year\n(4-quarter rolling sum, {units.lower()}s)",
        width=[2, 2, 1.5],
        style=["-", "-", "--"],
        annotate=True,
        rounding=1,
        rfooter=sources(DWELLINGS_CATALOGUE, COMPLETIONS_CATALOGUE),
        lfooter="Australia. Original series. Rolling 4-quarter sum. "
        "Knock-downs = completions less net additions to the dwelling stock. ",
        legend=LEGEND_SMALL,
        y0=True,
    )


def dwelling_revisions(release: AbsRelease) -> None:
    """Chart revisions to net new dwellings across the last six ABS vintages."""
    stock, units = capture_dwelling_revisions(DWELLINGS_DID)
    if units not in THOUSAND_UNITS:
        raise ValueError(f"Unexpected dwelling units: {units}")
    net_new, net_units = ra.recalibrate((stock * THOUSAND).diff(1).tail(REVISION_QUARTERS), "Number")
    revision_plot_finalise(
        data=net_new,
        ylabel=f"Net new dwellings per quarter ({net_units.lower()}s)",
        title="Data revisions: Net new dwellings",
        rfooter=release.source,
        lfooter="Australia. Original series. "
        "Net new dwellings = quarter-on-quarter change in the dwelling stock. ",
        legend=REVISION_LEGEND,
        pre_tag="revisions",
        y0=True,
    )


def dwelling_revision_seasonality(release: AbsRelease) -> None:
    """Chart the average first revision to net new dwellings by quarter of the year, flagging the latest print.

    The first revision is the change from a quarter's first print to the next release.
    """
    stock, _units = capture_dwelling_revisions(DWELLINGS_DID, how_far_back=SEASONALITY_VINTAGES)
    net = (stock * THOUSAND).diff(1)  # one column per vintage
    last_quarter = {column: net[column].last_valid_index() for column in net.columns}
    column_for = {quarter: column for column, quarter in last_quarter.items()}
    records: list[tuple[pd.Period, float]] = []
    for quarter, column in column_for.items():
        if not isinstance(quarter, pd.Period):
            raise TypeError("Expected quarterly Periods")
        if (quarter + 1) in column_for:
            first_print = net[column][quarter]
            next_release = net[column_for[quarter + 1]][quarter]
            records.append((quarter, (next_release - first_print) / first_print * PERCENT))
    first_revisions = pd.DataFrame(records, columns=["refq", "pct"]).set_index("refq")
    first_revisions["Q"] = [period.quarter for period in first_revisions.index]
    means = first_revisions.groupby("Q")["pct"].mean()
    means.index = [f"Q{i}" for i in means.index]

    newest = net.columns[0]
    latest_quarter = last_quarter[newest]
    if not isinstance(latest_quarter, pd.Period):
        raise TypeError("Expected a quarterly Period")
    latest_first_print = net[newest][latest_quarter]
    quarter_mean = means.get(f"Q{latest_quarter.quarter}", float("nan"))
    implied = latest_first_print * (1 + quarter_mean / PERCENT)
    bar_plot_finalise(
        means,
        annotate=True,
        rounding=1,
        above=False,
        title="Net new dwellings: average first revision by quarter",
        ylabel="First revision, first print to next release (%)",
        rfooter=release.source,
        lfooter=f"Australia. Original series. {len(net.columns)} ABS vintages. "
        "First revision = change from a quarter's first print to the next release. ",
        lheader=f"Latest first print {latest_quarter}: {latest_first_print:,.0f} -> "
        f"~{implied:,.0f} expected after a typical Q{latest_quarter.quarter} revision",
        y0=True,
        pre_tag="revisions",
        tag="seasonality",
    )


# --- table of contents, in run order
CHARTS = (
    (completions_vs_net_additions, ()),
    (dwelling_revisions, ()),
    (dwelling_revision_seasonality, ()),
)
