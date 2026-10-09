"""Government debt across OECD members: general government gross and net financial liabilities, per cent of GDP.

Both measures are the OECD Economic Outlook's, for general government: every level of
government, consolidated. Gross debt is all financial liabilities. Net debt is those
liabilities less all financial assets, so equities and pension fund holdings count against
the debt. Net debt is broader than national net debt measures, which net off only debt
instruments, and the gap is large where governments hold big funds (Norway, Japan,
Canada, Australia's Future Fund). The Economic Outlook projects the current year and the
next; those years are shaded.
"""

# --- dependencies
import time
from dataclasses import dataclass

import pandas as pd
from mgplot import bar_plot_finalise

from au_econ.charting.international import AUSTRALIA, country_group_charts
from au_econ.sources import oecd

# --- module contract
RELEASE = ("oecd-debt",)
TOPICS = ("international", "government")
TITLE = "Government Debt"

# --- constants
DATAFLOW = "OECD.ECO.MAD,DSD_EO@DF_EO,"  # unversioned: the latest Economic Outlook
MEASURES = {  # measure name: (key for every area, annual, as a per cent of GDP; footer definition)
    "Gross": (".GGFLQ.A", "Gross debt: total financial liabilities. "),
    "Net": (".GNFLQ.A", "Net debt: financial liabilities less financial assets. "),
}
SECTOR_NOTE = "General government (national + state + local). "
START = "1990"
WEB_DELAY = 2  # seconds between requests, to be gentle on the OECD server
OECD_AGGREGATE = "OECD"  # area code of the OECD-wide aggregate
OECD_LABEL = "OECD aggregate"
SOURCE = "OECD: Economic Outlook"
COUNTRY_COLOR, AUSTRALIA_COLOR, OECD_COLOR = "blue", "darkorange", "darkred"  # as in world_context_axes
PROJECTION_SPAN = {"color": "goldenrod", "alpha": 0.15, "zorder": 0}
RANKING_FIGSIZE = (9, 9)  # inches: double height, so some 35 country names do not touch


@dataclass(frozen=True)
class DebtMeasure:
    """One measure, annual (per cent of GDP): countries as columns, and the OECD aggregate."""

    countries: pd.DataFrame
    oecd_aggregate: pd.Series


@dataclass(frozen=True)
class GovernmentDebt:
    """Every measure in MEASURES, by name, and the first year the Economic Outlook projects."""

    measures: dict[str, DebtMeasure]
    first_projection: pd.Period  # the Economic Outlook projects this year and later


# --- data
def _measure(name: str, key: str) -> DebtMeasure:
    """Fetch one measure for every area; split off the OECD aggregate."""
    table = oecd.get_table(DATAFLOW, key, START)
    table.index = pd.PeriodIndex(table.index.astype(str), freq="Y")
    if OECD_AGGREGATE not in table.columns:
        raise ValueError(f"OECD {DATAFLOW} {key}: no {OECD_AGGREGATE} aggregate")
    aggregate = table[OECD_AGGREGATE].dropna().rename(OECD_LABEL)
    countries = oecd.national_only(table)
    oecd.report_missing(countries)
    print(f"{name} debt: {countries.index[0]} to {countries.index[-1]}, {len(countries.columns)} countries")
    return DebtMeasure(countries=countries.rename(columns=oecd.LABELS), oecd_aggregate=aggregate)


def fetch() -> GovernmentDebt:
    """Fetch every measure in MEASURES."""
    measures: dict[str, DebtMeasure] = {}
    for name, (key, _note) in MEASURES.items():
        if measures:
            time.sleep(WEB_DELAY)
        measures[name] = _measure(name, key)
    first_projection = pd.Period.now(freq="Y")
    print(f"Projections from {first_projection}")
    return GovernmentDebt(measures=measures, first_projection=first_projection)


# --- charts
def debt_ranking(data: GovernmentDebt) -> None:
    """For each measure, every country in the last year before the projections, ranked, with the OECD aggregate."""
    year = data.first_projection - 1
    colors = {AUSTRALIA: AUSTRALIA_COLOR, OECD_LABEL: OECD_COLOR}
    for name, measure in data.measures.items():
        rows = measure.countries[measure.countries.index == year]
        aggregate = measure.oecd_aggregate[measure.oecd_aggregate.index == year]
        if rows.empty or aggregate.empty:
            raise ValueError(f"No {name.lower()} debt data for {year}")
        latest = rows.iloc[0]
        missing = sorted(latest[latest.isna()].index)
        ranked = pd.concat([latest.dropna(), aggregate.set_axis([OECD_LABEL])]).sort_values()
        no_data = f"No {year} data: {', '.join(missing)}. " if missing else ""
        bar_plot_finalise(
            ranked,
            horizontal=True,
            color=[colors.get(label, COUNTRY_COLOR) for label in ranked.index],
            figsize=RANKING_FIGSIZE,
            title=f"Government {name} Debt, {year}",
            xlabel="Per cent of GDP",
            lfooter=f"{SECTOR_NOTE}{MEASURES[name][1]}{no_data}",
            rfooter=SOURCE,
        )


def debt_groups(data: GovernmentDebt) -> None:
    """For each measure, a chart per country group, with the projection years shaded."""
    for name, measure in data.measures.items():
        last = measure.countries.index[-1]
        projecting = last >= data.first_projection
        country_group_charts(
            measure.countries,
            title=f"Government {name} Debt",
            ylabel="Per cent of GDP",
            legend=True,  # even for a group with one country
            rfooter=SOURCE,
            lfooter=f"{SECTOR_NOTE}{MEASURES[name][1]}{'Shaded: OECD projections. ' if projecting else ''}",
            axvspan={**PROJECTION_SPAN, "xmin": data.first_projection, "xmax": last} if projecting else None,
        )


# --- table of contents, in run order
CHARTS = (
    (debt_ranking, ()),
    (debt_groups, ()),
)
