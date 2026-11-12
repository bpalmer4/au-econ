"""Excess money growth and inflation since COVID: broad money growth less real GDP growth, against CPI inflation.

One point per economy, each growth rate annualised December to December. Three charts:
the whole of 2019 to 2025; money growth to 2021 against inflation after it (money leads);
and money growth after 2021 against inflation to it (inflation leads, the placebo).
Broad money is OECD M3 (the monetary aggregates dataflow), real GDP is the OECD quarterly
national accounts, consumer prices are the BIS long CPI series. Costa Rica has M3 and GDP
but no BIS CPI, so it is left out. China is in the printed table but not on the charts or
in the fits (EXCLUDED gives the reason).

Doubts: these charts may show nothing more than you would expect anyway. By the quantity
identity, inflation = excess money growth + velocity growth, so a fit of one on the other
measures how far velocity varied across countries, not whether money drove prices. Broad
money is mostly deposits, which grow with nominal incomes, so higher inflation produces
higher money growth by itself.

The fits are carried by Turkey, the one high-inflation economy (excess money about 43% a
year, inflation about 41%). With it, 2019-2025 gives slope 0.95 and R² 0.97; without it,
slope 0.61 and R² 0.63. Money leading (money to 2021, inflation after) falls from R² 0.71
to 0.18 without Turkey; the placebo (inflation to 2021, money after) from 0.91 to 0.41,
so among ordinary-inflation economies inflation predicts later money growth better than
money predicts later inflation. Among advanced economies alone money leads, but weakly
(slope about 0.14). The six-year chart looks cleaner than either half because velocity's
collapse in 2020-21 and its rebound after net out.

This matches the literature: Borio, Hofmann and Zakrajšek (BIS, 2023), across 32
countries in ten-year averages, find excess money growth and inflation near one-for-one
when inflation is high and weakly related otherwise; McCracken and Fu (St. Louis Fed,
"Does Growth in the Money Supply Predict U.S. Inflation? Yes, but ...", November 2026)
find the same in US data, with velocity offsetting money growth at ordinary rates
(M2 velocity growth swung from about -23% in 2020 to +11% by 2023). Money growth is a
signal when it moves far outside its own range, not an everyday predictor.
"""

# --- dependencies
from dataclasses import dataclass

import numpy as np
import pandas as pd
from adjustText import adjust_text
from mgplot import finalise_plot, scatter_plot
from mgplot.utilities import get_color_list

from au_econ.sources import bis, oecd

# --- module contract
RELEASE = ("money-inflation",)
TOPICS = ("international", "prices")
TITLE = "Money Growth and Inflation"

# --- constants
START = pd.Period("2019-12", freq="M")
MIDDLE = pd.Period("2021-12", freq="M")  # the end of the COVID money surge
END = pd.Period("2025-12", freq="M")
WINDOWS = ((START, END), (START, MIDDLE), (MIDDLE, END))  # each a December-to-December span
PERCENT = 100

ECONOMIES = {  # label: (OECD money area, OECD GDP area, BIS area)
    "Australia": ("AUS", "AUS", "AU"),
    "Canada": ("CAN", "CAN", "CA"),
    "Switzerland": ("CHE", "CHE", "CH"),
    "Chile": ("CHL", "CHL", "CL"),
    "Colombia": ("COL", "COL", "CO"),
    "Czechia": ("CZE", "CZE", "CZ"),
    "Denmark": ("DNK", "DNK", "DK"),
    "Euro area": ("EA20", "EA", "XM"),
    "UK": ("GBR", "GBR", "GB"),
    "Hungary": ("HUN", "HUN", "HU"),
    "Iceland": ("ISL", "ISL", "IS"),
    "Israel": ("ISR", "ISR", "IL"),
    "Japan": ("JPN", "JPN", "JP"),
    "Korea": ("KOR", "KOR", "KR"),
    "Mexico": ("MEX", "MEX", "MX"),
    "Norway": ("NOR", "NOR", "NO"),
    "New Zealand": ("NZL", "NZL", "NZ"),
    "Poland": ("POL", "POL", "PL"),
    "Sweden": ("SWE", "SWE", "SE"),
    "Turkey": ("TUR", "TUR", "TR"),
    "US": ("USA", "USA", "US"),
    "Brazil": ("BRA", "BRA", "BR"),
    "Bulgaria": ("BGR", "BGR", "BG"),
    "China": ("CHN", "CHN", "CN"),
    "Indonesia": ("IDN", "IDN", "ID"),
    "India": ("IND", "IND", "IN"),
    "Romania": ("ROU", "ROU", "RO"),
    "South Africa": ("ZAF", "ZAF", "ZA"),
}
NON_MEMBERS = ("Brazil", "Bulgaria", "China", "Indonesia", "India", "Romania", "South Africa")  # of the OECD
EXCLUDED = {  # economy: why it is in the table but left off the chart and the fit
    "China": "administered prices and capital controls; money does not reach the CPI the same way",
}
# M3 index, monthly; key dimensions:
# REF_AREA.FREQ.MEASURE.UNIT_MEASURE.ACTIVITY.ADJUSTMENT.TRANSFORMATION.TIME_HORIZ.METHODOLOGY
MONEY_FLOW = "OECD.SDD.STES,DSD_STES@DF_MONAGG,"
MONEY_KEY = "{areas}.M.MABM.IX._Z.{adjustment}._Z._Z.N"
ADJUSTMENTS = ("N", "Y")  # original preferred; seasonally adjusted where a country publishes no original (Czechia)
# real GDP, seasonally adjusted, chain-linked volumes, growth on a year earlier; expenditure table
GDP_FLOW = "OECD.SDD.NAD,DSD_NAMAIN1@DF_QNA,"
GDP_KEY = "Q.Y.{areas}...B1GQ.....L.GY.T0102"

XLABEL = "Broad money (M3) growth less real GDP growth {window}, % a year"
YLABEL = "CPI inflation {window}, % a year"
LFOOTER = (
    "Annualised Dec to Dec (GDP Q4 to Q4). M3, CPI orig (Czechia M3 seas adj); GDP seas adj. "
    f"Excluded: {', '.join(EXCLUDED)}. "
)
SOURCE = "BIS: WS_LONG_CPI; OECD: MEI, QNA"
LABEL_SIZE = "xx-small"


@dataclass(frozen=True)
class MoneyInflation:
    """Annualised growth per economy (per cent a year), columns (window, measure).

    window is "2019-2025" etc.; measure is money, gdp, excess money or inflation.
    """

    growth: pd.DataFrame


# --- data
def fetch() -> MoneyInflation:
    """Return each economy's annualised M3, real GDP and CPI growth over each of the WINDOWS."""
    dates = sorted({date for window in WINDOWS for date in window})
    # broad money: M3 index at each date, original where published
    money_areas = "+".join(money for money, _, _ in ECONOMIES.values())
    money: pd.DataFrame | None = None
    for adjustment in ADJUSTMENTS:
        key = MONEY_KEY.format(areas=money_areas, adjustment=adjustment)
        money = oecd.combine(money, oecd.get_table(MONEY_FLOW, key, str(START)))
    if money is None:
        raise ValueError("OECD M3: no data")
    money_at = money.reindex([str(date) for date in dates])

    # real GDP: compound the Q4 year-on-year growth rates into a Q4 level path from 2019Q4 = 1
    gdp_areas = "+".join(gdp for _, gdp, _ in ECONOMIES.values())
    gdp_growth = oecd.get_table(GDP_FLOW, GDP_KEY.format(areas=gdp_areas), f"{START.year + 1}-Q4")
    fourth_quarters = gdp_growth.reindex([f"{year}-Q4" for year in range(START.year + 1, END.year + 1)])

    # consumer prices at each date
    prices = bis.get_consumer_prices([area for _, _, area in ECONOMIES.values()], str(START))
    prices_at = prices.reindex(pd.PeriodIndex(dates)).set_axis([str(date) for date in dates])

    rows: dict[str, dict[tuple[str, str], float]] = {}
    for label, (money_area, gdp_area, price_area) in ECONOMIES.items():
        money_levels = money_at.get(money_area, pd.Series(dtype=float))
        gdp_years = fourth_quarters.get(gdp_area, pd.Series(dtype=float))
        price_levels = prices_at.get(price_area, pd.Series(dtype=float))
        if money_levels.isna().any() or gdp_years.isna().any() or price_levels.isna().any():
            raise ValueError(f"{label}: missing M3, GDP or CPI between {START} and {END}")
        gdp_levels = dict(
            zip(
                range(START.year, END.year + 1),
                np.cumprod(np.concatenate([[1.0], 1 + gdp_years.to_numpy(dtype=float) / PERCENT])),
                strict=True,
            )
        )
        rows[label] = {}
        for start, end in WINDOWS:
            years = end.year - start.year
            window = f"{start.year}-{end.year}"
            ratios = {
                "money": money_levels[str(end)] / money_levels[str(start)],
                "gdp": gdp_levels[end.year] / gdp_levels[start.year],
                "inflation": price_levels[str(end)] / price_levels[str(start)],
            }
            growth = {measure: (ratio ** (1 / years) - 1) * PERCENT for measure, ratio in ratios.items()}
            rows[label] |= {(window, measure): value for measure, value in growth.items()}
            rows[label][(window, "excess money")] = growth["money"] - growth["gdp"]
    table = pd.DataFrame(rows).T
    for start, end in WINDOWS:
        window = f"{start.year}-{end.year}"
        print(f"\nAnnualised growth, {start} to {end} (% a year): {len(table)} economies")
        measures = table[window]
        if not isinstance(measures, pd.DataFrame):
            raise TypeError(f"expected a table of measures for {window}")
        print(measures.sort_values("excess money").round(2).to_string())
    return MoneyInflation(growth=table)


# --- charts
def _scatter(data: MoneyInflation, money_window: str, price_window: str, title: str) -> None:
    """Scatter inflation in price_window against excess money growth in money_window, with an OLS line."""
    points = pd.DataFrame(
        {
            "excess money": data.growth[(money_window, "excess money")],
            "inflation": data.growth[(price_window, "inflation")],
        }
    ).drop(list(EXCLUDED))
    x_values, y_values = points["excess money"].to_numpy(), points["inflation"].to_numpy()
    slope, intercept = np.polyfit(x_values, y_values, 1)
    residuals = y_values - (slope * x_values + intercept)
    r_squared = 1 - (residuals**2).sum() / ((y_values - y_values.mean()) ** 2).sum()
    print(f"{title}: inflation = {intercept:.2f} + {slope:.2f} x excess money; R² = {r_squared:.2f}")

    # every economy with the fit line, then the non-members redrawn over them in a second colour
    member_colour, other_colour = get_color_list(2)
    fit_label = f"inflation = {intercept:.2f} + {slope:.2f} × excess money; R² = {r_squared:.2f}"
    ax = scatter_plot(
        points,
        color=member_colour,
        alpha=1.0,
        label="OECD members and euro area",
        fit={"color": "grey", "ls": "--", "label": fit_label},
    )
    scatter_plot(
        points.loc[points.index.intersection(list(NON_MEMBERS))],
        ax=ax,
        color=other_colour,
        alpha=1.0,
        label="Other economies",
    )
    labels = [
        ax.text(x, y, str(name), fontsize=LABEL_SIZE)
        for name, x, y in zip(points.index, x_values, y_values, strict=True)
    ]
    adjust_text(labels, ax=ax, arrowprops={"arrowstyle": "-", "color": "grey", "linewidth": 0.5})
    finalise_plot(
        ax,
        title=title,
        xlabel=XLABEL.format(window=money_window),
        ylabel=YLABEL.format(window=price_window),
        legend={"loc": "upper left", "fontsize": "x-small"},
        lfooter=LFOOTER,
        rfooter=SOURCE,
    )


def money_and_inflation(data: MoneyInflation) -> None:
    """Excess money growth against inflation over the same span, December 2019 to December 2025."""
    window = f"{START.year}-{END.year}"
    _scatter(data, window, window, f"Excess Money Growth vs Inflation: {window}")


def money_leads(data: MoneyInflation) -> None:
    """Excess money growth to December 2021 against inflation after it."""
    money_window, price_window = f"{START.year}-{MIDDLE.year}", f"{MIDDLE.year}-{END.year}"
    _scatter(data, money_window, price_window, f"Excess Money {money_window} vs Inflation {price_window}")


def inflation_leads(data: MoneyInflation) -> None:
    """Excess money growth after December 2021 against inflation to it: the placebo for money_leads."""
    money_window, price_window = f"{MIDDLE.year}-{END.year}", f"{START.year}-{MIDDLE.year}"
    _scatter(data, money_window, price_window, f"Excess Money {money_window} vs Inflation {price_window}")


# --- table of contents, in run order
CHARTS = ((money_and_inflation, ()), (money_leads, ()), (inflation_leads, ()))
