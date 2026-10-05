"""Overseas Arrivals and Departures, Australia (3401.0): monthly border movements.

Arrivals and departures by category, the permanent and long-term flows, and the 12-month
net of total arrivals less departures as a timely (if rough) proxy for net migration,
against the official Net Overseas Migration (3101.0).
"""

# --- dependencies
from dataclasses import dataclass

import pandas as pd
import readabs as ra
from mgplot import line_plot_finalise, multi_start, postcovid_plot_finalise, seastrend_plot_finalise
from readabs import metacol as mc
from statsmodels.tsa.filters.hp_filter import hpfilter

from au_econ.analysis.decompose import decompose
from au_econ.analysis.henderson import hma
from au_econ.charting.footers import SERIES_TYPE_NOTES
from au_econ.series.nom import get_nom

# --- module contract
RELEASE = ("3401", "movements")
TOPICS = ("migration",)
TITLE = "Overseas Movements"

# --- constants
CATALOGUE = "3401.0"
ARRIVALS, DEPARTURES = "340101", "340102"
SOURCE = "ABS: 3401.0"
ORIGINAL = "Original"
RECENT_M = pd.Period("2020-12", freq="M")  # the start of the recent window
PLOT_TIMES_M = (0, RECENT_M)
RECENT_MONTHS = 88  # about seven years, for the net migration charts
MONTHS_PER_YEAR = 12
THOUSAND = 1_000
PAIR_WIDTHS = [1, 2]
COVID_YEARS = (2020, 2021)
PAIRS = {
    "Total Overseas": (
        ("Number of movements ;  Total Arrivals ;", ARRIVALS),
        ("Number of movements ;  Total Departures ;", DEPARTURES),
    ),
    "Short-term residents": (
        ("Number of movements ;  Short-term Residents returning ;", ARRIVALS),
        ("Number of movements ;  Short-term Residents departing ;", DEPARTURES),
    ),
    "Short-term visitors": (
        ("Number of movements ;  Short-term Visitors arriving ;", ARRIVALS),
        ("Number of movements ;  Short-term Visitors departing ;", DEPARTURES),
    ),
    "Permanent and Long-term": (
        ("Number of movements ;  Permanent and Long-term Arrivals ;", ARRIVALS),
        ("Number of movements ;  Permanent and Long-term Departures ;", DEPARTURES),
    ),
}
PERMANENT_LONG_TERM = "Permanent and Long-term"
TOTAL_ARRIVALS, TOTAL_DEPARTURES = PAIRS["Total Overseas"]
COVID_START, COVID_END = pd.Period("2020-03", freq="M"), pd.Period("2024-09", freq="M")
HP_LAMBDA = 129600  # monthly data
HMA_TERMS = 25


@dataclass(frozen=True)
class MovementsData:
    """The arrivals and departures tables, keyed by table name, and their combined metadata."""

    tables: dict[str, pd.DataFrame]
    meta: pd.DataFrame


# --- data
def fetch() -> MovementsData:
    """Fetch the arrivals and departures tables (each on its own: the release has many more)."""
    tables, metas = {}, []
    for table in (ARRIVALS, DEPARTURES):
        data, meta = ra.read_abs_cat(CATALOGUE, single_excel_only=table, verbose=False)
        if table not in data or data[table].empty:
            raise ValueError(f"ABS {CATALOGUE}: table {table} not returned")
        tables[table] = data[table]
        metas.append(meta)
    print(f"Arrivals/Departures current to: {tables[ARRIVALS].index[-1]}")
    return MovementsData(tables=tables, meta=pd.concat(metas).drop_duplicates(subset=[mc.id]))


# --- helpers
def _recalibrated[T: (pd.Series, pd.DataFrame)](data: T, units: str) -> tuple[T, str]:
    result, units = ra.recalibrate(data, units)
    if not isinstance(result, type(data)):
        raise TypeError(f"recalibrate returned {type(result).__name__}")
    return result, units


def _select(data: MovementsData, did: str, table: str, **kwargs: bool) -> tuple[pd.Series, str]:
    """One Original movements series, by description and table, with its units."""
    search = {did: mc.did, table: mc.table, ORIGINAL: mc.stype}
    _table, series_id, units = ra.find_abs_id(data.meta, search, **kwargs)
    return data.tables[table][series_id], units


def _net_arrivals(data: MovementsData) -> pd.Series:
    """Total arrivals less total departures, as a 12-month rolling sum in thousands."""
    (arrivals_did, arrivals_table), (departures_did, departures_table) = TOTAL_ARRIVALS, TOTAL_DEPARTURES
    arrivals = _select(data, arrivals_did, arrivals_table, verbose=False)[0]
    departures = _select(data, departures_did, departures_table, verbose=False)[0]
    return ((arrivals - departures).rolling(MONTHS_PER_YEAR).sum() / THOUSAND).dropna()


def _permanent_long_term_charts(title: str, units: str, pair: pd.DataFrame) -> None:
    """Net monthly permanent and long-term flows, and an in-house seasonal decomposition of each."""
    net, net_units = _recalibrated(pair.iloc[:, 0] - pair.iloc[:, 1], units)
    multi_start(
        pd.DataFrame(
            {
                "Net Monthly Arrivals-Departures": net,
                "12m Rolling Mean": net.rolling(MONTHS_PER_YEAR, min_periods=MONTHS_PER_YEAR).mean(),
            }
        ),
        function=line_plot_finalise,
        starts=PLOT_TIMES_M,
        title=f"{title}: Net Monthly Arrivals-Departures",
        ylabel=f"{net_units} / month",
        rfooter=SOURCE,
        lfooter=f"Australia. {ORIGINAL} series. ",
        width=PAIR_WIDTHS,
        annotate=True,
        y0=True,
        pre_tag="arr",
    )
    selector = "Seasonally Adjusted"
    selected = {}
    for column, series in pair.items():
        decomposed = decompose(series.dropna(), arima_extend=True, ignore_years=COVID_YEARS)[[selector, "Trend"]]
        selected[column] = decomposed[selector]
        multi_start(
            decomposed,
            function=seastrend_plot_finalise,
            starts=PLOT_TIMES_M,
            title=f"{column}: Seasonal Decomposition",
            ylabel=f"{units} / month",
            rfooter=SOURCE,
            lfooter="Australia. ",
            y0=True,
            pre_tag="arr",
        )
    multi_start(
        pd.DataFrame(selected),
        function=line_plot_finalise,
        starts=PLOT_TIMES_M,
        title=f"{title} movements: {selector}",
        ylabel=f"{units} / month",
        rfooter=SOURCE,
        annotate=True,
        lfooter=f"Australia. In-house seasonal decomposition. {SERIES_TYPE_NOTES[selector]} ",
        y0=True,
        pre_tag="arr",
    )


def _net_migration_chart(frame: pd.DataFrame, *, title: str, lfooter: str) -> None:
    frame, units = _recalibrated(frame, "Thousands")
    multi_start(
        frame,
        function=line_plot_finalise,
        starts=(0, -RECENT_MONTHS),
        title=title,
        ylabel=f"{units} / year",
        dropna=True,
        width=PAIR_WIDTHS,
        y0=True,
        annotate=True,
        legend=True,
        lfooter=lfooter,
        rfooter=SOURCE,
        pre_tag="arr",
    )


# --- charts
def headline_pairs(data: MovementsData) -> None:
    """Chart arrivals against departures by category, and their 12-month net flow."""
    for title, plotable in PAIRS.items():
        pair = pd.DataFrame()
        units = ""
        for did, table in plotable:
            series, units = _select(data, did, table)
            pair[did.split(";")[-2].strip()] = series
        pair, units = _recalibrated(pair, units)
        multi_start(
            pair,
            function=line_plot_finalise,
            starts=PLOT_TIMES_M,
            title=f"{title}: Arrivals and Departures",
            ylabel=f"{units} / month",
            rfooter=SOURCE,
            lfooter=f"Australia. {ORIGINAL} series. ",
            legend=True,
            pre_tag="arr",
        )
        annual = pair.rolling(MONTHS_PER_YEAR, min_periods=MONTHS_PER_YEAR).sum()
        net_annual, net_units = _recalibrated(annual.iloc[:, 0] - annual.iloc[:, 1], units)
        multi_start(
            net_annual,
            function=line_plot_finalise,
            starts=PLOT_TIMES_M,
            title=f"{title}: Arrivals-Departures (12m rolling sum)",
            ylabel=f"{net_units} / year",
            rfooter=SOURCE,
            lfooter=f"Australia. {ORIGINAL} series. ",
            annotate=True,
            y0=True,
            pre_tag="arr",
        )
        if title == PERMANENT_LONG_TERM:
            _permanent_long_term_charts(title, units, pair)


def individual_movements(data: MovementsData) -> None:
    """Chart every arrivals and departures series: its history, and against its pre-COVID trend."""
    for table in (ARRIVALS, DEPARTURES):
        for did in data.meta.loc[data.meta[mc.table] == table, mc.did]:
            raw, units = _select(data, did, table, exact_match=True, verbose=False)
            series, units = _recalibrated(raw, units)
            title = did.split(";")[-2]
            multi_start(
                series,
                starts=PLOT_TIMES_M,
                function=line_plot_finalise,
                title=title,
                ylabel=f"{units} / month",
                rfooter=SOURCE,
                lfooter=f"Australia. {ORIGINAL} series. ",
                annotate=True,
                y0=True,
                pre_tag="arr",
            )
            postcovid_plot_finalise(
                series,
                title=title,
                ylabel=f"{units} / month",
                rfooter=SOURCE,
                lfooter=f"Australia. {ORIGINAL} series. ",
                y0=True,
                pre_tag="arr",
            )


def net_migration_hp(data: MovementsData) -> None:
    """Chart 12-month net arrivals with an HP-filter trend, fitted separately either side of COVID."""
    net = _net_arrivals(data)
    pre_covid, post_covid = net[net.index < COVID_START], net[net.index > COVID_END]
    _, pre_trend = hpfilter(pre_covid, lamb=HP_LAMBDA)
    _, post_trend = hpfilter(post_covid, lamb=HP_LAMBDA)
    trend = pd.concat([pd.Series(pre_trend, index=pre_covid.index), pd.Series(post_trend, index=post_covid.index)])
    _net_migration_chart(
        pd.DataFrame({"12m Rolling Net Arrivals": net, "HP Filter Trend": trend}),
        title="Net Migration Proxy: 12m Rolling Net Arrivals (HP Filtered)",
        lfooter="Australia. Original series. Net arrivals: total arrivals minus total departures. "
        "HP filter excludes Mar 2020 to Sep 2024. ",
    )


def net_migration_hma(data: MovementsData) -> None:
    """Chart 12-month net arrivals with a 25-term Henderson moving average trend."""
    net = _net_arrivals(data)
    _net_migration_chart(
        pd.DataFrame({"12m Rolling Net Arrivals": net, f"{HMA_TERMS}-term HMA Trend": hma(net, HMA_TERMS)}),
        title="Net Migration Proxy: 12m Rolling Net Arrivals (HMA Smoothed)",
        lfooter="Australia. Original series. Net arrivals: total arrivals minus total departures. "
        f"{HMA_TERMS}-term Henderson moving average. ",
    )


def nplt_vs_nom(data: MovementsData) -> None:
    """Chart net permanent and long-term arrivals (12-month sum) against Net Overseas Migration (3101.0)."""
    (arrivals_did, arrivals_table), (departures_did, departures_table) = PAIRS[PERMANENT_LONG_TERM]
    arrivals = _select(data, arrivals_did, arrivals_table)[0]
    departures = _select(data, departures_did, departures_table)[0]
    net_plt = (arrivals - departures).rolling(MONTHS_PER_YEAR).sum() / THOUSAND
    nom_quarterly, _units, _stype = get_nom()
    nom, _ = _recalibrated(ra.qtly_to_monthly(nom_quarterly), "Persons")
    frame, units = _recalibrated(
        pd.DataFrame(
            {
                "Net Permanent and Long-term Arrivals (12m rolling)": net_plt,
                "Net Overseas Migration (4Q rolling sum)": nom,
            }
        ),
        "Thousands",
    )
    multi_start(
        frame,
        function=line_plot_finalise,
        starts=(0, -RECENT_MONTHS),
        title="Net Permanent and Long-term Arrivals vs Net Overseas Migration",
        ylabel=f"{units} / year",
        rheader="The ABS cautions against using NPLT as a migration proxy.",
        dropna=True,
        width=[1.5, 2],
        style=["-.", "-"],
        y0=True,
        annotate=True,
        legend=True,
        lfooter="Australia. Original series. Net PLT: 12m rolling sum. NOM: 4-quarter rolling sum. ",
        rfooter="ABS: 3101.0, 3401.0",
        pre_tag="multi",
    )


# --- table of contents, in run order
CHARTS = (
    (headline_pairs, ()),
    (individual_movements, ()),
    (net_migration_hp, ()),
    (net_migration_hma, ()),
    (nplt_vs_nom, ()),
)
