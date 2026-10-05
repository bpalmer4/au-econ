"""Australian National Accounts: State Accounts (5220.0): gross state product growth, per head and per km².

Financial years ending 30 June.
"""

# --- dependencies
import mgplot as mg
import pandas as pd
import readabs as ra
from readabs import metacol as mc

from au_econ.series.population import get_state_erp
from au_econ.sources.abs import AbsRelease, fetch_release

# --- module contract
RELEASE = ("5220", "state-accounts")
TOPICS = ("economy",)
TITLE = "State Accounts"

# --- constants
CATALOGUE = "5220.0"
SOURCE_WITH_ERP = "ABS: 3101.0, 5220.0"  # GSP per head divides by 3101.0 state ERP
GSP_TABLE = "5220001_Annual_Gross_State_Product_All_States"
GSP_GROWTH_DID = ";  Gross state product: Chain volume measures - Percentage changes ;"
GSP_DID = ";  Gross state product: Chain volume measures ;"
ORIGINAL = "Original"
STATE_MAP = dict(zip(mg.state_names, mg.state_abbrs, strict=True))
STATE_AREAS_KM2 = pd.Series(
    {
        "New South Wales": 809_952,
        "Victoria": 237_657,
        "Queensland": 1_851_736,
        "South Australia": 1_044_353,
        "Western Australia": 2_642_753,
        "Tasmania": 90_758,
        "Northern Territory": 1_420_970,
        "Australian Capital Territory": 2_358,
    }
)
GROWTH_LEGEND = {"loc": "best", "ncol": 2, "fontsize": "small"}


# --- data
def fetch() -> AbsRelease:
    """Fetch the release once; every chart function receives it."""
    return fetch_release(CATALOGUE)


# --- helpers
def get_data(release: AbsRelease, table: str, did: str, stype: str) -> tuple[pd.DataFrame, str]:
    """Return a set of related state columns, named by state, with their units."""
    rows = ra.search_abs_meta(release.meta, {table: mc.table, did: mc.did, stype: mc.stype})
    data = release.data[table][rows[mc.id]]
    data.index.name = "Year"
    data.columns = rows[mc.did].str.replace(did, "").str.strip().tolist()
    return data, rows[mc.unit].iloc[0]


def latest_gsp(release: AbsRelease) -> tuple[pd.Series, str, pd.Period, pd.Period]:
    """Return the latest year's real GSP by state, its units, the year, and the June quarter it ends in."""
    data, units = get_data(release, GSP_TABLE, GSP_DID, ORIGINAL)
    recent_year = data.index[-1]
    if not isinstance(recent_year, pd.Period):
        raise TypeError("Expected an annual Period index")
    return data.iloc[-1], units, recent_year, pd.Period(f"{recent_year}-Q2", freq="Q")


# --- charts
def annual_growth(release: AbsRelease) -> None:
    """Chart annual growth in real gross state product, one line per state."""
    data, _units = get_data(release, GSP_TABLE, GSP_GROWTH_DID, ORIGINAL)
    data.columns = [STATE_MAP[s] for s in data.columns]
    mg.line_plot_finalise(
        data,
        title="Real Gross State Product, Annual Percentage Change",
        color=[mg.get_color(x) for x in data.columns],
        xlabel="Financial Year ending June 30",
        ylabel="Annual Percentage Change (%)",
        y0=True,
        rfooter=release.source,
        lfooter="Australia. Original series. Chain volume measures. ",
        legend=GROWTH_LEGEND,
    )


def gsp_per_capita(release: AbsRelease) -> None:
    """Chart the latest year's real gross state product per head, by state."""
    recent_gsp, gsp_units, recent_year, recent_qtr = latest_gsp(release)
    state_pops = pd.DataFrame({state: get_state_erp(state)[0] for state in mg.state_names})
    recent_pop_date = recent_qtr if recent_qtr in state_pops.index else state_pops.index[-1]
    recent_pop = state_pops[state_pops.index == recent_pop_date].iloc[0]
    per_capita, pc_units = ra.recalibrate(recent_gsp.div(recent_pop), gsp_units)
    per_capita.index = [STATE_MAP[s] for s in per_capita.index]
    per_capita = per_capita.sort_values()
    mg.bar_plot_finalise(
        per_capita,
        horizontal=True,
        color=[mg.get_color(s) for s in per_capita.index],
        annotate=True,
        above=True,
        title="Gross State Product per Capita, Latest Year",
        xlabel=f"{pc_units} per Capita",
        rfooter=SOURCE_WITH_ERP,
        lfooter="Australia. Original series. Chain volume measures. "
        f"Population at {recent_pop_date}. Financial Year ending in {recent_year}. ",
    )


def gsp_per_km2(release: AbsRelease) -> None:
    """Chart the latest year's real gross state product per km², with and without the ACT."""
    recent_gsp, gsp_units, recent_year, _recent_qtr = latest_gsp(release)
    per_area = recent_gsp.div(STATE_AREAS_KM2)
    per_area.index = [STATE_MAP[s] for s in per_area.index]
    for tag, frame in (("0", per_area), ("1", per_area.drop("ACT"))):
        plot_data, plot_units = ra.recalibrate(frame, gsp_units)
        plot_data = plot_data.sort_values()
        mg.bar_plot_finalise(
            plot_data,
            horizontal=True,
            color=[mg.get_color(s) for s in plot_data.index],
            annotate=True,
            above=True,
            title="Gross State Product per km², Latest Year",
            xlabel=plot_units + " per km²",
            tag=tag,
            rfooter=release.source,
            lfooter=f"Australia. Original series. Chain volume measures. Financial Year ending in {recent_year}. ",
        )


# --- table of contents, in run order
CHARTS = (
    (annual_growth, ()),
    (gsp_per_capita, ()),
    (gsp_per_km2, ()),
)
