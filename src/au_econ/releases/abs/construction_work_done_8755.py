"""Construction Work Done, Australia, Preliminary (8755.0): building and engineering work done, quarterly.

The dollar value of all construction, by sector, state and type of work, including
non-residential building and engineering; it complements the dwelling counts in 8752.
"""

# --- dependencies
import pandas as pd
import readabs as ra
from mgplot import get_color, line_plot_finalise, multi_start, seastrend_plot_finalise, series_growth_plot_finalise
from readabs import metacol as mc

from au_econ.charting.windows import quarterly_plot_times
from au_econ.series.gdp import get_gdp
from au_econ.sources.abs import AbsRelease, fetch_release

# --- module contract
RELEASE = ("8755", "cwd")
TOPICS = ("building",)
TITLE = "Construction Work Done"

# --- constants
CATALOGUE = "8755.0"
ANNUAL_QTRS = 4  # quarters in a year: annualising window
PERCENT = 100
THOUSANDS_PER_MILLION = 1_000
INDEX_BASE = pd.Period("2019Q4", freq="Q-DEC")  # pre-COVID base for indexing
GDP_SOURCE = "ABS: 5206.0, 8755.0"
LEGEND = {"loc": "best", "fontsize": "x-small"}

# 8755.0 table names
CVM_TABLE = "8755001"  # by sector, chain volume measures
CP_TABLE = "8755002"  # by sector, current prices
BUILDING_CP_TABLE = "8755006"  # building by type of work, current prices
STATE_CVM_TABLE = "8755008"  # by state, chain volume measures
ENG_TYPE_TABLE = "87550010"  # engineering by type, current prices, Original only

# data item description fragments -> chart labels
CONSTRUCTION_TYPES = {
    "Total building": "Building",
    "Engineering Construction": "Engineering",
    "Total (Type of Construction)": "All Construction",
}
ALL_CONSTRUCTION = "Total (Type of Construction)"
SECTORS = ("Total Sectors", "Private Sector", "Public Sector")
ALL_SECTORS = "Total Sectors"
SEAS_TREND = ("Seasonally Adjusted", "Trend")
SA = "Seasonally Adjusted"

# current prices do not split new residential into houses and other residential
BUILDING_WORK_TYPES = {
    "New ;  Total Residential ;": "New residential",
    "Alterations and additions including conversions ;  Total Residential ;": "Alterations and additions",
    "Total (Type of Work) ;  Total Non-residential ;": "Non-residential",
}
ENG_WORK_TYPES = {
    "Roads, highways and subdivisions": "Roads",
    "Railways": "Railways",
    "Electricity generation, transmission and distribution": "Electricity",
    "Oil, gas, coal and other minerals": "Oil, gas, coal and minerals",
    "Water storage and supply": "Water",
    "Telecommunications": "Telecommunications",
}
COMPARE_STATES = ("New South Wales", "Victoria", "Queensland", "Western Australia")


# --- data
def fetch() -> AbsRelease:
    """Fetch the release once; every chart function receives it."""
    return fetch_release(CATALOGUE)


# --- helpers
def _series(release: AbsRelease, table: str, did: str, stype: str) -> tuple[pd.Series, str]:
    """Select one series by table, data item description and series type; raise if it is empty.

    A renamed or discontinued series then fails here rather than as a blank chart.
    """
    _table, series_id, units = ra.find_abs_id(
        release.meta, {table: mc.table, did: mc.did, stype: mc.stype}, verbose=False
    )
    series = release.data[table][series_id].dropna()
    if series.empty:
        raise ValueError(f"No data for {stype} {did!r} in table {table}")
    return series, units


def _nominal_gdp(series_type: str) -> pd.Series:
    """Nominal GDP (5206.0) in $ Millions; series_type is SA, T or O."""
    gdp, units = get_gdp("CP", series_type)
    if units != "$ Millions":
        raise ValueError(f"Expected nominal GDP in $ Millions, got {units!r}")
    return gdp


def _share_of_gdp(work: pd.Series, units: str, gdp: pd.Series) -> pd.Series:
    """Current-price work done ($'000) as a percentage of nominal GDP ($ Millions).

    The two series must be the same kind of flow (both quarterly, or both annualised).
    """
    if units != "$'000":
        raise ValueError(f"Expected work done in $'000, got {units!r}")
    return (work / THOUSANDS_PER_MILLION / gdp * PERCENT).dropna()


def _recalibrated(frame: pd.DataFrame, units: str) -> tuple[pd.DataFrame, str]:
    """Recalibrate a frame to readable units."""
    result, units = ra.recalibrate(frame, units)
    if not isinstance(result, pd.DataFrame):
        raise TypeError(f"recalibrate returned {type(result).__name__}")
    return result, units


def _share_chart(frame: pd.DataFrame, *, title: str, lfooter: str) -> None:
    """Chart shares of GDP, full history and recent."""
    multi_start(
        frame,
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title=title,
        ylabel="Per cent of GDP",
        annotate=True,
        legend=LEGEND,
        lfooter=lfooter,
        rfooter=GDP_SOURCE,
    )


# --- charts
def headline(release: AbsRelease) -> None:
    """Seasonally adjusted and trend work done (CVM), by sector and construction type."""
    for sector in SECTORS:
        for ctype, label in CONSTRUCTION_TYPES.items():
            did = f"Value of work done ;  Chain Volume Measures ;  {sector} ;  {ctype} ;"
            parts = {}
            units = ""
            for stype in SEAS_TREND:
                parts[stype], units = _series(release, CVM_TABLE, did, stype)
            frame, units = _recalibrated(pd.DataFrame(parts), units)
            multi_start(
                frame,
                function=seastrend_plot_finalise,
                starts=quarterly_plot_times,
                title=f"Work Done: {label}: {sector}",
                ylabel=f"{units}/Quarter",
                lfooter="Australia. Chain volume measures. ",
                rfooter=release.source,
            )


def growth(release: AbsRelease) -> None:
    """Quarterly and through-the-year growth in work done (CVM, SA, all sectors)."""
    for ctype, label in CONSTRUCTION_TYPES.items():
        did = f"Value of work done ;  Chain Volume Measures ;  {ALL_SECTORS} ;  {ctype} ;"
        series, _units = _series(release, CVM_TABLE, did, SA)
        series_growth_plot_finalise(
            series,
            plot_from=quarterly_plot_times[1],
            title=f"Growth in Work Done: {label}",
            lfooter="Australia. Seasonally adjusted. Chain volume measures. ",
            rfooter=release.source,
        )


def composition(release: AbsRelease) -> None:
    """Chart building v engineering (all sectors), and private v public (all construction)."""
    comparisons = {
        "Work Done: Building v Engineering": {
            label: f"{ALL_SECTORS} ;  {ctype} ;"
            for ctype, label in CONSTRUCTION_TYPES.items()
            if ctype != ALL_CONSTRUCTION
        },
        "Work Done: Private v Public Sector": {
            sector: f"{sector} ;  {ALL_CONSTRUCTION} ;" for sector in SECTORS if sector != ALL_SECTORS
        },
    }
    for title, wanted in comparisons.items():
        parts = {}
        units = ""
        for label, fragment in wanted.items():
            did = f"Value of work done ;  Chain Volume Measures ;  {fragment}"
            parts[label], units = _series(release, CVM_TABLE, did, SA)
        frame, units = _recalibrated(pd.DataFrame(parts), units)
        multi_start(
            frame,
            function=line_plot_finalise,
            starts=quarterly_plot_times,
            title=title,
            ylabel=f"{units}/Quarter",
            annotate=True,
            legend=LEGEND,
            lfooter="Australia. Seasonally adjusted. Chain volume measures. ",
            rfooter=release.source,
        )


def share_of_gdp(release: AbsRelease) -> None:
    """Work done (current prices, SA) as a percentage of nominal GDP (SA): both quarterly flows."""
    gdp = _nominal_gdp("SA")
    shares = {}
    for ctype, label in CONSTRUCTION_TYPES.items():
        did = f"Value of work done ;  Current Prices ;  {ALL_SECTORS} ;  {ctype} ;"
        work, units = _series(release, CP_TABLE, did, SA)
        shares[label] = _share_of_gdp(work, units, gdp)
    _share_chart(
        pd.DataFrame(shares).dropna(),
        title="Construction Work Done as a Share of GDP",
        lfooter="Australia. Seasonally adjusted. Current prices. ",
    )


def building_by_work_type(release: AbsRelease) -> None:
    """Chart building work done by type of work (current prices, SA) as a share of nominal GDP."""
    gdp = _nominal_gdp("SA")
    parts = {}
    for fragment, label in BUILDING_WORK_TYPES.items():
        did = f"Value of work done during quarter ;  Current Prices ;  {ALL_SECTORS} ;  {fragment}"
        work, units = _series(release, BUILDING_CP_TABLE, did, SA)
        parts[label] = _share_of_gdp(work, units, gdp)
    _share_chart(
        pd.DataFrame(parts).dropna(),
        title="Building Work Done by Type of Work as a Share of GDP",
        lfooter="Australia. Seasonally adjusted. Current prices. All sectors. ",
    )


def engineering_by_type(release: AbsRelease) -> None:
    """Engineering work done by type (all sectors) as a share of nominal GDP.

    Published in current prices and Original only, so both sides are annualised with a
    rolling 4-quarter sum, which removes the seasonal pattern.
    """
    annual_gdp = _nominal_gdp("O").rolling(ANNUAL_QTRS).sum()
    parts = {}
    for eng_type, label in ENG_WORK_TYPES.items():
        did = f"Value of work done ;  Total all sectors ;  {eng_type} ;"
        work, units = _series(release, ENG_TYPE_TABLE, did, "Original")
        parts[label] = _share_of_gdp(work.rolling(ANNUAL_QTRS).sum(), units, annual_gdp)
    _share_chart(
        pd.DataFrame(parts).dropna(),
        title="Engineering Work Done by Type of Construction as a Share of GDP",
        lfooter="Australia. Original series. Current prices. All sectors. Annualised (rolling 4-quarter sums). ",
    )


def states(release: AbsRelease) -> None:
    """Chart work done (CVM, SA) by state, indexed to a pre-COVID base so states compare proportionally."""
    for ctype, label in CONSTRUCTION_TYPES.items():
        parts = {}
        for state in COMPARE_STATES:
            did = f"Value of work done ;  Chain Volume Measures ;  {state} ;  {ctype} ;"
            series, _units = _series(release, STATE_CVM_TABLE, did, SA)
            base = series[series.index == INDEX_BASE]
            if base.empty:
                raise ValueError(f"{state} {label}: no value for the index base {INDEX_BASE}")
            parts[state] = series / base.iloc[0] * PERCENT
        multi_start(
            pd.DataFrame(parts),
            function=line_plot_finalise,
            starts=quarterly_plot_times,
            title=f"Work Done by State: {label}",
            ylabel=f"Index ({INDEX_BASE} = 100)",
            color=[get_color(state) for state in COMPARE_STATES],
            annotate=True,
            legend=LEGEND,
            lfooter="Australia. Seasonally adjusted. Chain volume measures. ",
            rfooter=release.source,
        )


# --- table of contents, in run order
CHARTS = (
    (headline, ()),
    (growth, ()),
    (composition, ()),
    (share_of_gdp, ()),
    (building_by_work_type, ()),
    (engineering_by_type, ()),
    (states, ()),
)
