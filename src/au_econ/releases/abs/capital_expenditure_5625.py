"""Private New Capital Expenditure and Expected Expenditure, Australia (5625.0): actual capex, quarterly.

Total capex, by asset type and by industry, in current prices and chain volume measures;
and a data-centre signature: Information Media and Telecommunications (IMT) is where
hyperscaler investment is classified, and equipment within IMT (servers etc.) is the
import-intensive leg. The survey leads the national accounts by a quarter.
"""

# --- dependencies
import pandas as pd
import readabs as ra
from mgplot import line_plot_finalise, multi_start, series_growth_plot_finalise
from readabs import metacol as mc

from au_econ.charting.windows import quarterly_plot_times
from au_econ.sources.abs import AbsRelease, fetch_release

# --- module contract
RELEASE = ("5625", "capex")
TOPICS = ("building",)
TITLE = "Capital Expenditure"

# --- constants
CATALOGUE = "5625.0"
SA = "Seasonally Adjusted"
CVM = "chain volume measures"
MEASURES = {  # measure label: (table, price label in the data item description, short tag)
    "current prices": ("04_current_prices_seasonally_adjusted_capex", "Current Price", "CP"),
    CVM: ("07_volume_measures_seasonally_adjusted_capex", "Chain Volume Measures", "CVM"),
}
ALL_ASSETS = "Total (Type of Asset - Detailed Level)"
ALL_INDUSTRIES = "Total, including Education and Health"
BUILDINGS, EQUIPMENT = "Buildings and Structures", "Equipment, Plant and Machinery"
INDUSTRIES = (
    "Mining",
    "Non-Mining, including Education and Health",
    "Manufacturing",
    "Electricity, Gas, Water and Waste Services",
    "Construction",
    "Wholesale Trade",
    "Retail Trade",
    "Accommodation and Food Services",
    "Transport, Postal and Warehousing",
    "Information Media and Telecommunications",
    "Financial and Insurance Services",
    "Rental, Hiring and Real Estate Services",
    "Professional, Scientific and Technical Services",
    "Administrative and Support Services",
    "Education and Training",
    "Health Care and Social Assistance",
    "Arts and Recreation Services",
    "Other Services",
)
DATA_CENTRE_INDUSTRY = "Information Media and Telecommunications"
DATA_CENTRE_LFOOTER = "Australia. Seasonally adjusted. Chain volume measures. Data-centre proxy. "


# --- data
def fetch() -> AbsRelease:
    """Fetch the release once; every chart function receives it."""
    release = fetch_release(CATALOGUE)
    print("Latest data:", release.data[MEASURES["current prices"][0]].index[-1])
    return release


# --- helpers
def _raw(release: AbsRelease, asset: str, industry: str, measure: str) -> tuple[pd.Series, str]:
    """One seasonally adjusted capex level, by asset type, industry and measure, with its units."""
    table, price_label, _short = MEASURES[measure]
    did = f"Actual Expenditure ;  Total (State) ;  {asset} ;  {price_label} ;  {industry} ;"
    _table, series_id, units = ra.find_abs_id(
        release.meta, {table: mc.table, SA: mc.stype, did: mc.did}, verbose=False
    )
    series = release.data[table][series_id].dropna()
    if series.empty:
        raise ValueError(f"No data for {did!r} in table {table}")
    return series, units


def _capex(release: AbsRelease, asset: str, industry: str, measure: str) -> tuple[pd.Series, str]:
    """One capex level recalibrated to readable units."""
    series, units = ra.recalibrate(*_raw(release, asset, industry, measure))
    if not isinstance(series, pd.Series):
        raise TypeError(f"recalibrate returned {type(series).__name__}")
    return series, units


def _level_and_growth(series: pd.Series, units: str, *, title: str, lfooter: str, source: str) -> None:
    """Chart the level as a line (full history and recent) and its growth as bars and a line."""
    multi_start(
        series,
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title=title,
        ylabel=f"{units}/Quarter",
        rfooter=source,
        lfooter=lfooter,
    )
    series_growth_plot_finalise(
        series,
        plot_from=quarterly_plot_times[1],
        title=f"Growth: {title}",
        rfooter=source,
        lfooter=lfooter,
    )


def _by_measure(release: AbsRelease, asset: str, industry: str, label: str) -> None:
    """Chart one asset type and industry in current prices and in chain volume measures."""
    for measure, (_table, _price, short) in MEASURES.items():
        series, units = _capex(release, asset, industry, measure)
        _level_and_growth(
            series,
            units,
            title=f"CapEx: {label}: {short}",
            lfooter=f"Australia. {SA.capitalize()}. {measure.capitalize()}. ",
            source=release.source,
        )


# --- charts
def headline(release: AbsRelease) -> None:
    """Chart total private new capital expenditure: level and growth, CP and CVM."""
    _by_measure(release, ALL_ASSETS, ALL_INDUSTRIES, "total")


def by_asset_type(release: AbsRelease) -> None:
    """Chart capex by asset type: buildings and structures, and equipment, plant and machinery."""
    for asset in (BUILDINGS, EQUIPMENT):
        _by_measure(release, asset, ALL_INDUSTRIES, asset)


def by_industry(release: AbsRelease) -> None:
    """Chart capex by industry, all asset types, in CP and CVM."""
    for industry in INDUSTRIES:
        _by_measure(release, ALL_ASSETS, industry, industry)


def datacentre_imt_equipment(release: AbsRelease) -> None:
    """Chart IMT equipment capex (servers etc.), the data-centre proxy: level and growth, full history."""
    series, units = _capex(release, EQUIPMENT, DATA_CENTRE_INDUSTRY, CVM)
    _level_and_growth(
        series,
        units,
        title="CapEx: Info Media & Telecom: Equipment",
        lfooter=DATA_CENTRE_LFOOTER,
        source=release.source,
    )


def datacentre_imt_equipment_vs_buildings(release: AbsRelease) -> None:
    """Chart IMT capex split into equipment (hardware) and buildings (the data-centre shells)."""
    equipment, units = _raw(release, EQUIPMENT, DATA_CENTRE_INDUSTRY, CVM)
    buildings, building_units = _raw(release, BUILDINGS, DATA_CENTRE_INDUSTRY, CVM)
    if building_units != units:
        raise ValueError(f"IMT equipment in {units!r} but buildings in {building_units!r}")
    raw = pd.DataFrame({"Equipment (servers etc.)": equipment, "Buildings & structures": buildings}).dropna()
    frame, units = ra.recalibrate(raw, units)  # one scale for both series
    line_plot_finalise(
        frame,
        title="CapEx: Info Media & Telecom: Equipment vs Buildings",
        ylabel=f"{units}/Quarter",
        rfooter=release.source,
        lfooter=DATA_CENTRE_LFOOTER,
    )


# --- table of contents, in run order
CHARTS = (
    (headline, ()),
    (by_asset_type, ()),
    (by_industry, ()),
    (datacentre_imt_equipment, ()),
    (datacentre_imt_equipment_vs_buildings, ()),
)
