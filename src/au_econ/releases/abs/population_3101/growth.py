"""Population growth and migration: three population estimates, the components of growth, NOM and its proxies."""

# --- dependencies
from typing import Any

import pandas as pd
import readabs as ra
from mgplot import line_plot_finalise, multi_start
from mgplot.utilities import get_color_list

from au_econ.analysis.henderson import hma
from au_econ.charting.windows import quarterly_plot_times
from au_econ.releases.abs.population_3101.common import (
    ERP_GROWTH,
    HMA_TERMS,
    MONTHS_PER_YEAR,
    PERCENT,
    RECENT_MONTHS,
    SCALE_WORDS,
    SOURCE_3101,
    SOURCE_3101_3401,
    SOURCE_3101_6202,
    SOURCE_POP,
    THOUSAND,
    PopulationData,
    recalibrated,
)
from au_econ.series.nom import get_nom, get_nom_forward_proxy, get_population_growth_proxy
from au_econ.series.population import get_erp

# --- constants
RECENT = (0, -RECENT_MONTHS)
MIGRATION_LFOOTER = (
    "Australia. Original series. NOM: 4Q rolling sum. "
    "Net arrivals: arrivals less departures, 12m sum, 25-term HMA. "
)
SPLIT_LFOOTER = (
    "Australia. Original series. Rolling 4-quarter sums. Net migration = ERP growth less natural increase. "
)
COVID_START, COVID_END = pd.Period("2020-01", freq="M"), pd.Period("2023-02", freq="M")
LAST_CENSUS = pd.Period("2021-09", freq="M")
CENSUS_MONTHS = [pd.Period(f"{year}-09", freq="M") for year in (1991, 1996, 2001, 2006, 2011, 2016, 2021)]
NOM_LABEL = "Net Overseas Migration (4Q rolling sum)"
PROXY_LABEL = "Net Arrivals Proxy (12m net, 25-term HMA)"
NET_MIGRATION_LABEL = "Net Migration (ERP growth less natural increase)"


# --- helpers
def _official_and_proxy_colors() -> list[str]:
    """Return mgplot's first colour for the official series and its second for both proxy lines."""
    official, proxy = get_color_list(2)
    return [official, proxy, proxy]


def _nom_monthly() -> pd.Series:
    """Return official NOM ('000, 4-quarter rolling sum) on a monthly index."""
    nom, _units, _stype = get_nom()
    return ra.qtly_to_monthly(nom)


def _erp_monthly() -> pd.Series:
    """Return national ERP in thousands, without projection, on a monthly index."""
    erp, _ = get_erp()
    return ra.qtly_to_monthly(erp) / THOUSAND


def _smoothed_net_arrivals(data: PopulationData) -> pd.Series:
    return hma(data.growth["12 month rolling net total arrivals"].dropna(), HMA_TERMS)


def _growth_units(data: PopulationData) -> str:
    return SCALE_WORDS.get(data.erp_growth_units, data.erp_growth_units)


# --- charts
def population_estimates(data: PopulationData) -> None:
    """Chart three population estimates: ERP, civilian population aged 15+, National Accounts population."""
    keys = [
        "Estimated Resident Population",
        "LFS Civilian Population 15+",
        "Implicit population from National Accounts",
    ]
    frame, units = recalibrated(pd.DataFrame({key: data.growth[key] for key in keys}), "Thousands")
    multi_start(
        frame,
        function=line_plot_finalise,
        starts=RECENT,
        title="Population Estimates",
        ylabel=units,
        dropna=True,
        width=[2.5, 2, 1.5],
        style=["-", "--", "-."],
        lfooter="Australia. ",
        rfooter=SOURCE_POP,
        pre_tag="multi",
    )


def population_growth(data: PopulationData) -> None:
    """Chart annual population growth in persons from the three estimates, with the net migration proxy."""
    keys = [
        "Estimated Resident Population Annual Growth",
        "LFS Civilian Population 15+ Annual Growth",
        "Implicit population (from National Accounts) growth",
        "ERP Growth less Natural Increase",
    ]
    frame = pd.DataFrame({key: data.growth[key] for key in keys}).rename(
        columns={"ERP Growth less Natural Increase": "ERP Growth less Natural Increase (Net migration proxy)"}
    )
    frame, _ = recalibrated(frame, "Thousands")
    multi_start(
        frame,
        function=line_plot_finalise,
        title="Population Growth",
        starts=(0, frame.index[-RECENT_MONTHS]),
        ylabel="Thousands per year",
        dropna=True,
        width=[2.5, 2, 1.5, 1],
        style=["-", "--", ":", "-."],
        y0=True,
        annotate=True,
        lfooter="Australia. ERP = Estimated Resident Population. ",
        rfooter=SOURCE_POP,
        pre_tag="multi",
    )


def population_growth_rate(data: PopulationData) -> None:
    """Chart the annual population growth rate from the three estimates."""
    keys = [
        "Estimated Resident Population Annual Growth Rate",
        "LFS Civilian Population 15+ Annual Growth Rate",
        "Implicit population (from National Accounts) growth rate",
    ]
    multi_start(
        pd.DataFrame({key: data.growth[key] for key in keys}),
        function=line_plot_finalise,
        starts=RECENT,
        title="Population Growth Rate",
        ylabel="Annual percentage change",
        dropna=True,
        width=[2, 1.5, 1],
        style=["-", "--", "-", ":"],
        y0=True,
        lfooter="Australia. ",
        rfooter=SOURCE_POP,
        pre_tag="multi",
    )


def implied_migration(data: PopulationData) -> None:
    """Chart ERP growth less natural increase against 12-month net arrivals."""
    frame, units = recalibrated(
        pd.DataFrame(
            {
                "ERP Growth less Natural Increase": data.growth["ERP Growth less Natural Increase"],
                "12m Rolling Net Arrivals": data.growth["12 month rolling net total arrivals"],
            }
        ),
        "Thousands",
    )
    multi_start(
        frame,
        function=line_plot_finalise,
        starts=RECENT,
        title="Implied Net Migration: ERP Growth less Natural Increase",
        ylabel=f"{units} / year",
        dropna=True,
        width=[2, 1],
        y0=True,
        annotate=True,
        legend=True,
        lfooter="Australia. Original series. ERP = Estimated Resident Population. "
        "Natural increase: rolling 4-quarter sum. ",
        rfooter=SOURCE_3101_3401,
        pre_tag="multi",
    )


def growth_components(data: PopulationData) -> None:
    """Chart the components of ERP growth: births, deaths (negative), natural increase, net migration, total."""
    growth = data.growth
    frame, units = recalibrated(
        pd.DataFrame(
            {
                "Deaths (negative)": -growth["Annual Deaths"],
                "Births": growth["Annual Births"],
                "Natural Increase": growth["Annual Natural Increase"],
                NET_MIGRATION_LABEL: growth["ERP Growth less Natural Increase"],
                "ERP Annual Growth": growth[ERP_GROWTH],
            }
        ),
        "Thousands",
    )
    multi_start(
        frame,
        function=line_plot_finalise,
        starts=RECENT,
        title="Components of Population Growth",
        ylabel=f"{units} / year",
        dropna=True,
        width=[2, 2, 1, 2, 2],
        style=["-", "-", ":", "-", "--"],
        y0=True,
        annotate=True,
        legend=True,
        lfooter="Australia. Original series. Rolling 4-quarter sums. Natural increase = births - deaths. "
        "ERP = Estimated Resident Population. ",
        rfooter=SOURCE_3101,
        pre_tag="multi",
    )


def growth_split(data: PopulationData) -> None:
    """Chart ERP growth split into natural increase and net migration: in persons, and as rates.

    The rates are per cent of ERP a year earlier, so they sum to the published growth rate.
    """
    natural_increase = data.growth["Annual Natural Increase"]
    migration = data.growth["ERP Growth less Natural Increase"]
    year_earlier = data.growth["Estimated Resident Population"].shift(MONTHS_PER_YEAR)
    common: dict[str, Any] = {
        "dropna": True,
        "width": [2, 2],
        "y0": True,
        "annotate": True,
        "legend": True,
        "rfooter": SOURCE_3101,
        "pre_tag": "multi",
    }
    frame, units = recalibrated(
        pd.DataFrame({"Natural Increase": natural_increase, NET_MIGRATION_LABEL: migration}), "Thousands"
    )
    multi_start(
        frame,
        function=line_plot_finalise,
        starts=RECENT,
        title="Population Growth: Natural Increase vs Net Migration",
        ylabel=f"{units} / year",
        lfooter=f"{SPLIT_LFOOTER}ERP = Estimated Resident Population. ",
        **common,
    )
    multi_start(
        pd.DataFrame(
            {
                "Natural Increase": natural_increase / year_earlier * PERCENT,
                NET_MIGRATION_LABEL: migration / year_earlier * PERCENT,
            }
        ),
        function=line_plot_finalise,
        starts=RECENT,
        title="Population Growth Rate: Natural Increase vs Net Migration",
        ylabel="Per cent per year",
        lfooter=f"{SPLIT_LFOOTER}Rates relative to ERP a year earlier. ",
        **common,
    )


def migration_tty(data: PopulationData) -> None:
    """Chart through-the-year migrant population growth: NOM against smoothed net arrivals."""
    frame, units = recalibrated(
        pd.DataFrame({NOM_LABEL: _nom_monthly(), PROXY_LABEL: _smoothed_net_arrivals(data)}), "Thousands"
    )
    multi_start(
        frame,
        function=line_plot_finalise,
        starts=RECENT,
        title="Migrant Population Growth (TTY)",
        ylabel=f"{units} / year",
        dropna=True,
        width=[2, 1],
        style=["-", "--"],
        y0=True,
        annotate=True,
        legend=True,
        lfooter="Australia. Original series. NOM: 4-quarter rolling sum. "
        "Net arrivals=arrivals-departures, 12m sum, 25-term HMA. ",
        rfooter=SOURCE_3101_3401,
        pre_tag="multi",
    )


def migration_growth_rate(data: PopulationData) -> None:
    """Chart migrant population growth as a per cent of ERP: NOM and the net arrivals proxy."""
    erp = _erp_monthly()
    multi_start(
        pd.DataFrame(
            {
                NOM_LABEL: _nom_monthly() / erp * PERCENT,
                PROXY_LABEL: _smoothed_net_arrivals(data) / erp * PERCENT,
            }
        ),
        function=line_plot_finalise,
        starts=RECENT,
        title="Migrant Population Growth Rate (TTY)",
        ylabel="Per cent of ERP per year",
        dropna=True,
        width=[2, 1.5],
        style=["-", "--"],
        y0=True,
        annotate=True,
        legend=True,
        lfooter=MIGRATION_LFOOTER,
        rfooter=SOURCE_3101_3401,
        pre_tag="multi",
    )


def migration_share_of_growth(data: PopulationData) -> None:
    """Chart migration as a per cent of ERP growth, with the COVID years masked.

    ERP growth was tiny or negative through 2020-2022, so the ratio explodes there. The
    net arrivals share is smoothed separately either side of COVID, so the 25-term window
    does not carry COVID into the shoulders.
    """
    erp_growth = _erp_monthly().diff(MONTHS_PER_YEAR)
    raw_share = (data.growth["12 month rolling net total arrivals"].dropna() / erp_growth * PERCENT).dropna()
    pre, post = raw_share[raw_share.index < COVID_START], raw_share[raw_share.index > COVID_END]
    frame = pd.DataFrame(
        {
            NOM_LABEL: _nom_monthly() / erp_growth * PERCENT,
            "Net Arrivals Proxy (raw)": raw_share,
            "Net Arrivals Proxy (25-term HMA)": pd.concat([hma(pre, HMA_TERMS), hma(post, HMA_TERMS)]),
        }
    )
    frame.loc[(frame.index >= COVID_START) & (frame.index <= COVID_END)] = pd.NA
    multi_start(
        frame,
        function=line_plot_finalise,
        starts=RECENT,
        title="Migration as a Share of Population Growth",
        ylabel="Per cent of ERP annual growth",
        dropna=False,
        width=[1, 0.75, 2],
        style=["-", "-", "--"],
        color=_official_and_proxy_colors(),  # the smoothed proxy shares the raw proxy's colour
        alpha=[1.0, 0.4, 1.0],
        annotate=[True, False, True],
        y0=True,
        legend=True,
        axvspan={
            "xmin": COVID_START,
            "xmax": COVID_END,
            "color": "mistyrose",
            "alpha": 0.6,
            "label": "COVID (excluded)",
        },
        lfooter=MIGRATION_LFOOTER,
        rfooter=SOURCE_3101_3401,
        pre_tag="multi",
    )


def _forward_proxy_chart(
    official: pd.Series,
    proxy: pd.Series,
    last_official: pd.Period,
    last_complete: pd.Period,
    *,
    official_label: str,
    title: str,
    rheader: str,
    lfooter: str,
) -> None:
    """Chart a 6202-based forward proxy against its official series, full history and recent.

    The proxy is split at the last complete civ15 quarter, so the part-quarter estimate plots
    as its own dotted segment with its own end label.
    """
    frame = pd.DataFrame(
        {
            official_label: official,
            "6202 Forward Proxy": proxy.loc[:last_complete],
            "6202 Proxy: Part-quarter Estimate": proxy.loc[last_complete:],  # overlaps, so the tail joins
        }
    )
    multi_start(
        frame,
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        width=[2, 1.5, 1.5],
        style=["-", "--", ":"],
        color=_official_and_proxy_colors(),  # the estimate shares the proxy colour
        annotate=True,
        rounding=0,
        near_end=0.0,  # each label at its own line end, with a leader back to it
        leader_lines=True,
        dropna=True,
        title=title,
        ylabel="Persons per year ('000)",
        axvline={"x": last_official, "color": "grey", "linestyle": ":", "linewidth": 1},
        rheader=rheader,
        lfooter=lfooter,
        rfooter=SOURCE_3101_6202,
        pre_tag="multi",
    )


def nom_forward_proxy(_data: PopulationData) -> None:
    """Chart the 6202-based forward proxy for NOM against the official series."""
    proxy, nom, last_official, last_complete = get_nom_forward_proxy()
    _forward_proxy_chart(
        nom,
        proxy,
        last_official,
        last_complete,
        official_label="Official NOM (3101.0)",
        title="Net Overseas Migration: 6202 Forward Proxy",
        rheader="Proxy = civ15 growth - 15yo ageing-in + 15+ deaths + child migration",
        lfooter="Australia. Grey line marks last official NOM. "
        "Child migration held at its recent share of growth. Final quarter is an estimate. ",
    )


def population_growth_proxy(_data: PopulationData) -> None:
    """Chart the 6202-based forward proxy for annual ERP growth (the NOM proxy plus natural increase)."""
    proxy, official, last_official, last_complete = get_population_growth_proxy()
    _forward_proxy_chart(
        official,
        proxy,
        last_official,
        last_complete,
        official_label="Official ERP growth (3101.0)",
        title="Population Growth: 6202 Forward Proxy",
        rheader="Proxy = NOM forward proxy + natural increase",
        lfooter="Australia. Grey line marks last official ERP. "
        "Natural increase held at its latest value. Final quarter is an estimate. ",
    )


def nom_vs_erp_growth_less_ni(data: PopulationData) -> None:
    """Chart NOM against ERP growth less natural increase, over the full history."""
    frame = pd.DataFrame(
        {
            NOM_LABEL: _nom_monthly(),
            "ERP Growth less Natural Increase": data.growth["ERP Growth less Natural Increase"],
        }
    ).dropna(how="all")
    frame, units = recalibrated(frame, _growth_units(data))
    line_plot_finalise(
        frame,
        title="Net Overseas Migration vs ERP Growth less Natural Increase",
        ylabel=f"{units} of persons / year",
        dropna=True,
        width=[2.5, 1.5],
        style=["-", "--"],
        y0=True,
        annotate=True,
        legend=True,
        lfooter="Australia. Original series. NOM: 4-quarter rolling sum. ERP = Estimated Resident Population. ",
        rfooter=SOURCE_3101,
        pre_tag="multi",
    )


def erp_growth_less_ni_minus_nom(data: PopulationData) -> None:
    """Chart (ERP growth less natural increase) less NOM: the implied intercensal discrepancy.

    After each census the ABS spreads the census-against-estimate gap over the previous 20
    quarters, hence the peaks and troughs near census dates. The open period since the latest
    census is zero by convention, so it is shaded.
    """
    discrepancy = (data.growth["ERP Growth less Natural Increase"] - _nom_monthly()).dropna()
    discrepancy.name = "Implied intercensal discrepancy"
    discrepancy, units = recalibrated(discrepancy, _growth_units(data))
    line_plot_finalise(
        discrepancy,
        title="Implied Intercensal Discrepancy: (ERP growth - NI) - NOM",
        ylabel=f"{units} of persons / year",
        dropna=True,
        y0=True,
        annotate=True,
        axvline=[
            {"x": census, "color": "lightgrey", "linestyle": ":", "linewidth": 0.8} for census in CENSUS_MONTHS
        ],
        axvspan={
            "xmin": LAST_CENSUS,
            "xmax": discrepancy.index[-1],
            "color": "lightgrey",
            "alpha": 0.35,
            "label": "Open intercensal period (discrepancy = 0 by convention)",
        },
        legend=True,
        lfooter="Australia. Original series. 4Q rolling sums. "
        "Peaks near census years: the ABS spreads each census revision over the prior 20 quarters. ",
        rfooter=SOURCE_3101,
        pre_tag="multi",
    )


# --- table of contents, in run order
CHARTS = (
    (population_estimates, ()),
    (population_growth, ()),
    (population_growth_rate, ()),
    (implied_migration, ()),
    (growth_components, ()),
    (growth_split, ()),
    (migration_tty, ()),
    (migration_growth_rate, ()),
    (migration_share_of_growth, ()),
    (nom_forward_proxy, ()),
    (population_growth_proxy, ()),
    (nom_vs_erp_growth_less_ni, ()),
    (erp_growth_less_ni_minus_nom, ()),
)
