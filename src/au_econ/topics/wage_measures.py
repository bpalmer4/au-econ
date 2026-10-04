"""Three measures of Australian pay, as through-the-year growth on one axis.

The three are not the same object, and the gaps between the lines are mostly that rather
than disagreement about wages: the WPI (6345.0) prices a fixed basket of jobs; AWOTE
(6302.0, every six months) is average full-time adult ordinary-time earnings, so it moves
with the mix of jobs; and compensation of employees per hour (5206.0) is a ratio of two
national accounts aggregates covering different populations, so its largest swings are
compositional.
"""

# --- dependencies
from dataclasses import dataclass

import pandas as pd
from mgplot import line_plot_finalise, multi_start

from au_econ.charting.windows import quarterly_plot_times
from au_econ.series.gdp import get_compensation_per_hour
from au_econ.series.prices import get_wage_index

# --- module contract
RELEASE = ("wage-measures",)
TOPICS = ("wages",)
TITLE = "Wage Measures"

# --- constants
SOURCE = "ABS: 6345.0, 6302.0, 5206.0"
PAIR_SOURCE = "ABS: 6345.0, 6302.0"  # no national accounts once COE is dropped
# the measures do not share a series type: the WPI and COE are SA, AWOTE only Original
LFOOTER = "Australia. WPI and COE per hour seasonally adjusted; AWOTE original. "
PAIR_LFOOTER = "Australia. WPI seasonally adjusted; AWOTE original. "
WPI_GLOSS = "WPI = Wage Price Index"
AWOTE_GLOSS = "AWOTE = Average Weekly Ordinary Time Earnings"
COE_GLOSS = "COE = Compensation of Employees"
HEADER = f"{WPI_GLOSS}; {AWOTE_GLOSS}; {COE_GLOSS}"
PAIR_HEADER = f"{WPI_GLOSS}; {AWOTE_GLOSS}"
PAIR = ["WPI", "AWOTE"]  # the directly comparable measures: both employee pay
QUARTERS_PER_YEAR = 4


# --- data
@dataclass(frozen=True)
class WageData:
    """Through-the-year growth in the three measures, one column each, on a quarterly PeriodIndex."""

    growth: pd.DataFrame


def _through_the_year(series: pd.Series, lag: int = QUARTERS_PER_YEAR) -> pd.Series:
    """Annual growth in per cent, matching on the period index.

    Unlike a positional pct_change(), this compares each observation with the one exactly
    `lag` quarters earlier, so it is right for a series that does not occupy every quarter
    (AWOTE occupies only Q2 and Q4).
    """
    index = series.index
    if not isinstance(index, pd.PeriodIndex):
        raise TypeError(f"Expected a PeriodIndex, got {type(index).__name__}")
    year_earlier = series.copy()
    year_earlier.index = index.shift(lag)
    return ((series / year_earlier - 1) * 100).dropna()


def fetch() -> WageData:
    """Fetch the three measures and turn each into through-the-year growth."""
    wpi, _units, _stype = get_wage_index("WPI")
    awote, _units, _stype = get_wage_index("AWOTE")
    coe, _units = get_compensation_per_hour()
    levels = {"WPI": wpi, "AWOTE": awote, "COE per hour": coe}
    return WageData(growth=pd.DataFrame({name: _through_the_year(series) for name, series in levels.items()}))


# --- helpers
def _plot(growth: pd.DataFrame, *, title: str, lfooter: str, lheader: str, rfooter: str) -> None:
    multi_start(
        growth,
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title=title,
        ylabel="Per cent per year",
        y0=True,
        legend={"loc": "best", "fontsize": "small"},
        lheader=lheader,
        rfooter=rfooter,
        lfooter=lfooter,
    )


# --- charts
def three_measures(data: WageData) -> None:
    """Annual growth in the WPI, AWOTE and compensation of employees per hour."""
    _plot(
        data.growth,
        title="Wages: Annual Growth in Three Measures",
        lfooter=LFOOTER,
        lheader=HEADER,
        rfooter=SOURCE,
    )


def wpi_and_awote(data: WageData) -> None:
    """Annual growth in the two directly comparable measures, without COE per hour's compositional swings."""
    _plot(
        data.growth[PAIR],
        title="Wages: Annual Growth in the WPI and AWOTE",
        lfooter=PAIR_LFOOTER,
        lheader=PAIR_HEADER,
        rfooter=PAIR_SOURCE,
    )


# --- table of contents, in run order
CHARTS = (
    (three_measures, ()),
    (wpi_and_awote, ()),
)
