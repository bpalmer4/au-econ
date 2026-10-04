"""National Accounts saving: net saving by sector, saving against investment, and the current account balances."""

# --- dependencies
from functools import reduce
from operator import add
from typing import TYPE_CHECKING, Any

import mgplot as mg
import pandas as pd
import readabs as ra
from mgplot import (
    chart_subdir,
    fill_between_plot,
    finalise_plot,
    line_plot,
    line_plot_finalise,
    multi_start,
    postcovid_plot_finalise,
)
from readabs import metacol as mc
from statsmodels.tsa.filters.hp_filter import hpfilter

from au_econ.charting.windows import quarterly_plot_times
from au_econ.releases.abs.national_accounts_5206.common import (
    AUSTRALIA,
    CP_NOTE,
    EXPENDITURE_CP,
    QUARTERS_PER_YEAR,
    SA_NOTE,
    SA_SHORT,
    SEASONALLY_ADJUSTED,
    data_to,
)
from au_econ.series.gdp import get_gdp

if TYPE_CHECKING:
    from au_econ.sources.abs import AbsRelease

# --- constants
SUBDIR = "Savings"
SA = SEASONALLY_ADJUSTED
PERCENT = 100
NATIONAL_INCOME = "5206011_National_Income_Account"
EXTERNAL = "5206021_External_Account"
NAT_GG = "5206018_Nat_Gen_Govt_Income_Account"
STATE_GG = "5206019_StateLocal_Gen_Govt_Income_Account"
NET_SAVING = "Net saving"

# excess household saving during COVID
EXCESS_FROM = "2014Q4"
EXCESS_THRESHOLD = 20  # $ billion a quarter: a cautious stand-in for the pre-COVID trend
COVID_FROM, COVID_TO, AFTER_FROM = "2020Q1", "2022Q3", "2022Q4"
SAVED_LABEL_AT, SAVED_LABEL_Y = pd.Period("2021Q2", freq="Q"), 30
SPENT_LABEL_AT, SPENT_LABEL_Y = pd.Period("2023Q3", freq="Q"), 10

# saving and investment
HP_LAMBDA = 1600  # quarterly data

# current account balances
GG_CATALOGUE = "5232.0"
GG_CAPITAL = "5232027"  # general government capital account
CA_DID = "Balance on external income account ;"  # the rest of the world's view: minus Australia's CA
GG_SAVING_DIDS = ("Net saving ;", "Consumption of fixed capital ;")  # summed: gross saving
GG_INVESTMENT_DIDS = ("Gross fixed capital formation ;", "Changes in inventories ;")
GG_LEVELS = {  # chart label: (income account table, GFCF data item in the expenditure table)
    "Cwlth (T - G)": (NAT_GG, "General government - National ;  Gross fixed capital formation ;"),
    "State and local (T - G)": (
        STATE_GG,
        "General government - State and local ;  Gross fixed capital formation ;",
    ),
}
GG_CAPITAL_TRANSFERS_DID = "Total net capital transfers ;"
GG_NET_LENDING_DID = "Net lending (+) / net borrowing (-) ;"
GG_NET_INVESTMENT_DIDS = (  # added: GFCF, inventories and land; CFC is subtracted
    "Gross fixed capital formation ;",
    "Changes in inventories ;",
    "Acquisitions less disposals of non-produced non-financial assets ;",
)
GG_CFC_DID = "Consumption of fixed capital ;"
CA_PARTS = {  # chart label: (items added, items subtracted), from the external account
    "Trade balance (X - M)": (["Exports of goods and services ;"], ["Imports of goods and services ;"]),
    "Net primary income": (
        [
            "Primary income payable by non-residents - Compensation of employees ;",
            "Primary income payable by non-residents - Property Income ;",
        ],
        [
            "Primary income receivable by non-residents - Compensation of employees ;",
            "Primary income receivable by non-residents - Property Income ;",
        ],
    ),
    "Net secondary income": (
        ["Secondary income payable by non-residents - Current transfers ;"],
        ["Secondary income receivable by non-residents - Current transfers ;"],
    ),
}


# --- helpers
def _sa(release: AbsRelease, table: str, did: str) -> pd.Series:
    """Return one seasonally adjusted series from a 5206 table, by description."""
    _, series_id, _ = ra.find_abs_id(release.meta, {table: mc.table, SA: mc.stype, did: mc.did}, verbose=False)
    return release.data[table][series_id]


def _total(series: list[pd.Series]) -> pd.Series:
    """Add series together (aligned; a gap in any leaves a gap)."""
    return reduce(add, series)


def _excess_savings(plotable: pd.Series, common: dict[str, Any], units: str) -> None:
    """Draw household saving since 2014, shading saving above and below the threshold after COVID began."""
    recent = plotable.loc[lambda x: x.index >= EXCESS_FROM].copy()
    covid = (recent.index >= COVID_FROM) & (recent.index <= COVID_TO)
    after = recent.index >= AFTER_FROM
    saved = (recent[covid] - EXCESS_THRESHOLD).sum()
    print(f"COVID Household savings: {saved:.0f}$B")
    spent = (recent[after] - EXCESS_THRESHOLD).sum()
    print(f"COVID Household disavings: {spent:.0f}$B {spent / saved:.1%}")

    ax = mg.line_plot(recent)
    for window, colour, at, y, amount in (
        (covid, "cornflowerblue", SAVED_LABEL_AT, SAVED_LABEL_Y, saved),
        (after, "darkred", SPENT_LABEL_AT, SPENT_LABEL_Y, spent),
    ):
        mg.fill_between_plot(
            pd.DataFrame({"threshold": EXCESS_THRESHOLD, "savings": recent[window]}),
            ax=ax,
            color=colour,
            alpha=1.0,
        )
        ax.text(
            x=at.ordinal,  # mgplot maps a PeriodIndex to period ordinals on the x-axis
            y=y,
            s=f"${amount:.0f}B",
            ha="center",
            va="center",
            color="white",
            fontsize=12,
        )
    finalise_plot(
        ax,
        title="Excess household savings during COVID",
        ylabel=units,
        legend=True,
        **{k: v for k, v in common.items() if k != "title"},
    )


def _balance_shares(balances: pd.DataFrame, title: str, lfooter: str, **kwargs: Any) -> None:
    """Draw sectoral balances as a per cent of GDP, quarterly and as four-quarter rolling sums."""
    gdp, _ = get_gdp("CP", "SA")
    versions = {
        "quarterly": (balances, gdp),
        "4Q rolling sum": (balances.rolling(QUARTERS_PER_YEAR).sum(), gdp.rolling(QUARTERS_PER_YEAR).sum()),
    }
    for label, (flows, denominator) in versions.items():
        share = flows.div(denominator, axis=0).mul(PERCENT).dropna()
        multi_start(
            share,
            function=line_plot_finalise,
            starts=quarterly_plot_times,
            title=f"{title}: {label}",
            ylabel="Per cent of GDP",
            legend={"loc": "best", "fontsize": "x-small"},
            y0=True,
            pre_tag="saving-",
            lfooter=f"{lfooter}{data_to(share)}",
            **kwargs,
        )


# --- charts
def savings(release: AbsRelease) -> None:
    """Net saving by sector: level, share of GDP and COVID recovery; household excess saving during COVID."""
    meta = release.meta
    rows = meta[
        (meta[mc.table] == NATIONAL_INCOME) & (meta[mc.stype] == SA) & meta[mc.did].str.contains(NET_SAVING)
    ]
    gdp = get_gdp("CP", "SA")[0]
    with chart_subdir(SUBDIR):
        for description in rows[mc.did]:
            row = rows[rows[mc.did] == description].iloc[0]
            series = release.data[NATIONAL_INCOME][row[mc.id]].rename("Series")
            plotable, units = ra.recalibrate(series, f"{row[mc.unit]} / Qtr")
            title = description.replace(" ;", "").replace("  ", " ").capitalize()
            common: dict[str, Any] = {
                "title": title,
                "y0": True,
                "rfooter": release.source,
                "lfooter": f"{AUSTRALIA}{SA_NOTE}{CP_NOTE}{data_to(plotable)}",
                "pre_tag": "saving-",
            }
            multi_start(
                plotable,
                function=line_plot_finalise,
                starts=quarterly_plot_times,
                ylabel=units,
                annotate=True,
                **common,
            )
            multi_start(
                series / gdp * PERCENT,
                function=line_plot_finalise,
                starts=quarterly_plot_times,
                ylabel="% GDP (Current prices)",
                annotate=True,
                **(common | {"title": f"{title} as a % of GDP"}),
            )
            postcovid_plot_finalise(
                data=plotable, tag="covid-current-prices", annotate=[False, True], ylabel=units, **common
            )
            if "Household" in title:
                _excess_savings(plotable, common, units)


def saving_investment(release: AbsRelease) -> None:
    """Gross saving and investment as shares of GDP, with HP trends; the gap between the trends shaded."""
    gdp, _ = get_gdp("CP", "SA")
    gross_saving = _sa(release, NATIONAL_INCOME, "All sectors ;  Net saving ;") + _sa(
        release, NATIONAL_INCOME, "Consumption of fixed capital ;"
    )
    investment = _sa(release, EXPENDITURE_CP, "All sectors ;  Gross fixed capital formation ;")
    saving_pct = (gross_saving / gdp * PERCENT).dropna()
    invest_pct = (investment / gdp * PERCENT).dropna()
    saving_trend = pd.Series(hpfilter(saving_pct, lamb=HP_LAMBDA)[1], index=saving_pct.index)
    invest_trend = pd.Series(hpfilter(invest_pct, lamb=HP_LAMBDA)[1], index=invest_pct.index)

    lines = pd.DataFrame(
        {
            "Gross saving": saving_pct,
            "Gross saving (trend)": saving_trend,
            "Investment (GFCF)": invest_pct,
            "Investment (trend)": invest_trend,
        }
    ).dropna()
    trend = pd.DataFrame({"saving": saving_trend, "investment": invest_trend}).dropna()
    in_deficit = trend["saving"] < trend["investment"]
    surplus = trend[["investment", "saving"]].copy()
    surplus.loc[in_deficit, "saving"] = surplus.loc[in_deficit, "investment"]
    deficit = trend[["saving", "investment"]].copy()
    deficit.loc[~in_deficit, "investment"] = deficit.loc[~in_deficit, "saving"]

    with chart_subdir(SUBDIR):
        ax = line_plot(lines, color=["darkorange", "darkorange", "blue", "blue"], width=[0.7, 2.5, 0.7, 2.5])
        fill_between_plot(surplus, ax=ax, color="green", alpha=0.15, label="Current account surplus")
        fill_between_plot(deficit, ax=ax, color="red", alpha=0.15, label="Current account deficit")
        finalise_plot(
            ax,
            title="Saving and Investment as a share of GDP",
            ylabel="Per cent of GDP",
            legend={"loc": "best", "fontsize": "xx-small"},
            rfooter=release.source,
            lfooter=f"{AUSTRALIA}{SA_NOTE}{CP_NOTE}HP trend. Gross Saving = Investment + Current Account. "
            f"{data_to(lines)}",
            pre_tag="saving-",
        )


def current_account(release: AbsRelease) -> None:
    """Chart the current account split into private and government balances, by level, and into its parts."""
    gg_data, gg_meta = ra.read_abs_cat(GG_CATALOGUE, single_excel_only=GG_CAPITAL)

    def gg(did: str) -> pd.Series:
        _, gg_id, _ = ra.find_abs_id(gg_meta, {GG_CAPITAL: mc.table, SA: mc.stype, did: mc.did}, verbose=False)
        return gg_data[GG_CAPITAL][gg_id]

    current = -_sa(release, EXTERNAL, CA_DID)
    govt = _total([gg(did) for did in GG_SAVING_DIDS]) - _total([gg(did) for did in GG_INVESTMENT_DIDS])
    totals = pd.DataFrame(
        {"Current account": current, "Private (S - I)": current - govt, "Government (T - G)": govt}
    ).dropna()
    if totals.empty:
        raise ValueError("No overlapping current account and government data")

    levels = {
        label: _total([_sa(release, table, did) for did in GG_SAVING_DIDS])
        - _sa(release, EXPENDITURE_CP, gfcf_did)
        for label, (table, gfcf_did) in GG_LEVELS.items()
    }
    by_level = pd.DataFrame(
        {"Current account": totals["Current account"], "Private (S - I)": totals["Private (S - I)"], **levels}
    ).dropna()
    if by_level.empty:
        raise ValueError("No overlapping current account and government data by level")

    operating = pd.DataFrame(
        {
            "Operating balance": gg("Net saving ;") + gg(GG_CAPITAL_TRANSFERS_DID),
            "Net capital investment": _total([gg(did) for did in GG_NET_INVESTMENT_DIDS]) - gg(GG_CFC_DID),
            "Net lending (+) / borrowing (-)": gg(GG_NET_LENDING_DID),
        }
    ).dropna()
    if operating.empty:
        raise ValueError("No general government operating balance data")

    parts = {"Current account": current}
    for label, (added, subtracted) in CA_PARTS.items():
        parts[label] = _total([_sa(release, EXTERNAL, did) for did in added]) - _total(
            [_sa(release, EXTERNAL, did) for did in subtracted]
        )
    external = pd.DataFrame(parts).dropna()
    if external.empty:
        raise ValueError("No current account components")

    with chart_subdir(SUBDIR):
        both = f"{release.source}, {GG_CATALOGUE}"
        _balance_shares(
            totals,
            title="Current account = (S - I) + (T - G)",
            rfooter=both,
            lfooter=f"{AUSTRALIA}{SA_SHORT}{CP_NOTE}G = general government (all levels). "
            "S - I = CA - (T - G). Excl. capital account. ",
        )
        _balance_shares(
            by_level,
            title="Current account with (T - G) by level of govt",
            rfooter=both,
            lheader="Cwlth and State after Cwlth-to-State current grants.",
            lfooter=f"{AUSTRALIA}{SA_NOTE}{CP_NOTE}G split by level of government. "
            "S - I = CA - (T - G). Excl. capital account. ",
        )
        _balance_shares(
            operating,
            title="Govt operating balance vs net capital investment",
            rfooter=both,
            lheader="Net lending = operating balance - net capital investment.",
            lfooter=f"{AUSTRALIA}{SA_SHORT}{CP_NOTE}General government, all levels. "
            "National accounts equivalents of GFS measures. ",
        )
        _balance_shares(
            external,
            title="CA = (X - M) + primary + secondary income",
            rfooter=release.source,
            lfooter=f"{AUSTRALIA}{SA_NOTE}{CP_NOTE}Income terms are net. "
            "Primary income is mostly interest, dividends and profits. ",
        )


# --- table of contents, in run order
CHARTS = (
    (savings, ()),
    (saving_investment, ()),
    (current_account, ()),
)
