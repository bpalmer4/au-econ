"""Business Indicators, Australia (5676.0): inventories, profits and wages, quarterly.

The survey is published shortly before the National Accounts and is the source of their
private non-farm inventories, so its inventory levels preview the inventories
contribution to GDP growth.
"""

# --- dependencies
import pandas as pd
import readabs as ra
from mgplot import (
    bar_plot_finalise,
    line_plot_finalise,
    multi_start,
    scatter_plot_finalise,
    series_growth_plot_finalise,
)
from readabs import metacol as mc
from readabs.download_cache import CacheError, HttpError

from au_econ.analysis.henderson import hma
from au_econ.charting.footers import SERIES_TYPE_NOTES
from au_econ.charting.titles import fix_abs_title
from au_econ.charting.windows import quarterly_plot_times
from au_econ.series.gdp import get_gdp, get_table
from au_econ.sources.abs import AbsRelease, fetch_release

# --- module contract
RELEASE = ("5676", "bi")
TOPICS = ("business",)
TITLE = "Business Indicators"

# --- constants
CATALOGUE = "5676.0"
SA = "Seasonally Adjusted"
SA_LFOOTER = f"Australia. {SERIES_TYPE_NOTES[SA]} "
PRICE_NOTES = {"Chain Volume Measures": "Chain volume measures. ", "Current Price": "Current prices. "}
COMPANIES = ("CORP", "Companies. ")  # profit before income tax: companies only
PERCENT = 100
THOUSAND = 1_000
HMA_TERM = 7
TOP_OF_LIST = "AAA"  # headline file-name prefix ("aaa-"), first alphabetically: mgplot drops punctuation like "!"
WITH_GDP_SOURCE = "ABS: 5206.0, 5676.0"  # charts that use the National Accounts
SCATTER_LEGEND = {"loc": "upper left", "fontsize": 9}
HEADLINES = (  # (description, a flow: so its level is per quarter)
    ("Inventories ;  Total (State) ;  Total (Industry) ;  Chain Volume Measures ;", False),
    ("Profit before Income Tax ;  Total (State) ;  Total (Industry) ;  Current Price ;  CORP ;", True),
    ("Gross Operating Profits ;  Total (State) ;  Total (Industry) ;  Current Price ;  TOTAL (SCP_SCOPE) ;", True),
    ("Wages ;  Total (State) ;  Total (Industry) ;  Current Price ;", True),
)
WAGES_TABLE, WAGES_DID = "56760017", "Wages ;  Total (State) ;  Total (Industry) ;  Current Price ;"
PROFITS_TABLE = "56760015"
PROFITS_DID = (
    "Gross Operating Profits ;  Total (State) ;  Total (Industry) ;  Current Price ;  TOTAL (SCP_SCOPE) ;"
)
CURRENT_PRICE = "Current Price"
INVENTORY_DID = "Inventories ;  Total (State) ;  Total (Industry) ;  Chain Volume Measures ;  TOTAL (SCP_SCOPE) ;"
NA_INVENTORIES = "5206009_Changes_In_Inventories"
NA_PNF_DID = "Private ;  Non-farm ;  Chain volume measures ;"
NA_TOTAL_DID = "CHANGES IN INVENTORIES: Chain volume measures ;"
QUARTER_END_MONTHS = {1: "mar", 2: "jun", 3: "sep", 4: "dec"}  # for an ABS vintage tag, e.g. "jun-2026"
DOWN_WEIGHT_TOLERANCE = 1e-3  # a factor this close to 1 is no down-weight


# --- data
def fetch() -> AbsRelease:
    """Fetch the release once; every chart function receives it."""
    release = fetch_release(CATALOGUE)
    print("Latest data: ", release.data["5676001"].index[-1])
    return release


# --- helpers
def _recalibrated(series: pd.Series, units: str) -> tuple[pd.Series, str]:
    result, units = ra.recalibrate(series, units)
    if not isinstance(result, pd.Series):
        raise TypeError(f"recalibrate returned {type(result).__name__}")
    return result, units


def _row(release: AbsRelease, did: str, *, exact: bool = True) -> pd.Series:
    """Return the metadata row of the seasonally adjusted series with this description (or containing it)."""
    meta = release.meta
    match = meta[mc.did] == did if exact else meta[mc.did].str.contains(did, regex=False)
    return meta[(meta[mc.stype] == SA) & match].iloc[0]


def _series(release: AbsRelease, row: pd.Series) -> pd.Series:
    return release.data[row[mc.table]][row[mc.id]]


def _selected(release: AbsRelease, table: str, did: str) -> tuple[pd.Series, str]:
    """One seasonally adjusted series by table and description, with its units."""
    _table, series_id, units = ra.find_abs_id(
        release.meta, {table: mc.table, SA: mc.stype, did: mc.did}, verbose=False
    )
    return release.data[table][series_id].dropna(), units


def _dollar_rows(release: AbsRelease, did_part: str, *also: str) -> pd.DataFrame:
    """Return the metadata rows of seasonally adjusted dollar series whose description contains every part."""
    meta = release.meta
    mask = (meta[mc.stype] == SA) & meta[mc.unit].str.contains("$", regex=False)
    for part in (did_part, *also):
        mask &= meta[mc.did].str.contains(part, regex=False)
    return meta[mask]


def _lfooter(did: str) -> str:
    """Return a seasonally adjusted series' lfooter: its price measure and, for profits, the company scope."""
    lfooter = SA_LFOOTER + "".join(note for measure, note in PRICE_NOTES.items() if f"{measure} ;" in did)
    code, note = COMPANIES
    return lfooter + (note if f"{code} ;" in did else "")


def _inventory_level(release: AbsRelease) -> pd.Series:
    """Return the total private non-farm inventory level (CVM)."""
    return _series(release, _row(release, INVENTORY_DID)).dropna()


# --- charts
def headline(release: AbsRelease) -> None:
    """Chart inventories, company profits, gross operating profits and wages: level and growth."""
    for did, flow in HEADLINES:
        row = _row(release, did, exact=False)
        series, units = _recalibrated(_series(release, row), str(row[mc.unit]))
        title, _ = fix_abs_title(f"Business indicators: {row[mc.did]}", "")
        lfooter = _lfooter(str(row[mc.did]))
        multi_start(
            series,
            function=line_plot_finalise,
            starts=quarterly_plot_times,
            title=title,
            ylabel=f"{units}/Quarter" if flow else units,
            pre_tag=TOP_OF_LIST,
            rfooter=release.source,
            lfooter=lfooter,
        )
        series_growth_plot_finalise(
            series,
            plot_from=quarterly_plot_times[1],
            title=f"Growth in {title.title()}",
            pre_tag=TOP_OF_LIST,
            rfooter=release.source,
            lfooter=lfooter,
        )


def profits_v_wages(release: AbsRelease) -> None:
    """Chart profits as a share of profits plus wages, and profits against wages in dollars and as indexes."""
    wages, wage_units = _selected(release, WAGES_TABLE, WAGES_DID)
    profits, profit_units = _selected(release, PROFITS_TABLE, PROFITS_DID)
    wages_name = WAGES_DID.split(";", maxsplit=1)[0].strip()
    profits_name = PROFITS_DID.split(";", maxsplit=1)[0].strip()
    if wage_units != profit_units:
        raise ValueError(f"Units differ: wages {wage_units}, profits {profit_units}")

    share = profits / (profits + wages) * PERCENT
    line_plot_finalise(
        pd.DataFrame({f"{profits_name} share": share, "Henderson moving average": hma(share.dropna(), HMA_TERM)}),
        title="Profits as a share of profits plus wages",
        ylabel="Per cent",
        rfooter=release.source,
        lfooter=f"{SA_LFOOTER}{HMA_TERM}-term Henderson moving average. ",
    )

    if CURRENT_PRICE not in WAGES_DID or CURRENT_PRICE not in PROFITS_DID:
        raise ValueError("Wages and profits must both be Current Price series")
    if "Millions" not in wage_units:
        raise ValueError(f"Expected wages in Millions, got {wage_units}")
    line_plot_finalise(
        pd.DataFrame({"Wages": wages / THOUSAND, "Profits": profits / THOUSAND}),
        title="Profits vs Wages",
        ylabel="$ Billions/Quarter",
        rfooter=release.source,
        lfooter=f"{SA_LFOOTER}Current prices. ",
    )

    if profits.index[0] != wages.index[0]:
        raise ValueError(f"Start dates differ: profits {profits.index[0]}, wages {wages.index[0]}")
    line_plot_finalise(
        pd.DataFrame(
            {
                f"{wages_name} index": wages / wages.iloc[0] * PERCENT,
                f"{profits_name} index": profits / profits.iloc[0] * PERCENT,
            }
        ),
        title="Profits index vs Wages index",
        ylabel="Index",
        rfooter=release.source,
        lfooter=f"{SA_LFOOTER}Current prices. ",
    )


def inventories(release: AbsRelease) -> None:
    """Chart every seasonally adjusted inventory level in chain volume measures."""
    for _, row in _dollar_rows(release, "Inventories", "Chain Volume Measures").iterrows():
        series, units = _recalibrated(_series(release, row), str(row[mc.unit]))
        title, _ = fix_abs_title(str(row[mc.did]), "")
        lfooter = _lfooter(str(row[mc.did]))
        multi_start(
            series,
            function=line_plot_finalise,
            starts=quarterly_plot_times,
            title=title,
            ylabel=units,
            rfooter=release.source,
            lfooter=lfooter,
        )


def inventories_change_vs_na(release: AbsRelease) -> None:
    """Scatter the change in the 5676 inventory level against the National Accounts changes in inventories.

    5676 publishes inventory levels (CVM); the National Accounts publish changes in
    inventories (a CVM flow). The difference of the level is the implied change, against
    the private non-farm component (like for like) and the all-sector total (which also
    has farm and public authorities). CVM levels are not perfectly additive over time, so
    the difference approximates the flow.
    """
    change = _inventory_level(release).diff().dropna()
    na_data, na_meta = get_table(NA_INVENTORIES)

    def scatter_vs(na_did: str, scope: str, lheader: str = "") -> None:
        _, na_id, _ = ra.find_abs_id(na_meta, {na_did: mc.did, SA: mc.stype}, exact_match=True, verbose=False)
        frame = pd.DataFrame({"bi": change, "na": na_data[NA_INVENTORIES][na_id].dropna()}).dropna()
        corr = frame["bi"].corr(frame["na"])
        scatter_plot_finalise(
            frame,
            label="Quarterly change",
            diagonal=True,
            title=f"Inventories Change: Business Indicators vs National Accounts ({scope})",
            xlabel="Business Indicators: Δ inventory level (5676), $m",
            ylabel=f"National Accounts: changes in\ninventories (5206, {scope}), $m",
            legend=SCATTER_LEGEND,
            lheader=lheader,
            rfooter=WITH_GDP_SOURCE,
            lfooter=(
                f"{SA_LFOOTER}CVM. 5676 (private non-farm) Δlevel "
                f"vs 5206 {scope} flow. R²={corr**2:.2f}, n={len(frame)}. "
            ),
        )

    scatter_vs(NA_PNF_DID, "PNF", lheader="PNF = private non-farm.")
    scatter_vs(NA_TOTAL_DID, "All")


def inventories_change_bars(release: AbsRelease) -> None:
    """Chart the quarterly change in total inventories (CVM) as bars: above zero the stock is rising."""
    row = _row(release, INVENTORY_DID)
    change, units = _recalibrated(_series(release, row).dropna().diff().dropna(), str(row[mc.unit]))
    change.name = "Quarterly change"
    multi_start(
        change,
        function=bar_plot_finalise,
        starts=quarterly_plot_times,
        title="Inventories: Quarterly Change",
        ylabel=f"{units}/Quarter",
        annotate=True,
        rounding=1,
        rfooter=release.source,
        lfooter=f"{SA_LFOOTER}Chain volume measures. Change in inventory level. ",
    )


def _history_factor(table: str, gdp_tag: str, level: pd.Series) -> float:
    """Return the factor putting the inventory level on the reference basis of the vintage with the latest GDP."""
    data, meta = ra.read_abs_cat(CATALOGUE, single_excel_only=table, history=gdp_tag, verbose=False)
    row = meta[(meta[mc.did] == INVENTORY_DID) & (meta[mc.stype] == SA)].iloc[0]
    past = data[table][row[mc.id]].dropna()
    common = level.index.intersection(past.index)
    return float((level.loc[common] / past.loc[common]).median())


def inventories_contribution_bi(release: AbsRelease) -> None:
    """Chart the estimated inventories contribution to GDP growth from the 5676 level (a partial preview).

    The difference of the private non-farm level is an implied changes-in-inventories flow;
    its change over lagged real GDP is an early read on the contribution. Farm and public
    inventories arrive with GDP. In the annual re-referencing quarter the 5676 level is on
    the new reference year while the latest GDP is on the old one, so the level is scaled
    back by the median ratio of the current level to the vintage published with the latest
    GDP. Otherwise the factor is 1 and the extra fetch is skipped.
    """
    row = _row(release, INVENTORY_DID)
    level = _series(release, row).dropna()
    gdp_all, _units = get_gdp("CVM", "SA")
    gdp = gdp_all.dropna()
    last = gdp.index[-1]
    if not isinstance(last, pd.Period):
        raise TypeError("Expected a quarterly PeriodIndex for GDP")
    gdp_tag = f"{QUARTER_END_MONTHS[last.quarter]}-{last.year}"

    factor = 1.0
    if gdp.index[-1] < level.index[-1]:
        try:
            factor = _history_factor(str(row[mc.table]), gdp_tag, level)
        except (HttpError, CacheError, OSError, ValueError, KeyError, IndexError) as error:  # chart without it
            print(f"Re-referencing down-weight skipped: {error}")

    flow = (level / factor).diff()
    gdp_lag = gdp.copy()
    gdp_lag.index = gdp_lag.index + 1  # by index, so the leading quarter divides by the last published GDP
    contribution = ((flow - flow.shift(1)) / gdp_lag * PERCENT).dropna()
    contribution.name = "Inventories contribution (BI proxy)"
    down_weight = "none" if abs(factor - 1) < DOWN_WEIGHT_TOLERANCE else f"level x{factor:.3f}"
    multi_start(
        contribution,
        function=bar_plot_finalise,
        starts=quarterly_plot_times,
        title="Estimated Inventories Contribution to GDP Growth",
        ylabel="Percentage points (quarterly)",
        annotate=True,
        rounding=1,
        y0=True,
        rfooter=WITH_GDP_SOURCE,
        lfooter=f"{SA_LFOOTER}Private non-farm Δlevel / lagged GDP, CVM. Down-weight: {down_weight}. ",
    )


def wage_growth(release: AbsRelease) -> None:
    """Chart growth in every seasonally adjusted wages series."""
    for _, row in _dollar_rows(release, "Wages").iterrows():
        series, _units = _recalibrated(_series(release, row), str(row[mc.unit]))
        title, _ = fix_abs_title(str(row[mc.did]), "")
        lfooter = _lfooter(str(row[mc.did]))
        series_growth_plot_finalise(
            series,
            plot_from=quarterly_plot_times[1],
            title=f"Growth: {title}",
            rfooter=release.source,
            lfooter=lfooter,
        )


# --- table of contents, in run order
CHARTS = (
    (headline, ()),
    (profits_v_wages, ()),
    (inventories, ()),
    (inventories_change_vs_na, ()),
    (inventories_change_bars, ()),
    (inventories_contribution_bi, ()),
    (wage_growth, ()),
)
