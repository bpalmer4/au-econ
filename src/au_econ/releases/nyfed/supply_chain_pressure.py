"""Global Supply Chain Pressure Index (NY Fed): the full history, and the recent window."""

# --- dependencies
import pandas as pd
from mgplot import line_plot_finalise, multi_start

from au_econ.charting.footers import data_to
from au_econ.sources import nyfed

# --- module contract
RELEASE = ("gscpi",)
TOPICS = ("international", "prices")
TITLE = "Global Supply Chain Pressure Index"

# --- constants
SOURCE = "NY Fed"
RECENT_START = pd.Period("2019-01", freq="M")  # the COVID spike, its unwind, and since
YLABEL = "Std devs from average"


# --- data
def fetch() -> pd.Series:
    """Fetch the monthly GSCPI."""
    gscpi = nyfed.get_gscpi()
    print(f"Latest GSCPI: {gscpi.iloc[-1]:.2f} ({gscpi.index[-1]})")
    return gscpi


# --- charts
def supply_chain_pressure(gscpi: pd.Series) -> None:
    """Plot the GSCPI over its full history, and from RECENT_START."""
    multi_start(
        gscpi,
        function=line_plot_finalise,
        starts=(0, RECENT_START),
        title=TITLE,
        ylabel=YLABEL,
        xlabel=None,
        y0=True,
        annotate=True,
        rounding=2,
        lfooter=f"Global. Monthly. Zero is the long-run average. {data_to(gscpi)}",
        rfooter=SOURCE,
    )


# --- table of contents, in run order
CHARTS = ((supply_chain_pressure, ()),)
