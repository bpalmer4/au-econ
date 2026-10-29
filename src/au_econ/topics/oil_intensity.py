"""Oil use per unit of real GDP in Australia: tonnes of oil per $1,000 of GDP, by calendar year.

Oil consumption (million tonnes, from 1965) is the Energy Institute's Statistical Review of
World Energy, formerly BP's, read through Our World in Data. Real GDP is the ABS chain
volume measure (5206.0), original quarters summed to calendar years; only complete years
are kept.
"""

# --- dependencies
from dataclasses import dataclass

import pandas as pd
from mgplot import line_plot_finalise

from au_econ.charting.footers import SERIES_TYPE_NOTES, data_to
from au_econ.series.gdp import get_gdp
from au_econ.sources import owid

# --- module contract
RELEASE = ("oil-intensity",)
TOPICS = ("energy",)
TITLE = "Oil Intensity"

# --- constants
COUNTRY = "Australia"
OIL_COLUMN = "oil_consumption_mt"  # million tonnes
GDP_UNITS = "$ Millions"
QUARTERS_PER_YEAR = 4
# tonnes per $1,000 = (Mt x 1e6 tonnes) / ($m x 1e3 thousands)
TONNES_PER_THOUSAND = 1_000
SOURCE = "ABS: 5206.0; Energy Institute Statistical Review via OWID"


# --- data
@dataclass(frozen=True)
class OilIntensity:
    """Tonnes of oil per $1,000 of real GDP, annual."""

    intensity: pd.Series


def _annual_gdp() -> pd.Series:
    """Real GDP ($ millions, original) summed over each complete calendar year."""
    quarterly, units = get_gdp("CVM", "O")
    if units != GDP_UNITS:
        raise ValueError(f"Expected GDP in {GDP_UNITS}, got {units}")
    quarterly = quarterly.dropna()
    years = quarterly.groupby(pd.PeriodIndex(quarterly.index).asfreq("Y-DEC"))
    return years.sum()[years.count() == QUARTERS_PER_YEAR]


def fetch() -> OilIntensity:
    """Fetch oil consumption and real GDP and divide one by the other."""
    oil = owid.get_statistical_review(COUNTRY, OIL_COLUMN)
    intensity = (oil * TONNES_PER_THOUSAND / _annual_gdp()).dropna()
    if intensity.empty:
        raise ValueError("Oil consumption and real GDP share no years")
    latest = intensity.iloc[-1]
    print(f"Oil intensity: {intensity.index[0]} to {intensity.index[-1]}, latest {latest:.4f} t/$1,000")
    return OilIntensity(intensity=intensity)


# --- charts
def oil_intensity(data: OilIntensity) -> None:
    """Tonnes of oil used per $1,000 of real GDP."""
    line_plot_finalise(
        data.intensity.rename("Australia"),
        title="Oil Use per Unit of Real GDP",
        ylabel="Tonnes per $1,000 GDP",
        annotate=True,
        rounding=3,
        legend=False,
        lfooter=(
            f"Australia. {SERIES_TYPE_NOTES['Original']} Chain volume measures, "
            f"calendar years. {data_to(data.intensity)}"
        ),
        rfooter=SOURCE,
    )


# --- table of contents, in run order
CHARTS = ((oil_intensity, ()),)
