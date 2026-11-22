"""RBA Index of Commodity Prices (table I2): Australia's export-weighted commodity prices, monthly from 1982.

The index is published in Australian dollars, US dollars and SDR (the RBA's headline
basis), with rural, non-rural, base metals and bulk commodities components. Bulk
commodities are measured from export prices; the spot-price variants are not used.
"""

# --- dependencies
from dataclasses import dataclass

import pandas as pd
from mgplot import line_plot_finalise, multi_start

from au_econ.charting.footers import SERIES_TYPE_NOTES
from au_econ.sources import rba

# --- module contract
RELEASE = ("rba-commodities",)
TOPICS = ("commodities", "rba")
TITLE = "Index of Commodity Prices"

# --- constants
TABLE = "I2"
SOURCE = f"RBA: {TABLE}"
DESCRIPTION = "Index of commodity prices; {item}; {currency}"
ALL_ITEMS = "All items"
RBA_DASH = "\N{EN DASH}"  # the en dash the RBA puts between a component and its sub-component
ITEMS = {  # chart label: the item as the RBA describes it
    ALL_ITEMS: "All items",
    "Rural": "Rural component",
    "Non-rural": "Non-rural component",
    "Base metals": f"Non-rural component {RBA_DASH} Base metals",
    "Bulk commodities": f"Non-rural component {RBA_DASH} Bulk commodities (based on export price movements)",
}
CURRENCIES = ("A$", "US$", "SDR")
HEADLINE_CURRENCY = "SDR"
GROWTH_CURRENCIES = ("A$", "US$")
MONTHS_PER_YEAR = 12
PERCENT = 100
RECENT_MONTHS = 121  # about ten years
plot_times = (0, -RECENT_MONTHS)


@dataclass(frozen=True)
class CommodityPrices:
    """Monthly index levels, columns (item label, currency); the index units."""

    prices: pd.DataFrame
    units: str


# --- data
def fetch() -> CommodityPrices:
    """Fetch table I2 and select each item in each currency by its RBA description."""
    data, meta = rba.get_table(TABLE)
    columns = {}
    units = set()
    for label, item in ITEMS.items():
        for currency in CURRENCIES:
            description = DESCRIPTION.format(item=item, currency=currency)
            match = meta[meta["Description"] == description]
            if len(match) != 1:
                raise ValueError(f"RBA {TABLE} holds {len(match)} series described {description!r}")
            series = pd.to_numeric(data[match.index[0]], errors="coerce").dropna().astype(float)
            if series.empty:
                raise ValueError(f"RBA {TABLE}: no data for {description!r}")
            columns[(label, currency)] = series
            units.add(str(match["Units"].iloc[0]))
    if len(units) != 1:
        raise ValueError(f"RBA {TABLE}: mixed units {units}")
    prices = pd.concat(columns, axis=1).dropna(how="all")
    print(f"RBA {TABLE} commodity prices: {prices.index[0]} to {prices.index[-1]}")
    return CommodityPrices(prices=prices, units=units.pop())


# --- helpers
def _lfooter(frame: pd.DataFrame | pd.Series) -> str:
    """Left footer: Australia, series type and the latest month."""
    last = frame.index[-1]
    if not isinstance(last, pd.Period):
        raise TypeError("Expected a monthly PeriodIndex")
    return f"Australia. {SERIES_TYPE_NOTES['Original']} Monthly, data to {last.strftime('%b %Y')}."


# --- charts
def currencies(data: CommodityPrices) -> None:
    """Chart all items in Australian dollars, US dollars and SDR: full history and the last ten years."""
    frame = data.prices.xs(ALL_ITEMS, axis=1, level=0).dropna(how="all")
    if not isinstance(frame, pd.DataFrame):
        raise TypeError(f"RBA {TABLE}: expected one {ALL_ITEMS} column per currency")
    multi_start(
        frame,
        function=line_plot_finalise,
        starts=plot_times,
        title="RBA Index of Commodity Prices: by Currency",
        ylabel=data.units,
        lfooter=_lfooter(frame),
        rfooter=SOURCE,
        annotate=True,
    )


def components(data: CommodityPrices) -> None:
    """Chart the rural, non-rural, base metals and bulk commodities components, in SDR."""
    frame = data.prices.xs(HEADLINE_CURRENCY, axis=1, level=1).drop(columns=ALL_ITEMS).dropna(how="all")
    if not isinstance(frame, pd.DataFrame):
        raise TypeError(f"RBA {TABLE}: expected one {HEADLINE_CURRENCY} column per component")
    multi_start(
        frame,
        function=line_plot_finalise,
        starts=plot_times,
        title=f"RBA Index of Commodity Prices: Components ({HEADLINE_CURRENCY})",
        ylabel=data.units,
        lfooter=_lfooter(frame),
        rfooter=SOURCE,
        annotate=True,
    )


def annual_growth(data: CommodityPrices) -> None:
    """Chart year-on-year growth in all items, Australian dollars against US dollars."""
    levels = data.prices.xs(ALL_ITEMS, axis=1, level=0)[list(GROWTH_CURRENCIES)]
    growth = (levels.pct_change(MONTHS_PER_YEAR, fill_method=None) * PERCENT).dropna(how="all")
    if not isinstance(growth, pd.DataFrame):
        raise TypeError(f"RBA {TABLE}: expected one {ALL_ITEMS} column per currency")
    multi_start(
        growth,
        function=line_plot_finalise,
        starts=plot_times,
        title="RBA Index of Commodity Prices: Annual Growth",
        ylabel="Per cent change on a year earlier",
        y0=True,
        lfooter=_lfooter(growth),
        rfooter=SOURCE,
        annotate=True,
    )


# --- table of contents, in run order
CHARTS = (
    (currencies, ()),
    (components, ()),
    (annual_growth, ()),
)
