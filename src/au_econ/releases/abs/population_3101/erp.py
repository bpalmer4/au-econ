"""The official ERP: revisions, births, deaths and migration, natural increase, states, and growth."""

# --- dependencies
import re
from typing import Any

import pandas as pd
import readabs as ra
from mgplot import (
    abbreviate_state,
    growth_plot_finalise,
    line_plot_finalise,
    multi_start,
    postcovid_plot_finalise,
    revision_plot_finalise,
    seastrend_plot_finalise,
    series_growth_plot_finalise,
)
from readabs import metacol as mc

from au_econ.analysis.decompose import decompose
from au_econ.charting.windows import quarterly_plot_times
from au_econ.releases.abs.population_3101.common import (
    AGGREGATES,
    CATALOGUE,
    COVID_YEARS,
    DISCONTINUITIES,
    ORIGINAL,
    PERCENT,
    QUARTERS_PER_YEAR,
    SOURCE_3101,
    STATES_TABLE,
    PopulationData,
    aggregate,
    recalibrated,
)

# --- constants
REVISION_PRINTS = 6
REVISED = (
    "Estimated Resident Population",
    "Births ;  Australia ;",
    "Deaths ;  Australia ;",
    "Natural Increase ;  Australia ;",
    "Overseas Arrivals ;  Australia ;",
    "Overseas Departures ;  Australia ;",
    "Net Overseas Migration ;  Australia ;",
)
REVISION_LEGEND = {"loc": "best", "fontsize": 9}
ORIGINAL_LFOOTER = f"Australia. {ORIGINAL} series. "
KEY_SERIES = (
    "Births",
    "Deaths",
    "Natural Increase",
    "Overseas Arrivals",
    "Overseas Departures",
    "Net Overseas Migration",
)
ERP_PHRASE = "Estimated Resident Population ;  Persons ;"
LEVEL_GROWTH = (  # title, description, and whether a stock (growth = difference) or a flow
    (
        "Estimated Resident Population: Quarterly and Annual Growth",
        "Estimated Resident Population (ERP) ;  Australia ;",
        True,
    ),
    ("Net Overseas Migration: Quarterly and Annual Totals", "Net Overseas Migration ;  Australia ;", False),
)


# --- charts
def data_revisions(_data: PopulationData) -> None:
    """Chart the revisions to the headline 310101 series across the last six ABS prints."""
    for series in REVISED:
        units = None
        repository = pd.DataFrame()
        history = None
        for _ in range(REVISION_PRINTS):
            data, meta = ra.read_abs_cat(CATALOGUE, single_excel_only=AGGREGATES, history=history)
            table, series_id, units = ra.find_abs_id(
                meta, {series: mc.did, ORIGINAL: mc.stype}, regex=False, verbose=False
            )
            print_date = data[table].index[-1]
            repository[f"ABS print for {print_date.strftime('%Y-%b')}"] = data[table][series_id]
            history = (print_date - 1).strftime("%b-%Y").lower()
        if units is None:
            continue
        name = re.sub(":.*$", "", series)
        revision_plot_finalise(
            data=repository,
            ylabel=units,
            title=f"Data revisions: {name}",
            rfooter=SOURCE_3101,
            lfooter=ORIGINAL_LFOOTER,
            legend=REVISION_LEGEND,
            pre_tag="erp",
        )
        if series == "Estimated Resident Population":
            revision_plot_finalise(
                data=repository.diff(1),
                ylabel=units,
                title=f"Data revisions: {name} Growth",
                rfooter=SOURCE_3101,
                lfooter=ORIGINAL_LFOOTER,
                legend=REVISION_LEGEND,
                pre_tag="erp",
            )


def key_demographics(data: PopulationData) -> None:
    """Chart births, deaths, natural increase, arrivals, departures and NOM: raw, SA and post-COVID."""
    for chart in KEY_SERIES:
        raw, units = aggregate(data, chart)
        raw.name = chart
        series, units = recalibrated(raw, units)
        common: dict[str, Any] = {
            "title": chart,
            "y0": True,
            "ylabel": f"{units} / Quarter",
            "rfooter": SOURCE_3101,
            "pre_tag": "erp",
        }
        line_plot_finalise(series, lfooter=f"Australia. {ORIGINAL} series. ", **common)
        decomposed = decompose(
            series.dropna(),
            constant_seasonal=True,
            arima_extend=True,
            discontinuity_list=DISCONTINUITIES[chart],
            ignore_years=COVID_YEARS,
        )
        multi_start(
            decomposed[["Seasonally Adjusted", "Trend"]],
            function=seastrend_plot_finalise,
            starts=quarterly_plot_times,
            tag="sa-trend",
            lfooter="Australia. Seasonally adjusted using in-house methods. ",
            **common,
        )
        postcovid_plot_finalise(
            decomposed["Seasonally Adjusted"],
            tag="covid-recovery",
            lfooter="Australia. Seasonally adjusted series plotted. Seasonally adjusted using in-house methods. ",
            **common,
        )


def natural_increase_ratios(data: PopulationData) -> None:
    """Chart natural increase as a percentage of population, and of gross population increase."""
    erp = aggregate(data, "Estimated Resident Population")[0]
    natural_increase = aggregate(data, "Natural Increase")[0]
    deaths = aggregate(data, "Deaths")[0]

    of_population = natural_increase.rolling(QUARTERS_PER_YEAR).sum() / erp * PERCENT
    of_population.name = "Natural Increase (% of population, annualised)"
    multi_start(
        of_population.dropna(),
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title="Natural Increase as Percentage of Population",
        ylabel="Per cent per year",
        y0=True,
        lfooter=f"Australia. {ORIGINAL} series. Annualised. ",
        rfooter=SOURCE_3101,
        annotate=True,
        pre_tag="erp",
    )
    of_gross = natural_increase / (erp.diff() + deaths) * PERCENT
    of_gross.name = "Natural Increase (% of gross increase)"
    multi_start(
        of_gross.dropna(),
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title="Natural Increase as Percentage of Gross Population Increase",
        ylabel="Per cent",
        y0=True,
        lfooter=f"Australia. {ORIGINAL} series. Gross increase = ERP change + deaths. ",
        rfooter=SOURCE_3101,
        annotate=True,
        pre_tag="erp",
    )


def state_erp(data: PopulationData) -> None:
    """Chart ERP for each state and territory: the level, against its pre-COVID trend, and growth."""
    meta = data.meta[STATES_TABLE]
    states = (
        meta.loc[(meta[mc.table] == STATES_TABLE) & meta[mc.did].str.contains(ERP_PHRASE), mc.did]
        .str.replace(ERP_PHRASE, "")
        .str.replace(" ;", "")
        .str.strip()
        .to_list()
    )
    for state in states:
        selector = {STATES_TABLE: mc.table, ERP_PHRASE: mc.did, f";  {state} ;": mc.did}
        _table, series_id, units = ra.find_abs_id(meta, selector, verbose=False)
        raw = data.tables[STATES_TABLE][series_id]
        raw.name = "Estimated Resident Population"
        series, units = recalibrated(raw, "Number Persons" if units == "Persons" else units)
        title = f"Estimated Resident Population: {abbreviate_state(state)}"
        line_plot_finalise(
            series,
            title=title,
            ylabel=units,
            rfooter=SOURCE_3101,
            lfooter=ORIGINAL_LFOOTER,
            pre_tag="erp",
        )
        postcovid_plot_finalise(
            series,
            title=title,
            ylabel=units,
            tag="-covid",
            rfooter=SOURCE_3101,
            lfooter=ORIGINAL_LFOOTER,
            pre_tag="erp",
        )
        for start in quarterly_plot_times:
            series_growth_plot_finalise(
                series,
                plot_from=start,
                tag=f"growth-{start}",
                title=f"Growth in the {title}",
                rfooter=SOURCE_3101,
                lfooter=ORIGINAL_LFOOTER,
                pre_tag="erp",
            )


def level_growth(data: PopulationData) -> None:
    """Chart ERP and NOM growth in persons: quarterly increments (bars) and annual totals (line), recently.

    ERP is a stock, so its increments are differences; NOM is already a quarterly flow, so its
    quarterly value is the increment and its four-quarter sum the annual total.
    """
    for title, did, stock in LEVEL_GROWTH:
        level = aggregate(data, did)[0]
        if stock:
            annual, periodic = level.diff(QUARTERS_PER_YEAR), level.diff(1)
        else:
            annual, periodic = level.rolling(QUARTERS_PER_YEAR).sum(), level
        growth, units = recalibrated(
            pd.DataFrame({"Annual Growth": annual, "Quarterly Growth": periodic}), "Thousands"
        )
        growth_plot_finalise(
            growth,
            plot_from=quarterly_plot_times[1],
            title=title,
            ylabel=f"{units} of persons",
            rfooter=SOURCE_3101,
            lfooter=f"Australia. {ORIGINAL} series. ",
            y0=True,
            zero_y=True,
            legend=True,
            pre_tag="erp",
            tag="level-growth",
        )


# --- table of contents, in run order
CHARTS = (
    (data_revisions, ()),
    (key_demographics, ()),
    (natural_increase_ratios, ()),
    (state_erp, ()),
    (level_growth, ()),
)
