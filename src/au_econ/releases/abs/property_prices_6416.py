"""Residential Property Price Indexes (6416.0, discontinued 2021): long-run house prices against wages and the CPI.

The house-price level splices the current 6432.0 mean dwelling price over the discontinued
6416.0 indexes (see series.housing), reaching back to 1986.
"""

# --- dependencies
import pandas as pd
from mgplot import line_plot_finalise, multi_start

from au_econ.charting.windows import quarterly_plot_times
from au_econ.series.housing import get_house_price_index
from au_econ.series.prices import get_cpi, get_wage_index

# --- module contract
RELEASE = ("6416", "rppi")
TOPICS = ("building",)
TITLE = "Residential Property Prices"

# --- constants
SOURCE = "ABS: 6302.0, 6416.0, 6432.0"
WEEKS_PER_YEAR = 365.24 / 7  # annualises weekly AWOTE
PERCENT = 100
PRE_2003_LHEADER = "Pre-2003 house price uses the established-house index (pre-2005 methodology). "
PARITY = {"y": 100, "color": "grey", "linestyle": "--", "lw": 0.75}


# --- data
def fetch() -> pd.Series:
    """Fetch the long-run house-price level once; the wage and price series are fetched per chart."""
    hpi, _units, _stype = get_house_price_index()
    return hpi


# --- helpers
def _rebased(hpi: pd.Series, other: pd.Series, labels: tuple[str, str]) -> tuple[pd.DataFrame, pd.Period]:
    """Return both series indexed to 100 at their common start, and that start."""
    base = max(hpi.index.min(), other.index.min())
    frame = pd.DataFrame({labels[0]: hpi / hpi.loc[base] * PERCENT, labels[1]: other / other.loc[base] * PERCENT})
    return frame[frame.index >= base], base


# --- charts
def hpi_vs_awote(hpi: pd.Series) -> None:
    """Chart house prices against wages (AWOTE), both 100 at their common start."""
    awote, _units, awote_stype = get_wage_index("AWOTE")
    frame, base = _rebased(hpi, awote, ("House price index", "AWOTE (wages)"))
    multi_start(
        frame,
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title=f"House prices vs wages (AWOTE): {base} = 100",
        ylabel=f"Index ({base} = 100)",
        rfooter=SOURCE,
        lfooter=f"Australia. House prices original, AWOTE {awote_stype.lower()}. "
        "House-price index spliced from ABS 6432.0 and 6416.0. ",
        lheader=PRE_2003_LHEADER,
        annotate=True,
        rounding=0,
        axhline=PARITY,
    )


def price_to_income(hpi: pd.Series) -> None:
    """Chart the mean dwelling price as a multiple of annual AWOTE (years of earnings)."""
    awote, _units, awote_stype = get_wage_index("AWOTE")
    multi_start(
        (hpi / (awote * WEEKS_PER_YEAR)).dropna(),
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title="Mean dwelling price to income (AWOTE) ratio",
        ylabel="Years of annual earnings",
        rfooter=SOURCE,
        lfooter=f"Australia. House prices original, AWOTE {awote_stype.lower()}. "
        "Mean dwelling price / annual AWOTE (full-time adult ordinary earnings). ",
        lheader=PRE_2003_LHEADER,
        annotate=True,
        rounding=1,
    )


def resi_vs_cpi(hpi: pd.Series) -> None:
    """Chart house prices against the CPI, both 100 at their common start."""
    cpi, _units, cpi_stype = get_cpi("headline_sa")
    frame, base = _rebased(hpi, cpi, ("House price index", "CPI (All groups, SA)"))
    multi_start(
        frame,
        function=line_plot_finalise,
        starts=quarterly_plot_times,
        title=f"House prices vs CPI: {base} = 100",
        ylabel=f"Index ({base} = 100)",
        rfooter="ABS: 6401.0, 6416.0, 6432.0",
        lfooter=f"Australia. House prices original, CPI {cpi_stype.lower()}. "
        "House-price index spliced from ABS 6432.0 and 6416.0. ",
        lheader=PRE_2003_LHEADER,
        annotate=True,
        rounding=0,
        axhline=PARITY,
    )


# --- table of contents, in run order
CHARTS = (
    (hpi_vs_awote, ()),
    (price_to_income, ()),
    (resi_vs_cpi, ()),
)
