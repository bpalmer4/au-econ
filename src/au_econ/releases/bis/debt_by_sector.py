"""Debt by sector (BIS): household, corporate and government debt to GDP, and the household debt service ratio.

Australia against other advanced economies, with real house prices: the asset most household debt funds.
Real house price growth is also set against population growth (IMF World Economic Outlook) for every
country whose BIS series reaches back far enough.
"""

# --- dependencies
from dataclasses import dataclass

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from adjustText import adjust_text
from mgplot import finalise_plot, line_plot_finalise
from mgplot.utilities import get_color_list

from au_econ.charting.footers import data_to
from au_econ.sources import bis, imf

# --- module contract
RELEASE = ("bis-debt",)
TOPICS = ("international",)
TITLE = "Debt by Sector"

# --- constants
SOURCE = "BIS: WS_TC"
SERVICE_SOURCE = "BIS: WS_DSR"
PRICES_SOURCE = "BIS: WS_SPP"
PRICES_LFOOTER = "Residential property prices, deflated by consumer prices. "
PERCENT = 100
COUNTRIES = {  # country label: BIS code
    "Australia": "AU",
    "Canada": "CA",
    "New Zealand": "NZ",
    "United Kingdom": "GB",
    "United States": "US",
    "Japan": "JP",
}
NO_SERVICE_RATIO = "New Zealand"  # the BIS publishes no household debt service ratio for New Zealand
SERVICE_COUNTRIES = {label: code for label, code in COUNTRIES.items() if label != NO_SERVICE_RATIO}
START_COUNTRY = "Australia"  # the chart starts where this country's series does
DEBT = {  # chart title: (BIS borrower, BIS valuation, lfooter)
    "Household Debt": (
        "households",
        "market",
        (
            "Credit to households and non-profit institutions serving households, from all sectors. "
            "Market value, adjusted for breaks. "
        ),
    ),
    "Non-financial Corporate Debt": (
        "non-financial corporations",
        "market",
        "Credit to non-financial corporations, from all sectors. Market value, adjusted for breaks. ",
    ),
    "Government Debt": (
        "general government",
        "nominal",  # the BIS has no market value series for New Zealand government debt
        "Credit to general government, from all sectors. Nominal value, adjusted for breaks. ",
    ),
}
SERVICE_LFOOTER = (
    "Estimated interest and principal repayments by all households, "
    "as a share of their disposable income plus interest paid. "
)

# house prices against population: every country with a BIS real house price index from 2000
COMPARISON = {  # country label: (BIS code, IMF code)
    "Australia": ("AU", "AUS"),
    "Austria": ("AT", "AUT"),
    "Belgium": ("BE", "BEL"),
    "Bulgaria": ("BG", "BGR"),
    "Canada": ("CA", "CAN"),
    "Colombia": ("CO", "COL"),
    "Croatia": ("HR", "HRV"),
    "Denmark": ("DK", "DNK"),
    "Finland": ("FI", "FIN"),
    "France": ("FR", "FRA"),
    "Germany": ("DE", "DEU"),
    "Greece": ("GR", "GRC"),
    "Hong Kong": ("HK", "HKG"),
    "Hungary": ("HU", "HUN"),
    "Iceland": ("IS", "ISL"),
    "Ireland": ("IE", "IRL"),
    "Israel": ("IL", "ISR"),
    "Italy": ("IT", "ITA"),
    "Japan": ("JP", "JPN"),
    "Korea": ("KR", "KOR"),
    "Lithuania": ("LT", "LTU"),
    "Malaysia": ("MY", "MYS"),
    "Netherlands": ("NL", "NLD"),
    "New Zealand": ("NZ", "NZL"),
    "North Macedonia": ("MK", "MKD"),
    "Norway": ("NO", "NOR"),
    "Peru": ("PE", "PER"),
    "Portugal": ("PT", "PRT"),
    "Serbia": ("RS", "SRB"),
    "Singapore": ("SG", "SGP"),
    "South Africa": ("ZA", "ZAF"),
    "Spain": ("ES", "ESP"),
    "Sweden": ("SE", "SWE"),
    "Switzerland": ("CH", "CHE"),
    "Thailand": ("TH", "THA"),
    "United Kingdom": ("GB", "GBR"),
    "United States": ("US", "USA"),
}
POPULATION = "LP"  # IMF WEO population, millions
POPULATION_SOURCE = "BIS: WS_SPP; IMF: WEO"
START_YEARS = (1990, 2000)
QUARTERS_PER_YEAR = 4
FALLING = "tab:red"  # real house prices lower than at the start
POINT_SIZE = 40


# --- data
@dataclass(frozen=True)
class DebtBySector:
    """Quarterly, one column per country label.

    debt maps each DEBT chart title to credit as a per cent of GDP; service is the household
    debt service ratio, per cent of income; house_prices is the real residential property price
    index. comparison_prices is that index for every COMPARISON country the BIS covers, and
    population the IMF's annual population (millions) for every COMPARISON country it covers.
    """

    debt: dict[str, pd.DataFrame]
    service: pd.DataFrame
    house_prices: pd.DataFrame
    comparison_prices: pd.DataFrame
    population: pd.DataFrame


def _by_label(codes: pd.DataFrame, countries: dict[str, str], what: str) -> pd.DataFrame:
    """Relabel BIS country-code columns as country names; raise if any country has no data."""
    missing = [label for label, code in countries.items() if code not in codes or codes[code].dropna().empty]
    if missing:
        raise ValueError(f"BIS {what}: no data for {', '.join(missing)}")
    return pd.DataFrame({label: codes[code] for label, code in countries.items()})


def fetch() -> DebtBySector:
    """Fetch each sector's debt to GDP and the debt service ratio, one request each; check every country."""
    debt = {
        title: _by_label(bis.get_credit_to_gdp(borrower, valuation, COUNTRIES.values()), COUNTRIES, title)
        for title, (borrower, valuation, _lfooter) in DEBT.items()
    }
    service = bis.get_household_debt_service_ratio(SERVICE_COUNTRIES.values())
    house_prices = bis.get_property_price_indexes("real", [code for code, _imf in COMPARISON.values()])
    weo = imf.get_weo(POPULATION)
    comparison_prices = pd.DataFrame(
        {label: house_prices[code] for label, (code, _imf) in COMPARISON.items() if code in house_prices}
    )
    population = pd.DataFrame({label: weo[code] for label, (_bis, code) in COMPARISON.items() if code in weo})
    for what, found in (("BIS real property prices", comparison_prices), ("IMF population", population)):
        missing = sorted(set(COMPARISON) - set(found.columns))
        if missing:
            print(f"{what}: none for {', '.join(missing)}")
    if comparison_prices.empty or population.empty:
        raise ValueError("No countries with both real house prices and population")
    return DebtBySector(
        debt=debt,
        service=_by_label(service, SERVICE_COUNTRIES, "debt service ratio"),
        house_prices=_by_label(house_prices, COUNTRIES, "real property prices"),
        comparison_prices=comparison_prices,
        population=population,
    )


# --- charts
def _country_chart(data: pd.DataFrame, title: str, ylabel: str, lfooter: str, rfooter: str) -> None:
    """One line per country, the latest values annotated, with the frequency and last quarter in the header."""
    line_plot_finalise(
        data,
        title=title,
        lheader=f"Quarterly. {data_to(data)}",
        ylabel=ylabel,
        annotate=True,
        rounding=1,
        legend=True,
        lfooter=lfooter,
        rfooter=rfooter,
    )


def debt_to_gdp(data: DebtBySector) -> None:
    """Household, corporate and government debt to GDP by country, each from Australia's first quarter."""
    for title, (_borrower, _valuation, lfooter) in DEBT.items():
        debt = data.debt[title]
        start = debt[START_COUNTRY].first_valid_index()
        _country_chart(debt.loc[start:], f"{title}: Per Cent of GDP", "Per cent of GDP", lfooter, SOURCE)


def household_debt_service(data: DebtBySector) -> None:
    """Household debt service ratio by country: repayments as a share of income."""
    _country_chart(
        data.service,
        "Household Debt Service Ratio: Per Cent of Income",
        "Per cent of income",
        SERVICE_LFOOTER,
        SERVICE_SOURCE,
    )


def house_prices(data: DebtBySector) -> None:
    """Real house prices by country, each rebased to 100 at the first quarter all the countries share."""
    shared = data.house_prices.dropna()
    if shared.empty:
        raise ValueError("BIS real property prices: no quarter has data for every country")
    start = shared.index[0]
    if not isinstance(start, pd.Period):
        raise TypeError(f"BIS real property prices: expected a quarterly period, got {start!r}")
    prices = data.house_prices.loc[start:]
    _country_chart(
        prices / prices.iloc[0] * PERCENT,
        "Real House Prices",
        f"Index ({start} = 100)",
        PRICES_LFOOTER,
        PRICES_SOURCE,
    )


def house_prices_vs_population(data: DebtBySector) -> None:
    """Real house price growth against population growth, by country, from each of START_YEARS to the latest year.

    Each measure compares annual averages: the start year (all four quarters needed) and each
    country's latest year of house prices, which may be part of a year. The latest year's
    population can be an IMF projection.
    """
    prices = data.comparison_prices
    index = prices.index
    if not isinstance(index, pd.PeriodIndex):
        raise TypeError(f"BIS real property prices: expected a quarterly PeriodIndex, got {type(index).__name__}")
    end = int(index.year.max())
    yearly = prices.groupby(index.year)
    average, quarters = yearly.mean(), yearly.count()
    years = quarters.index.to_numpy(dtype=int)
    population = data.population.rename(index=lambda period: period.year)
    rising, falling = get_color_list(1)[0], FALLING
    for start in START_YEARS:
        # countries with a full start year and population at both ends, each to its own latest
        # year of house prices; one that ends before the others says so in its label
        rows: dict[str, dict[str, float]] = {}
        for country in prices.columns:
            counts = quarters[country].to_numpy(dtype=int)
            last = int(years[counts > 0].max())
            if counts[years == start].sum() != QUARTERS_PER_YEAR or country not in population:
                continue
            people = population[country].reindex([start, last]).to_numpy(dtype=float)
            if np.isnan(people).any():
                continue
            levels = average[country].to_numpy(dtype=float)
            label = country if last == end else f"{country} (to {last})"
            rows[label] = {
                "population": (people[1] / people[0] - 1) * PERCENT,
                "prices": (levels[years == last][0] / levels[years == start][0] - 1) * PERCENT,
            }
        points = pd.DataFrame(rows).T.sort_values("prices")
        print(f"\nReal house prices and population, {start}-{end}: {len(points)} countries")
        print(points.round(1).to_string())

        _fig, ax = plt.subplots()
        ax.scatter(
            points["population"],
            points["prices"],
            s=POINT_SIZE,
            color=[falling if value < 0 else rising for value in points["prices"]],
            zorder=3,
        )
        # ordinary least squares line through the countries, with its R²
        x_values, y_values = points["population"].to_numpy(), points["prices"].to_numpy()
        slope, intercept = np.polyfit(x_values, y_values, 1)
        residuals = y_values - (slope * x_values + intercept)
        r_squared = 1 - (residuals**2).sum() / ((y_values - y_values.mean()) ** 2).sum()
        line_x = np.array([x_values.min(), x_values.max()])
        ax.plot(
            line_x,
            slope * line_x + intercept,
            color="grey",
            linestyle="--",
            linewidth=1,
            zorder=2,
            label=f"OLS fit: R² = {r_squared:.2f}, slope = {slope:.1f}",
        )
        labels = [
            ax.text(
                x,
                y,
                str(name),
                fontsize="xx-small",
                fontweight="bold" if str(name).startswith(START_COUNTRY) else "normal",
            )
            for name, x, y in zip(points.index, points["population"], points["prices"], strict=True)
        ]
        # move the labels off each other and the markers, with a leader line where one moves far
        adjust_text(labels, ax=ax, arrowprops={"arrowstyle": "-", "color": "grey", "linewidth": 0.5})
        finalise_plot(
            ax,
            title=f"Real House Price Growth vs Population Growth: {start}-{end}",
            xlabel=f"Population growth {start}-{end} (%)",
            ylabel=f"Real house price growth {start}-{end} (%)",
            lheader=f"{len(points)} countries with BIS real house prices from {start}; R² = {r_squared:.2f}",
            legend={"loc": "lower right", "fontsize": "x-small"},
            axhline={"y": 0, "color": "grey", "linewidth": 0.75},
            axvline={"x": 0, "color": "grey", "linewidth": 0.75},
            lfooter=f"Real house prices. Annual averages; {end} to date and population projected. ",
            rfooter=POPULATION_SOURCE,
        )


# --- table of contents, in run order
CHARTS = (
    (debt_to_gdp, ()),
    (household_debt_service, ()),
    (house_prices, ()),
    (house_prices_vs_population, ()),
)
