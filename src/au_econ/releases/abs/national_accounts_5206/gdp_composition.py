"""National Accounts GDP composition: contributions to growth on the expenditure, production and income sides."""

# --- dependencies
from functools import reduce
from operator import add
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import mgplot as mg
import pandas as pd
import readabs as ra
from mgplot import bar_plot_finalise, chart_subdir, multi_start, series_growth_plot_finalise
from readabs import metacol as mc

from au_econ.charting.windows import quarterly_plot_times
from au_econ.releases.abs.national_accounts_5206.common import (
    ANALYTICAL,
    AUSTRALIA,
    CP_NOTE,
    CVM_NOTE,
    EXPENDITURE_VOLUME,
    INCOME_FROM_GDP,
    INDUSTRY_GVA,
    QUARTERS_PER_YEAR,
    SA_NOTE,
    SEASONALLY_ADJUSTED,
    data_to,
)
from au_econ.series.gdp import get_gdp

if TYPE_CHECKING:
    from matplotlib.axes import Axes

    from au_econ.sources.abs import AbsRelease

# --- constants
SUBDIR = "GDP-composition"
SA = SEASONALLY_ADJUSTED
PERCENT = 100
INVENTORIES_TABLE = "5206009_Changes_In_Inventories"
CONTRIBUTIONS_FROM = "2022Q2"  # recent history for the stacked contribution charts
FIGSIZE = (9, 5.5)
AVERAGE_YEARS = 30
PRE_COVID = (pd.Period("2000Q1", "Q-DEC"), pd.Period("2019Q4", "Q-DEC"))
CVM_SA = f"{AUSTRALIA}{SA_NOTE}{CVM_NOTE}"
CP_SA = f"{AUSTRALIA}{SA_NOTE}{CP_NOTE}"
ROUNDED = "Components rounded to 0.1 ppt. "
SOURCE = "ABS: 5206.0"

# expenditure side: published contributions to growth (5206002)
EXPENDITURE_STACK = (
    ("Household consumption", "skyblue"),
    ("Government consumption", "lightgreen"),
    ("Private investment", "lightcoral"),
    ("Public investment", "firebrick"),
    ("Inventories", "orchid"),
    ("Net exports", "gold"),
    ("Statistical discrepancy", "silver"),
)
TO_GROWTH = "Contributions to growth ;"

# private demand: component levels (5206002) and their totals
PFD_COMPONENTS = {
    "Household consumption": "Households ;  Final consumption expenditure ;",
    "Dwellings": "Private ;  Gross fixed capital formation - Dwellings - Total ;",
    "Ownership transfer costs": "Private ;  Gross fixed capital formation - Ownership transfer costs ;",
    "Non-dwelling construction": "Private ;  Gross fixed capital formation - Non-dwelling construction - Total ;",
    "Machinery and equipment": "Private ;  Gross fixed capital formation - Machinery and equipment - Total ;",
    "Intellectual property products": (
        "Private ;  Gross fixed capital formation - Intellectual property products ;"
    ),
    "Cultivated biological resources": (
        "Private ;  Gross fixed capital formation - Cultivated biological resources ;"
    ),
}
HOUSEHOLD_COMPONENTS = ("Household consumption", "Dwellings", "Ownership transfer costs")
BUSINESS_COMPONENTS = (
    "Non-dwelling construction",
    "Machinery and equipment",
    "Intellectual property products",
    "Cultivated biological resources",
)
PFD_DID = "Private ;  Final demand: Chain volume measures ;"
BUSINESS_DID = "Private ;  Gross fixed capital formation - Total private business investment ;"

# inventories
INVENTORIES_FROM = "2013Q4"  # about twelve years of contribution history
INVENTORIES_QUARTERS = 16  # quarters shown in the industry decomposition
INVENTORY_INDUSTRIES = (
    ("Farm", "Farm ;  Chain volume measures ;", "yellowgreen"),
    ("Mining", "Private ;  Mining (B) ;  Chain volume measures ;", "sienna"),
    ("Manufacturing", "Private ;  Manufacturing (C) ;  Chain volume measures ;", "steelblue"),
    ("Wholesale", "Private ;  Wholesale trade (F) ;  Chain volume measures ;", "mediumpurple"),
    ("Retail", "Private ;  Retail trade (G) ;  Chain volume measures ;", "salmon"),
    ("Other non-farm", "Private ;  Non-farm ;  Other non-farm industries: Chain volume measures ;", "silver"),
    ("Public", "Public authorities ;  Chain volume measures ;", "teal"),
)

# production side: industry contributions (5206006) summed into sectors
PRODUCTION_STACK = (
    ("Market sector", "steelblue"),
    ("Non-market sector", "lightgreen"),
    ("Ownership of dwellings", "tan"),
    ("Taxes less subsidies", "gold"),
    ("Statistical discrepancy (P)", "silver"),
)
MARKET_INDUSTRIES = (  # the ABS market sector: 16 ANZSIC divisions
    "Agriculture, forestry and fishing (A)",
    "Mining (B)",
    "Manufacturing (C)",
    "Electricity, gas, water and waste services (D)",
    "Construction (E)",
    "Wholesale trade (F)",
    "Retail trade (G)",
    "Accommodation and food services (H)",
    "Transport, postal and warehousing (I)",
    "Information media and telecommunications (J)",
    "Financial and insurance services (K)",
    "Rental, hiring and real estate services (L)",
    "Professional, scientific and technical services (M)",
    "Administrative and support services (N)",
    "Arts and recreation services (R)",
    "Other services (S)",
)
NON_MARKET_INDUSTRIES = (
    "Public administration and safety (O)",
    "Education and training (P)",
    "Health care and social assistance (Q)",
)

# income side (5206007, current prices)
INCOME_SHARES = (  # (label, ABS data item description, colour)
    ("Compensation of employees", "Compensation of employees ;", "cornflowerblue"),
    ("Corporate GOS (profits)", "Total corporations ;  Gross operating surplus ;", "indianred"),
    ("Dwellings GOS", "Dwellings owned by persons ;  Gross operating surplus ;", "tan"),
    ("General govt GOS", "General government ;  Gross operating surplus ;", "mediumseagreen"),
    ("Gross mixed income", "Gross mixed income ;", "mediumpurple"),
    ("Taxes less subsidies", "Taxes less subsidies on production and imports ;", "gold"),
)
INCOME_CONTRIBUTIONS = (*INCOME_SHARES, ("Statistical discrepancy", "Statistical discrepancy (I) ;", "silver"))
CORPORATE_GOS_SECTORS = (  # sums to total corporate GOS
    ("Private non-financial", "Private non-financial corporations ;  Gross operating surplus ;", "indianred"),
    ("Public non-financial", "Public non-financial corporations ;  Gross operating surplus ;", "tan"),
    ("Financial corporations", "Financial corporations ;  Gross operating surplus ;", "cornflowerblue"),
)
COE_COMPONENTS = (  # sums to total compensation of employees
    ("Wages and salaries", "Compensation of employees - Wages and salaries ;", "cornflowerblue"),
    (
        "Employers' social contributions",
        "Compensation of employees - Employers' social contributions ;",
        "tan",
    ),
)


# --- helpers
def _series(release: AbsRelease, table: str, did: str) -> pd.Series:
    """Return one seasonally adjusted series from a table by exact description, on a Q-DEC index."""
    meta = release.meta
    row = meta[(meta[mc.table] == table) & (meta[mc.did] == did) & (meta[mc.stype] == SA)].iloc[0]
    series = release.data[table][row[mc.id]].dropna()
    series.index = pd.PeriodIndex(series.index, freq="Q-DEC")
    return series


def _gdp_growth() -> pd.Series:
    """Return published quarterly GDP growth: the per cent change in chain volume GDP."""
    level, _units = get_gdp("CVM", "SA")
    growth = (level / level.shift(1) - 1) * PERCENT
    growth.index = pd.PeriodIndex(growth.index, freq="Q-DEC")
    growth.name = "GDP growth"
    return growth


def _expenditure(release: AbsRelease) -> tuple[pd.DataFrame, pd.Series, pd.Period]:
    """Return the published expenditure contributions, GDP growth, and the latest quarter."""

    def contribution(did: str) -> pd.Series:
        return _series(release, EXPENDITURE_VOLUME, f"{did}: {TO_GROWTH}")

    comp = pd.DataFrame(
        {
            "Household consumption": contribution("Households ;  Final consumption expenditure"),
            "Government consumption": contribution("General government ;  Final consumption expenditure"),
            "Private investment": contribution("Private ;  Gross fixed capital formation"),
            "Public investment": contribution("Public ;  Gross fixed capital formation"),
            "Inventories": contribution("Changes in inventories"),
            "Net exports": contribution("Exports of goods and services")
            + contribution("Imports of goods and services"),
            "Statistical discrepancy": contribution("Statistical discrepancy (E)"),
        }
    ).dropna()
    return comp, _gdp_growth().reindex(comp.index), comp.index[-1]


def _production(release: AbsRelease) -> tuple[pd.DataFrame, pd.Series, pd.Period]:
    """Return the production-side sector contributions, GDP growth, and the latest quarter.

    The statistical discrepancy (P) is published as a level only, so it is the residual.
    """

    def sector(industries: tuple[str, ...]) -> pd.Series:
        return reduce(add, (_series(release, INDUSTRY_GVA, f"{ind} ;  {TO_GROWTH}") for ind in industries))

    comp = pd.DataFrame(
        {
            "Market sector": sector(MARKET_INDUSTRIES),
            "Non-market sector": sector(NON_MARKET_INDUSTRIES),
            "Ownership of dwellings": _series(release, INDUSTRY_GVA, f"Ownership of dwellings ;  {TO_GROWTH}"),
            "Taxes less subsidies": _series(
                release, INDUSTRY_GVA, f"Taxes less subsidies on products: {TO_GROWTH}"
            ),
        }
    ).dropna()
    gdp = _gdp_growth().reindex(comp.index)
    comp["Statistical discrepancy (P)"] = gdp - comp.sum(axis=1)
    return comp, gdp, comp.index[-1]


def _split_label(label: str) -> str:
    """Break a label onto two lines at the space nearest its middle (for y ticks)."""
    spaces = [i for i, ch in enumerate(label) if ch == " "]
    if not spaces:
        return label
    i = min(spaces, key=lambda j: abs(j - len(label) / 2))
    return f"{label[:i]}\n{label[i + 1 :]}"


def _stacked_with_dots(comp: pd.DataFrame, dots: pd.Series, colours: list[str] | None = None) -> Axes:
    """Draw stacked contribution bars with the total as black dots."""
    ax = mg.bar_plot(comp, stacked=True) if colours is None else mg.bar_plot(comp, stacked=True, color=colours)
    mg.line_plot(dots, ax=ax, width=0, marker="o", markersize=5, color="black", annotate=False)
    return ax


def _distributions(comp: pd.DataFrame, latest: pd.Period, stack: tuple[tuple[str, str], ...], name: str) -> None:
    """Draw a boxplot of each component over the averaging window, with the latest quarter as a diamond."""
    window = comp.tail(AVERAGE_YEARS * QUARTERS_PER_YEAR)
    now = comp.iloc[-1]  # the latest quarter
    names = [n for n, _ in stack]
    colours = dict(stack)
    ypos = list(range(len(names) - 1, -1, -1))  # first component on top

    _fig, ax = plt.subplots(figsize=FIGSIZE)
    bp = ax.boxplot(
        [window[n].to_numpy() for n in names],
        positions=ypos,
        orientation="horizontal",
        widths=0.6,
        patch_artist=True,
        showfliers=False,
        zorder=2,
    )
    for patch, n in zip(bp["boxes"], names, strict=True):
        patch.set_facecolor(colours[n])
        patch.set_alpha(0.75)
    for median in bp["medians"]:
        median.set_color("black")
    for y, n in zip(ypos, names, strict=True):
        ax.plot(
            now[n],
            y,
            marker="D",
            color="black",
            markeredgecolor="white",
            markersize=8,
            linestyle="none",
            zorder=4,
            label=f"Latest {latest}" if y == ypos[0] else None,
        )
    ax.set_yticks(ypos)
    ax.set_yticklabels([_split_label(n) for n in names])
    mg.finalise_plot(
        ax,
        title=f"{name} Input Distribution Boxplots vs Latest {latest}",
        xlabel="Percentage points (q/q)",
        axvline={"x": 0, "color": "black", "linewidth": 0.6},
        legend={"loc": "best", "fontsize": 8},
        rfooter=SOURCE,
        lfooter=f"{CVM_SA}Diamond = latest quarter. {ROUNDED}",
    )


def _benchmarks(
    bars: list[tuple[str, pd.Series, float]],
    latest: pd.Period,
    stack: tuple[tuple[str, str], ...],
    name: str,
    ncol: int,
) -> None:
    """Draw horizontal stacked bars for the benchmarks and the latest quarter, each with a GDP growth dot."""
    _fig, ax = plt.subplots(figsize=FIGSIZE)
    ypos = list(range(len(bars) - 1, -1, -1))  # first bar on top
    top = ypos[0]
    data_min = data_max = 0.0
    for y, (_label, comps, gdp_dot) in zip(ypos, bars, strict=True):
        pos = neg = 0.0
        for component, colour in stack:
            v = comps[component]
            left = pos if v >= 0 else neg
            ax.barh(y, v, height=0.6, left=left, color=colour, zorder=2, label=component if y == top else None)
            pos, neg = (pos + v, neg) if v >= 0 else (pos, neg + v)
        data_min, data_max = min(data_min, neg), max(data_max, pos)
        ax.plot(gdp_dot, y, "o", color="black", markersize=6, zorder=3, label="GDP growth" if y == top else None)
    ax.set_yticks(ypos)
    ax.set_yticklabels([_split_label(label) for label, _, _ in bars])
    pad = 0.01 * (data_max - data_min)  # 1% breathing room at each end
    mg.finalise_plot(
        ax,
        title=f"{name} Contributions: Benchmarks vs Latest {latest}",
        xlabel="Percentage points (q/q)",
        ylim=(-0.5, top + 1.1),  # a band above the top bar for the legend
        xlim=(data_min - pad, data_max + pad),
        axvline={"x": 0, "color": "black", "linewidth": 0.6},
        legend={"loc": "upper center", "ncol": ncol, "fontsize": 8},
        rfooter=SOURCE,
        lfooter=f"{CVM_SA}Dot = GDP growth. {ROUNDED}",
    )


def _average_label() -> str:
    """Return the label for the long-run average bar."""
    return f"{AVERAGE_YEARS}-year average"


def _pre_covid_label() -> str:
    """Return the label for the pre-COVID average bar."""
    return f"{PRE_COVID[0].year}-{PRE_COVID[1].year} average"


def _level(release: AbsRelease, table: str, did: str) -> pd.Series:
    """Return a seasonally adjusted chain volume level, by description, or raise if it is empty."""
    _, series_id, _ = ra.find_abs_id(release.meta, {table: mc.table, SA: mc.stype, did: mc.did})
    series = release.data[table][series_id].dropna()
    if series.empty:
        raise ValueError(f"No data for {did}")
    return series


def _household_demand(release: AbsRelease) -> pd.Series:
    """Return household demand: consumption, dwellings and ownership transfer costs (the ABS publishes none)."""
    levels = pd.DataFrame(
        {name: _level(release, EXPENDITURE_VOLUME, PFD_COMPONENTS[name]) for name in HOUSEHOLD_COMPONENTS}
    )
    return levels.sum(axis=1, min_count=len(HOUSEHOLD_COMPONENTS)).dropna()


def _income_contributions(
    release: AbsRelease, items: tuple[tuple[str, str, str], ...], total_did: str
) -> tuple[pd.DataFrame, pd.Series]:
    """Return each item's q/q change as a per cent of last quarter's total, and the total's level."""
    levels = pd.DataFrame({lab: _series(release, INCOME_FROM_GDP, did) for lab, did, _ in items}).dropna()
    total = _series(release, INCOME_FROM_GDP, total_did).reindex(levels.index)
    comp = (levels.diff().div(total.shift(1), axis=0) * PERCENT).dropna().loc[CONTRIBUTIONS_FROM:]
    return comp, total


# --- charts
def expenditure_contributions(release: AbsRelease) -> None:
    """Stacked published expenditure contributions to quarterly GDP growth, with GDP growth as dots."""
    comp, _gdp, _latest = _expenditure(release)
    comp = comp.loc[CONTRIBUTIONS_FROM:]
    with chart_subdir(SUBDIR):
        ax = _stacked_with_dots(comp, _gdp_growth().reindex(comp.index), [c for _, c in EXPENDITURE_STACK])
        mg.finalise_plot(
            ax,
            title="Contributions to Quarterly GDP Growth: Expenditure",
            ylabel="Percentage points (q/q)",
            y0=True,
            legend={"loc": "best", "fontsize": 8, "ncol": 4},
            rfooter=SOURCE,
            lfooter=f"{CVM_SA}Dots = GDP growth. {ROUNDED}{data_to(comp)}",
        )


def demand_contributions(release: AbsRelease) -> None:
    """Contributions to growth in private final demand, business investment and household demand; their growth."""
    business = _level(release, EXPENDITURE_VOLUME, BUSINESS_DID)
    household = _household_demand(release)
    with chart_subdir(SUBDIR):
        for names, total, label in (
            (tuple(PFD_COMPONENTS), _level(release, ANALYTICAL, PFD_DID), "Private Final Demand"),
            (BUSINESS_COMPONENTS, business, "Private Business Investment"),
            (HOUSEHOLD_COMPONENTS, household, "Household Demand"),
        ):
            levels = pd.DataFrame({n: _level(release, EXPENDITURE_VOLUME, PFD_COMPONENTS[n]) for n in names})
            contributions = (levels.diff().div(total.shift(1), axis=0) * PERCENT).dropna().loc[CONTRIBUTIONS_FROM:]
            growth = (total / total.shift(1) - 1) * PERCENT
            growth.name = f"{label.capitalize()} growth"
            ax = _stacked_with_dots(contributions, growth.reindex(contributions.index))
            mg.finalise_plot(
                ax,
                title=f"Contributions to Quarterly {label} Growth",
                ylabel="Percentage points (q/q)",
                y0=True,
                legend={"loc": "best", "fontsize": 8, "ncol": 3},
                rfooter=release.source,
                lfooter=f"{CVM_SA}Contributions calculated from component levels. {data_to(contributions)}",
            )

        for level, label, note in (
            (business, "Private Business Investment", ""),
            (
                household,
                "Household Demand",
                "Household demand = consumption + dwellings + transfer costs. ",
            ),
        ):
            multi_start(
                level,
                function=series_growth_plot_finalise,
                starts=quarterly_plot_times,
                title=f"{label}: Growth",
                annotate_line=True,
                y0=True,
                rfooter=release.source,
                lfooter=f"{CVM_SA}{note}{data_to(level)}",
            )


def gdpe_distributions(release: AbsRelease) -> None:
    """Chart the latest quarter's expenditure contributions against their 30-year distribution and averages."""
    comp, gdp, latest = _expenditure(release)
    pre = (comp.index >= PRE_COVID[0]) & (comp.index <= PRE_COVID[1])
    window = AVERAGE_YEARS * QUARTERS_PER_YEAR
    bars = [
        (_average_label(), comp.tail(window).mean(), gdp.tail(window).mean()),
        (_pre_covid_label(), comp[pre].mean(), gdp[pre].mean()),
        (f"Latest {latest}", comp.iloc[-1], gdp.iloc[-1]),
    ]
    with chart_subdir(SUBDIR):
        _distributions(comp, latest, EXPENDITURE_STACK, "GDP(E)")
        _benchmarks(bars, latest, EXPENDITURE_STACK, "GDP(E)", ncol=4)


def gdpe_component_bars(release: AbsRelease) -> None:
    """Each expenditure component's quarterly contribution to GDP growth, in its stack colour."""
    comp, _gdp, _latest = _expenditure(release)
    comp = comp.loc[CONTRIBUTIONS_FROM:]
    with chart_subdir(SUBDIR):
        for name, colour in EXPENDITURE_STACK:
            bar_plot_finalise(
                comp[name].rename("Contribution"),
                color=[colour],
                title=f"{name}: Contribution to GDP(E) Growth",
                ylabel="Percentage points (q/q)",
                annotate=True,
                y0=True,
                pre_tag="gdpe-component-",
                rfooter=SOURCE,
                lfooter=f"{CVM_SA}{data_to(comp)}",
            )


def inventories(release: AbsRelease) -> None:
    """Chart the inventories contribution with its four-quarter sum, and the change in inventories by industry."""
    contrib = _series(release, EXPENDITURE_VOLUME, f"Changes in inventories: {TO_GROWTH}").loc[INVENTORIES_FROM:]
    roll = contrib.rolling(QUARTERS_PER_YEAR).sum()
    roll.name = "Rolling 4-quarter sum"
    comp = pd.DataFrame({name: _series(release, INVENTORIES_TABLE, did) for name, did, _ in INVENTORY_INDUSTRIES})
    comp = comp.dropna().tail(INVENTORIES_QUARTERS)
    total_did = "CHANGES IN INVENTORIES: Chain volume measures ;"
    total = _series(release, INVENTORIES_TABLE, total_did).reindex(comp.index)
    total.name = "Total change"

    with chart_subdir(SUBDIR):
        ax = mg.bar_plot(contrib, color="orchid", label_series=False)
        mg.line_plot(roll, ax=ax, color="indigo", marker=None, annotate=False)
        mg.finalise_plot(
            ax,
            title="Inventories: Contribution to Quarterly GDP Growth",
            ylabel="Percentage points (q/q)",
            y0=True,
            legend={"loc": "best", "fontsize": 8},
            rfooter=SOURCE,
            lfooter=f"{CVM_SA}Bars = inventories contribution; line = trailing 4-quarter sum. {data_to(contrib)}",
        )

        ax = _stacked_with_dots(comp, total, [col for _, _, col in INVENTORY_INDUSTRIES])
        mg.finalise_plot(
            ax,
            title="Change in Inventories by Industry",
            ylabel="$ million (CVM, q/q change)",
            y0=True,
            legend={"loc": "best", "fontsize": 7, "ncol": 4},
            rfooter=SOURCE,
            lfooter=f"{CVM_SA}Stack = change in inventories by industry; dots = total. {data_to(comp)}",
        )


def production_contributions(release: AbsRelease) -> None:
    """Production-side contributions to GDP growth: recent stack, 30-year distribution and averages."""
    comp, gdp, latest = _production(release)
    pre = (comp.index >= PRE_COVID[0]) & (comp.index <= PRE_COVID[1])
    window = AVERAGE_YEARS * QUARTERS_PER_YEAR
    bars = [
        (_average_label(), comp.tail(window).mean(), comp.tail(window).mean().sum()),
        (_pre_covid_label(), comp[pre].mean(), comp[pre].mean().sum()),
        (f"Latest {latest}", comp.iloc[-1], comp.iloc[-1].sum()),
    ]
    recent = comp.loc[CONTRIBUTIONS_FROM:]
    with chart_subdir(SUBDIR):
        ax = _stacked_with_dots(recent, gdp.loc[CONTRIBUTIONS_FROM:], [c for _, c in PRODUCTION_STACK])
        mg.finalise_plot(
            ax,
            title="Contributions to Quarterly GDP Growth: Production",
            ylabel="Percentage points (q/q)",
            y0=True,
            legend={"loc": "best", "fontsize": 8, "ncol": 3},
            rfooter=SOURCE,
            lfooter=f"{CVM_SA}Dots = GDP growth. {ROUNDED}{data_to(recent)}",
        )
        _distributions(comp, latest, PRODUCTION_STACK, "GDP(P)")
        _benchmarks(bars, latest, PRODUCTION_STACK, "GDP(P)", ncol=3)


def income_shares(release: AbsRelease) -> None:
    """Income-side composition of nominal GDP, and decompositions of nominal, corporate GOS and COE growth."""
    comp = pd.DataFrame({lab: _series(release, INCOME_FROM_GDP, did) for lab, did, _ in INCOME_SHARES}).dropna()
    share = comp.div(comp.sum(axis=1), axis=0) * PERCENT  # each row sums to 100%
    with chart_subdir(SUBDIR):
        multi_start(
            share,
            function=bar_plot_finalise,
            starts=quarterly_plot_times,
            title="GDP(I) Income Shares",
            stacked=True,
            color=[col for _, _, col in INCOME_SHARES],
            width=1.0,
            annotate=False,
            ylabel="Per cent of GDP(I)",
            ylim=(0.0, 100.0),
            legend={"loc": "lower center", "ncol": 3, "fontsize": 7},
            rfooter=SOURCE,
            lfooter=f"{CP_SA}Excl. statistical discrepancy (<1%). {data_to(share)}",
        )

        contributions, ngdp = _income_contributions(release, INCOME_CONTRIBUTIONS, "GROSS DOMESTIC PRODUCT ;")
        growth = ((ngdp / ngdp.shift(1) - 1) * PERCENT).reindex(contributions.index)
        growth.name = "Nominal GDP growth"
        ax = _stacked_with_dots(contributions, growth, [col for _, _, col in INCOME_CONTRIBUTIONS])
        mg.finalise_plot(
            ax,
            title="Contributions to Quarterly nGDP Growth: Income",
            ylabel="Percentage points (q/q)",
            y0=True,
            legend={"loc": "best", "fontsize": 8, "ncol": 4},
            rfooter=SOURCE,
            lfooter=f"{CP_SA}Dots = nominal GDP growth. GOS = Gross Operating Surplus. {data_to(contributions)}",
        )

        for items, total_did, name, title, what in (
            (
                CORPORATE_GOS_SECTORS,
                "Total corporations ;  Gross operating surplus ;",
                "Total corporate GOS",
                "Corporate Gross Operating Surplus Growth by Sector",
                "Bars = each sector's contribution to total growth (dots). ",
            ),
            (
                COE_COMPONENTS,
                "Compensation of employees ;",
                "Total compensation of employees",
                "Compensation of Employees Growth by Component",
                "Bars = each component's contribution to total growth (dots). ",
            ),
        ):
            contributions, total = _income_contributions(release, items, total_did)
            growth = (total.pct_change() * PERCENT).reindex(contributions.index)
            growth.name = name
            ax = _stacked_with_dots(contributions, growth, [col for _, _, col in items])
            mg.finalise_plot(
                ax,
                title=title,
                ylabel="Per cent (q/q)",
                y0=True,
                legend={"loc": "best", "fontsize": 8, "ncol": 2},
                rfooter=SOURCE,
                lfooter=f"{CP_SA}{what}{data_to(contributions)}",
            )


# --- table of contents, in run order
CHARTS = (
    (expenditure_contributions, ()),
    (demand_contributions, ()),
    (gdpe_distributions, ()),
    (gdpe_component_bars, ()),
    (inventories, ()),
    (production_contributions, ()),
    (income_shares, ()),
)
