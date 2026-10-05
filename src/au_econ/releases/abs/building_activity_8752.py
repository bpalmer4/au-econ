"""Building Activity, Australia (8752.0): dwellings commenced, completed, under construction and not yet commenced.

Also the building cycle against approvals (8731.0), and completions per person, per adult
(6202.0 civilian population aged 15+) and per new adult.
"""

# --- dependencies
import textwrap
from typing import Any

import pandas as pd
import readabs as ra
from matplotlib.ticker import NullFormatter, ScalarFormatter
from mgplot import finalise_plot, get_color, line_plot, line_plot_finalise, multi_start, seastrend_plot_finalise
from readabs import metacol as mc

from au_econ.charting.windows import quarterly_plot_times
from au_econ.series.population import get_erp
from au_econ.sources.abs import AbsRelease, fetch_release

# --- module contract
RELEASE = ("8752", "activity")
TOPICS = ("building",)
TITLE = "Building Activity"

# --- constants
CATALOGUE = "8752.0"
SOURCE = f"ABS: {CATALOGUE}"
CIV_POP_SOURCE = "ABS: 6202.0, 8752.0"
MONTHLY_RECENT = (0, -61)
TITLE_WIDTH = 60
ANNUAL_QTRS, ANNUAL_MONTHS, QUARTER_MONTHS = 4, 12, 3
PER_THOUSAND = 1_000
ERP_PROJECTION = 2  # quarters: extends ERP to cover the newest completions
LEGEND = {"loc": "best", "fontsize": "x-small"}

# trend building approvals (8731.0), named by description
APPROVALS_CAT, APPROVALS_TABLE = "8731.0", "8731006"
APPROVALS_DID = "Total number of dwelling units ;  Total (Type of Building) ;  Total Sectors ;"

COMMENCED, COMPLETED = "87520033", "87520037"
STATE_COMPLETED = "87520038"
ALL_DWELLINGS = "Total Sectors ;  Total (Type of Building) ;  Total (Type of Work) ;"
COMMENCED_DID = f"Dwelling units commenced ;  {ALL_DWELLINGS}"
COMPLETED_DID = f"Dwelling units completed ;  {ALL_DWELLINGS}"
HEADLINES = (  # (table, description)
    (COMMENCED, "Dwelling units commenced ;  Total Sectors ;  Houses ;  New ;"),
    (COMMENCED, "Dwelling units commenced ;  Total Sectors ;  Total Other Residential ;  New ;"),
    (COMMENCED, COMMENCED_DID),
    (COMPLETED, "Dwelling units completed ;  Total Sectors ;  Houses ;  New ;"),
    (COMPLETED, "Dwelling units completed ;  Total Sectors ;  Total Other Residential ;  New ;"),
    (COMPLETED, COMPLETED_DID),
    # under construction and not yet commenced are published Original only
    ("87520076", "Dwelling units under construction ;  Total Sectors ;  Houses ;  New ;"),
    ("87520076", "Dwelling units under construction ;  Total Sectors ;  Total Other Residential ;  New ;"),
    (
        "87520076",
        (
            "Dwelling units under construction ;  Total Sectors ;  Dwellings excluding new residential ;  "
            "Total (Type of Work) ;"
        ),
    ),
    ("87520076", f"Dwelling units under construction ;  {ALL_DWELLINGS}"),
    ("87520080", "Dwelling units not yet commenced ;  Houses ;  New ;  Australia ;"),
    ("87520080", "Dwelling units not yet commenced ;  Total Other Residential ;  New ;  Australia ;"),
    (
        "87520080",
        "Dwelling units not yet commenced ;  Total (Type of Building) ;  Total (Type of Work) ;  Australia ;",
    ),
)
SA, TREND, ORIGINAL = "Seasonally Adjusted", "Trend", "Original"
TARGET_LINE = {
    "y": 60,
    "label": "Target: build 1.2 million well-located new homes over 5 years, from 1 July 2024",
    "color": "darkred",
    "linestyle": "--",
    "lw": 0.75,
}

# civilian population aged 15+ (6202.0), by state
POP_TABLES = {
    "Australia": "62020001",
    "New South Wales": "62020002",
    "Victoria": "62020003",
    "Queensland": "62020004",
    "South Australia": "62020005",
    "Western Australia": "62020006",
    "Tasmania": "62020007",
    "Northern Territory": "62020008",
    "Australian Capital Territory": "62020009",
}
CIV_POP_DID = "Civilian population aged 15 years and over ;  Persons ;"
STATE_TOTAL = "Total (Type of Building) ;  Total (Type of Work) ;  Total Sectors ;"
COMPARE_STATES = ["New South Wales", "Victoria", "Queensland", "Western Australia"]

# completions per new adult
COMP_PER_GROWTH_YLIM = (0.2, 1.3)  # above the pre-COVID maximum, below the border-closure spike
COVID_SPAN = {
    "xmin": pd.Period("2020Q2", freq="Q-DEC"),
    "xmax": pd.Period("2024Q3", freq="Q-DEC"),
    "color": "goldenrod",
    "alpha": 0.3,
    "label": "COVID impacted inc. migration rebound",
}
LOG_YTICKS = [0.3, 0.4, 0.5, 0.7, 1.0, 1.5, 2.0, 3.0, 4.0]  # roughly even multiplicative steps


# --- data
def fetch() -> AbsRelease:
    """Fetch the release once; every chart function receives it."""
    return fetch_release(CATALOGUE)


# --- helpers
def _recalibrated[T: (pd.Series, pd.DataFrame)](data: T, units: str) -> tuple[T, str]:
    result, units = ra.recalibrate(data, units)
    if not isinstance(result, type(data)):
        raise TypeError(f"recalibrate returned {type(result).__name__}")
    return result, units


def _trend(release: AbsRelease, table: str, did: str) -> tuple[pd.Series, str]:
    """One trend 8752 series, by table and description, with its units."""
    _table, series_id, units = ra.find_abs_id(release.meta, {table: mc.table, did: mc.did, TREND: mc.stype})
    return release.data[table][series_id], units


def _trend_approvals() -> tuple[pd.Series, str]:
    """Trend monthly dwelling approvals (8731.0), with their units."""
    data, meta = ra.read_abs_cat(APPROVALS_CAT, single_excel_only=APPROVALS_TABLE)
    _table, series_id, units = ra.find_abs_id(
        meta, {APPROVALS_TABLE: mc.table, APPROVALS_DID: mc.did, TREND: mc.stype}, exact_match=True, verbose=False
    )
    return data[APPROVALS_TABLE][series_id].dropna(), units


def _log_line_chart(
    data: pd.Series, *, yticks: list[float], line_kw: dict[str, Any], finalise_kw: dict[str, Any], **extra: Any
) -> None:
    """Plot a series on a log y-axis with plain decimal tick labels and a gridline at each tick.

    matplotlib labels a log axis in scientific notation and puts intermediate values on the
    minor locator, which mgplot's grid does not draw; there is no formatter hook in the
    finalise path, so the line is drawn, the axis set here, and the plot then finalised.
    """
    axes = line_plot(data, **line_kw)
    axes.set_yscale("log")  # resets the locators, so set the ticks after it
    axes.set_yticks(yticks)
    formatter = ScalarFormatter()
    formatter.set_scientific(False)
    axes.yaxis.set_major_formatter(formatter)
    axes.yaxis.set_minor_formatter(NullFormatter())
    finalise_plot(axes, **finalise_kw, **extra)


# --- charts
def headline(release: AbsRelease) -> None:
    """Chart dwellings commenced, completed, under construction and not yet commenced."""
    for table, did in HEADLINES:
        found_series: dict[str, pd.Series] = {}
        units = ""
        for stype in (SA, TREND, ORIGINAL):
            try:
                _table, series_id, units = ra.find_abs_id(
                    release.meta, {table: mc.table, did: mc.did, stype: mc.stype}
                )
            except ValueError:
                continue
            found_series[stype] = release.data[table][series_id]
        found, units = _recalibrated(pd.DataFrame(found_series).sort_index(), units)
        title = textwrap.fill(did, TITLE_WIDTH)
        if SA in found_series and TREND in found_series:
            if ORIGINAL in found_series:
                found = found.drop(ORIGINAL, axis=1)
            multi_start(
                found,
                function=seastrend_plot_finalise,
                starts=quarterly_plot_times,
                title=title,
                lfooter="Australia. ",
                rfooter=SOURCE,
                ylabel=f"{units}/Quarter",
            )
        elif ORIGINAL in found_series:
            multi_start(
                found[ORIGINAL],
                function=line_plot_finalise,
                starts=quarterly_plot_times,
                title=title,
                lfooter="Australia. Original series. ",
                rfooter=SOURCE,
                ylabel=f"{units}/Quarter",
            )


def building_cycle(release: AbsRelease) -> None:
    """Chart trend commencements and completions, then the same with trend approvals (quarterly-equivalent)."""
    common: dict[str, Any] = {
        "function": line_plot_finalise,
        "axhline": TARGET_LINE,
        "legend": LEGEND,
        "annotate": True,
    }
    series, units = {}, ""
    for table, did in ((COMMENCED, COMMENCED_DID), (COMPLETED, COMPLETED_DID)):
        series[did], units = _trend(release, table, did)
    found, units = _recalibrated(pd.DataFrame(series).sort_index(), units)
    multi_start(
        found,
        starts=quarterly_plot_times,
        title="Trend Commencements and Completions",
        rfooter=SOURCE,
        ylabel=f"{units}/Quarter",
        lfooter="Australia. ",
        **common,
    )

    approvals, approval_units = _trend_approvals()
    monthly = {key: ra.qtly_to_monthly(value) for key, value in series.items()}
    monthly[f"Building Approvals ;  {APPROVALS_DID}"] = approvals.rolling(QUARTER_MONTHS).sum()
    found, units = _recalibrated(pd.DataFrame(monthly).sort_index(), approval_units)
    multi_start(
        found,
        starts=MONTHLY_RECENT,
        title="Trend Approvals, Commencements and Completions",
        rfooter="ABS: 8731.0, 8752.0",
        ylabel=f"{units}/Quarter",
        lfooter="Australia. Approvals: 3-month rolling sum (quarterly-equivalent rate on monthly index). ",
        **common,
    )


def completions_per_capita(release: AbsRelease) -> None:
    """Chart trend dwelling completions per 1000 people (annualised)."""
    completions, _units = _trend(release, COMPLETED, COMPLETED_DID)
    population, _ = get_erp(project_quarters=ERP_PROJECTION)
    multi_start(
        (completions.rolling(ANNUAL_QTRS).sum() / population * PER_THOUSAND).dropna(),
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title="Trend Dwelling Completions per 1000 People",
        lfooter="Australia. Annualised (rolling 4-quarter sum). ",
        rfooter="ABS: 3101.0, 8752.0",
        ylabel="Dwellings/1000 people/year",
        annotate=True,
    )


def approvals_commencements_completions_per_capita(release: AbsRelease) -> None:
    """Chart approvals, commencements and completions per 1000 people, monthly; approvals lead the others."""
    completions, _ = _trend(release, COMPLETED, COMPLETED_DID)
    commencements, _ = _trend(release, COMMENCED, COMMENCED_DID)
    approvals, _ = _trend_approvals()
    population_q, _ = get_erp(project_quarters=ERP_PROJECTION)
    population = ra.qtly_to_monthly(population_q)
    frame = pd.DataFrame(
        {
            "Approvals (12m sum, trend)": approvals.rolling(ANNUAL_MONTHS).sum() / population * PER_THOUSAND,
            "Commencements (4q sum, trend)": ra.qtly_to_monthly(commencements.rolling(ANNUAL_QTRS).sum())
            / population
            * PER_THOUSAND,
            "Completions (4q sum, trend)": ra.qtly_to_monthly(completions.rolling(ANNUAL_QTRS).sum())
            / population
            * PER_THOUSAND,
        }
    )
    multi_start(
        frame,
        function=line_plot_finalise,
        starts=MONTHLY_RECENT,
        title="Trend Approvals, Commencements & Completions per 1000 People",
        ylabel="Dwellings/1000 people/year",
        style=["--", "-", "-"],
        dropna=True,
        legend=LEGEND,
        annotate=True,
        lfooter="Australia. Trend series. Annualised rolling sums. "
        "Approvals shown on monthly basis (leads commencements/completions). ",
        rfooter="ABS: 3101.0, 8731.0, 8752.0",
    )


def completions_per_civ_pop(release: AbsRelease) -> None:
    """Chart trend completions per 1000 civilians aged 15+, for each state and Australia, and four states together.

    The population is in thousands, so annual completions over it is the rate per 1000.
    """
    ratios = {}
    for jurisdiction, pop_table in POP_TABLES.items():
        if jurisdiction == "Australia":
            completions, _ = _trend(release, COMPLETED, COMPLETED_DID)
        else:
            completions, _ = _trend(
                release, STATE_COMPLETED, f"Dwelling units completed ;  {jurisdiction} ;  {STATE_TOTAL}"
            )
        data, meta = ra.read_abs_cat("6202.0", single_excel_only=pop_table)
        _table, pop_id, _units = ra.find_abs_id(meta, {pop_table: mc.table, CIV_POP_DID: mc.did})
        population = ra.monthly_to_qtly(data[pop_table][pop_id], f="mean")
        ratios[jurisdiction] = (completions.rolling(ANNUAL_QTRS).sum() / population).dropna()
    frame = pd.DataFrame(ratios)

    source = CIV_POP_SOURCE
    ylabel = "Completions/1000 people aged 15+/year"
    note = "Trend completions, annualised (rolling 4-quarter sum). "
    for jurisdiction in frame.columns:
        multi_start(
            frame[jurisdiction].dropna(),
            function=line_plot_finalise,
            starts=quarterly_plot_times,
            title=f"Completions per 1000 People Aged 15+: {jurisdiction}",
            lfooter=f"Australia. {note}",
            rfooter=source,
            ylabel=ylabel,
            annotate=True,
        )
    multi_start(
        frame[COMPARE_STATES],
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title="Completions per 1000 People Aged 15+: NSW, Vic, Qld, WA",
        lfooter=f"Australia. {note}",
        rfooter=source,
        ylabel=ylabel,
        color=[get_color(state) for state in COMPARE_STATES],
        annotate=True,
        legend=LEGEND,
    )


def completions_per_pop_growth(release: AbsRelease) -> None:
    """Chart trend completions per new person aged 15+: linear, log, and linear clipped past the COVID spike.

    Both sides are a year's worth: annualised completions over the through-the-year change in
    the civilian population aged 15+. The ratio moves multiplicatively, so the log pair reads
    fairer; the denominator nears zero in the border closure, hence the clipped linear chart.
    """
    completions, _units = _trend(release, COMPLETED, COMPLETED_DID)
    annual_completions = completions.dropna().rolling(ANNUAL_QTRS).sum()
    pop_table = POP_TABLES["Australia"]
    data, meta = ra.read_abs_cat("6202.0", single_excel_only=pop_table)
    _table, pop_id, _pop_units = ra.find_abs_id(
        meta, {pop_table: mc.table, CIV_POP_DID: mc.did, ORIGINAL: mc.stype}
    )
    population = data[pop_table][pop_id].dropna() * PER_THOUSAND  # '000 -> persons
    if population.empty:
        raise ValueError(f"No civilian population 15+ data found in {pop_table}")
    quarterly = ra.monthly_to_qtly(population, f="mean")
    ratio = (annual_completions / (quarterly - quarterly.shift(ANNUAL_QTRS))).dropna()
    ratio.name = "Completions per new person aged 15+"
    if ratio.empty:
        raise ValueError("Completions and population 15+ series do not overlap")

    title = "Completions per New Person Aged 15+"
    line_kw: dict[str, Any] = {"annotate": True, "rounding": 2}
    ylabel = "Annual completions /\nannual growth in 15+ population"
    finalise_kw: dict[str, Any] = {
        "lfooter": "Australia. Trend completions, 4Q rolling sum, over the year's change in civilian population "
        "aged 15+. ",
        "rfooter": CIV_POP_SOURCE,
        "ylabel": ylabel,
    }
    multi_start(
        ratio, function=line_plot_finalise, starts=quarterly_plot_times, title=title, **line_kw, **finalise_kw
    )
    for i, start in enumerate(quarterly_plot_times):
        _log_line_chart(
            ratio.iloc[start:],
            yticks=LOG_YTICKS,
            line_kw=line_kw,
            finalise_kw=finalise_kw | {"ylabel": f"{ylabel} (log scale)"},
            title=title,
            tag=f"log-{i}",
        )
    line_plot_finalise(
        ratio,
        title=title,
        ylim=COMP_PER_GROWTH_YLIM,
        axvspan=COVID_SPAN,
        legend=LEGEND,
        tag="clipped",
        **line_kw,
        **finalise_kw,
    )


# --- table of contents, in run order
CHARTS = (
    (headline, ()),
    (building_cycle, ()),
    (completions_per_capita, ()),
    (approvals_commencements_completions_per_capita, ()),
    (completions_per_civ_pop, ()),
    (completions_per_pop_growth, ()),
)
