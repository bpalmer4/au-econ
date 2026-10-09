"""Government bond yields: 10- and 30-year for five markets, China against the US, and AU less US.

The five markets are the US, Japan, Germany, the UK and Australia (10-year only). France
has charts of its own: its 10- and 30-year yields, its 10-year against Germany's, and
France less Germany. Germany, France, Italy and Spain have 10-year benchmark yields from a
single source (Investing.com) from February 1994, when all four become continuous, and
France, Italy and Spain less Germany on the same basis.
Each country's line begins when its data begins. The series are not
computed identically: US and French yields are constant maturity, Japan's are benchmark
bond yields, Germany's, the UK's and China's are fitted curves, and Australia's are the
RBA's interpolated yields. Publication lags differ, so each chart's footer gives every
series' own last date.
"""

# --- dependencies
from dataclasses import dataclass
from typing import TYPE_CHECKING

import mgplot as mg
import pandas as pd
from mgplot.utilities import get_color_list

from au_econ.sources import banque_de_france, boe, bundesbank, chinabond, investing, mof, rba, yahoo

if TYPE_CHECKING:
    from collections.abc import Callable

# --- module contract
RELEASE = ("bonds",)
TOPICS = ("international",)
TITLE = "Government Bond Yields"

# --- constants
RECENT_TRADING_DAYS = -750  # roughly the last three years
plot_times = 0, RECENT_TRADING_DAYS
EARLIEST_START = "1960-01-01"  # the earliest date asked of Yahoo; each chart's start trims

# Series code per tenor and country: a Yahoo ticker (US), a MOF curve column (Japan), a
# Bundesbank series key (Germany), a BoE curve maturity in years (UK), or an RBA series
# title (Australia). Australia appears only at ten years: neither the RBA nor the AOFM
# publishes a 30-year yield.
CODES: dict[str, dict[str, str]] = {
    "10-year": {
        "United States": "^TNX",
        "Japan": "10Y",
        "Germany": "D.I.ZST.ZI.EUR.S1311.B.A604.R10XX.R.A.A._Z._Z.A",
        "United Kingdom": "10",
        "Australia": "Australian Government 10 year bond",
    },
    "30-year": {
        "United States": "^TYX",
        "Japan": "30Y",
        "Germany": "D.I.ZST.ZI.EUR.S1311.B.A604.R30XX.R.A.A._Z._Z.A",
        "United Kingdom": "30",
    },
}
SHORT_NAMES = {"United States": "US", "United Kingdom": "UK"}  # for chart titles
ABBREVIATIONS = {  # for the footer, which names every series at once
    "United States": "US",
    "Japan": "JP",
    "Germany": "DE",
    "United Kingdom": "UK",
    "Australia": "AU",
    "China": "CN",
    "France": "FR",
    "Italy": "IT",
    "Spain": "ES",
}
SOURCES = {  # each country's source, for the right footer
    "United States": "Yahoo",
    "Japan": "MOF",
    "Germany": "Bundesbank",
    "United Kingdom": "BoE",
    "Australia": "RBA: F2",
    "China": "ChinaBond",
    "France": "Banque de France",
}
TENOR_STARTS = {"10-year": "1986-01-01", "30-year": "1999-01-01"}  # Japan joins; the JGB 30-year opens
TENOR_NOTES = {
    "10-year": "",
    "30-year": (
        "US Feb 2002 to Feb 2006: no 30-year issuance, so ^TYX tracks the "
        "longest bond outstanding. UK curve reaches 30 years only from 2016"
    ),
}
CHINA_US_CODES = {"China": "10", "United States": "^TNX"}
CHINA_US_TENOR = "10-year"
CHINA_US_START = "2006-01-01"
CHINA_US_NOTE = "China: ChinaBond fitted CGB curve. US: ^TNX constant maturity"
SPREAD_TENOR = "10-year"
SPREAD_LEGS = ("Australia", "United States")
SPREAD_NOTE = (
    "RBA interpolated 10-year yield less the ^TNX constant maturity yield: "
    "the same tenor, but not identically computed"
)
FRANCE_CODES = {  # Banque de France constant maturity (TEC) series keys, by tenor
    "10-year": "FM.D.FR.EUR.FR2.BB.FRMOYTEC10.HSTA",
    "30-year": "FM.D.FR.EUR.FR2.BB.FRMOYTEC30.HSTA",
}
FRANCE_START = "2004-11-01"  # the TEC 10 series opens
FRANCE_NOTE = "Banque de France constant maturity yields. 30-year from Oct 2006"
FRANCE_GERMANY_TENOR = "10-year"
FRANCE_GERMANY_CODES = {
    "France": FRANCE_CODES[FRANCE_GERMANY_TENOR],
    "Germany": CODES[FRANCE_GERMANY_TENOR]["Germany"],
}
FRANCE_GERMANY_NOTE = "France: constant maturity. Germany: Bundesbank fitted curve"
FRANCE_GERMANY_SPREAD_NOTE = (
    "Banque de France constant maturity 10-year yield less the Bundesbank fitted-curve "
    "yield: the same tenor, but not identically computed"
)
EURO_TENOR = "10-year"
EURO_CODES = {  # Investing.com instrument IDs for 10-year benchmark yields; Germany first, the spread base
    "Germany": 23693,
    "France": 23778,
    "Italy": 23738,
    "Spain": 23806,
}
EURO_START = "1994-02-02"  # Spain opens and France resumes after a gap from May 1990: all four continuous
EURO_SOURCE = "Investing.com"
EURO_NOTE = "Benchmark bond yields, all from one source"
EURO_SPREAD_NOTE = "Each benchmark 10-year yield less Germany's, on days both traded"
RBA_CURRENT_TABLE, RBA_HISTORY_TABLE = "F2", "Z:F2-Daily-2013"  # the RBA split its daily yields in 2013


@dataclass(frozen=True)
class BondYields:
    """Daily yields (per cent): per tenor; China and US; France by tenor; France and Germany; euro benchmarks."""

    tenors: dict[str, pd.DataFrame]
    china_us: pd.DataFrame
    france: pd.DataFrame
    france_germany: pd.DataFrame
    euro: pd.DataFrame


# --- data
def _australia(title: str) -> pd.Series:
    """RBA daily yield by series title: the current table extended back by the pre-2013 one."""
    current, meta = rba.get_table(RBA_CURRENT_TABLE)
    matches = meta[meta["Title"] == title]
    if len(matches) != 1:
        raise ValueError(f"RBA {RBA_CURRENT_TABLE} holds {len(matches)} series titled {title!r}")
    series_id = str(matches["Series ID"].iloc[0])  # the two tables share IDs but not metadata layouts
    history, _ = rba.get_table(RBA_HISTORY_TABLE)
    if series_id not in history.columns:
        raise ValueError(f"RBA {RBA_HISTORY_TABLE} has no {series_id} column")
    joined = pd.concat([history[series_id].dropna(), current[series_id].dropna()])
    return joined[~joined.index.duplicated(keep="last")].sort_index()  # the current table wins on overlap


FETCHERS: dict[str, Callable[[str], pd.Series]] = {
    "United States": lambda code: yahoo.get_close(code, EARLIEST_START),
    "Japan": mof.get_jgb_yield,
    "Germany": bundesbank.get_series,
    "United Kingdom": lambda code: boe.get_gilt_yield(float(code)),
    "Australia": _australia,
    "China": chinabond.get_cgb_yield,
    "France": banque_de_france.get_series,
}


def _yield(country: str, code: str) -> pd.Series:
    """One country's yield, numeric (several sources hand back object columns, which lose end labels)."""
    series = pd.to_numeric(FETCHERS[country](code), errors="coerce").dropna()
    if series.empty:
        raise ValueError(f"No numeric observations for {country} ({code})")
    return series.rename(country)


def _report(prefix: str, frame: pd.DataFrame) -> None:
    """Print each column's span, observation count and last value."""
    for label in frame.columns:
        column = frame[label].dropna()
        print(
            f"{prefix} {label}: {column.index[0]} to {column.index[-1]}, "
            f"{len(column)} observations, last {column.iloc[-1]:.2f} per cent"
        )


def _tenor(name: str, codes: dict[str, str], start: str) -> pd.DataFrame:
    """One tenor's countries on a common daily index; gaps (holidays, late starts) left missing."""
    frame = pd.DataFrame({country: _yield(country, code) for country, code in codes.items()})
    frame = frame[frame.index >= pd.Period(start, freq="D")].dropna(how="all")
    if frame.empty:
        raise ValueError(f"No {name} observations on or after {start}")
    _report(name, frame)
    return frame


def _france() -> pd.DataFrame:
    """France's yields with tenors as columns, on a common daily index from FRANCE_START."""
    frame = pd.DataFrame({tenor: _yield("France", code) for tenor, code in FRANCE_CODES.items()})
    frame = frame[frame.index >= pd.Period(FRANCE_START, freq="D")]
    _report("France", frame)
    return frame


def _euro() -> pd.DataFrame:
    """Euro-area benchmark 10-year yields, countries as columns, on a common daily index from EURO_START."""
    frame = pd.DataFrame({country: investing.get_history(code) for country, code in EURO_CODES.items()})
    frame = frame[frame.index >= pd.Period(EURO_START, freq="D")]
    _report(EURO_TENOR, frame)
    return frame


def fetch() -> BondYields:
    """Fetch every tenor, China against the US, France, France against Germany, and the euro benchmarks."""
    tenors = {name: _tenor(name, codes, TENOR_STARTS[name]) for name, codes in CODES.items()}
    return BondYields(
        tenors=tenors,
        china_us=_tenor(CHINA_US_TENOR, CHINA_US_CODES, CHINA_US_START),
        france=_france(),
        france_germany=_tenor(FRANCE_GERMANY_TENOR, FRANCE_GERMANY_CODES, FRANCE_START),
        euro=_euro(),
    )


# --- helpers
def _join_names(names: list[str]) -> str:
    """Join names as a readable list: "a, b and c"."""
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def _title_countries(countries: list[str]) -> str:
    """Countries for a chart title, the long names shortened."""
    return _join_names([SHORT_NAMES.get(country, country) for country in countries])


def _data_to_footer(data: pd.DataFrame) -> str:
    """Every series' last observation date, grouped where they share one, most recent first."""
    ends: dict[pd.Period, list[str]] = {}
    for country in data.columns:
        last = data[country].dropna().index[-1]
        if not isinstance(last, pd.Period):
            raise TypeError(f"{country}: expected a daily PeriodIndex")
        ends.setdefault(last, []).append(ABBREVIATIONS.get(country, country))
    newest_first = sorted(ends.items(), reverse=True)
    parts = [f"{_join_names(codes)} {end.strftime('%-d-%b-%Y')}" for end, codes in newest_first]
    return f"Data to: {'; '.join(parts)}. "


def _source_footer(data: pd.DataFrame) -> str:
    """Name the publisher of every series on the chart."""
    return "; ".join(SOURCES[country] for country in data.columns)


def _yield_lines(data: pd.DataFrame, title: str, source: str, note: str) -> None:
    """Yield lines over the full history and the recent window."""
    mg.multi_start(
        data,
        function=mg.line_plot_finalise,
        starts=plot_times,
        title=title,
        ylabel="Per cent per year",
        xlabel=None,
        width=1,
        annotate=True,
        rounding=2,
        legend={"loc": "best", "fontsize": "small"},
        lfooter=_data_to_footer(data),
        rfooter=source,
        rheader=note,  # "" draws nothing
    )


def _yields_chart(name: str, data: pd.DataFrame, note: str) -> None:
    """One tenor, countries as columns, over the full history and the recent window."""
    title = f"{_title_countries(list(data.columns))}: {name} Government Bond Yields"
    _yield_lines(data, title, _source_footer(data), note)


def _spread_lines(
    spreads: pd.DataFrame, *, color: list[str], title: str, note: str, lfooter: str, rfooter: str
) -> None:
    """Spread lines over the full history and the recent window; a legend only for several spreads."""
    mg.multi_start(
        spreads,
        function=mg.line_plot_finalise,
        starts=plot_times,
        title=title,
        ylabel="Percentage points",
        xlabel=None,
        width=1,
        color=color,
        annotate=True,
        rounding=2,
        legend={"loc": "best", "fontsize": "small"} if len(spreads.columns) > 1 else False,
        y0=True,
        rheader=note,
        lfooter=lfooter,
        rfooter=rfooter,
    )


def _spread_chart(tenor: str, yields: pd.DataFrame, note: str) -> None:
    """First column's yield less the second's, on days both markets traded (no spread against a stale yield)."""
    first, second = (str(country) for country in yields.columns)
    pair = yields[[first, second]].dropna()
    if pair.empty:
        raise ValueError(f"No {tenor} days on which both {first} and {second} traded")
    legs = f"{_title_countries([first])} less {_title_countries([second])}"
    _spread_lines(
        (pair[first] - pair[second]).to_frame(),
        color=get_color_list(1),
        title=f"{legs}: {tenor} Government Bond Spread",
        note=note,
        lfooter=_data_to_footer(pair),
        rfooter=_source_footer(pair),
    )


# --- charts
def yields_10_year(data: BondYields) -> None:
    """10-year yields: US, Japan, Germany, UK and Australia."""
    _yields_chart("10-year", data.tenors["10-year"], TENOR_NOTES["10-year"])


def yields_30_year(data: BondYields) -> None:
    """30-year yields: US, Japan, Germany and UK."""
    _yields_chart("30-year", data.tenors["30-year"], TENOR_NOTES["30-year"])


def china_us(data: BondYields) -> None:
    """China against the US at ten years (China's history starts in 2006)."""
    _yields_chart(CHINA_US_TENOR, data.china_us, CHINA_US_NOTE)


def australia_us_spread(data: BondYields) -> None:
    """Australia less US 10-year yield, on days both markets traded."""
    _spread_chart(SPREAD_TENOR, data.tenors[SPREAD_TENOR][list(SPREAD_LEGS)], SPREAD_NOTE)


def france(data: BondYields) -> None:
    """France's 10- and 30-year yields."""
    _yield_lines(data.france, "France: Government Bond Yields", SOURCES["France"], FRANCE_NOTE)


def france_germany(data: BondYields) -> None:
    """France against Germany at ten years (France's history starts in 2004)."""
    _yields_chart(FRANCE_GERMANY_TENOR, data.france_germany, FRANCE_GERMANY_NOTE)


def france_germany_spread(data: BondYields) -> None:
    """France less Germany 10-year yield, on days both markets traded."""
    _spread_chart(FRANCE_GERMANY_TENOR, data.france_germany, FRANCE_GERMANY_SPREAD_NOTE)


def euro_yields(data: BondYields) -> None:
    """Germany, France, Italy and Spain benchmark 10-year yields, from one source."""
    title = f"{_title_countries(list(data.euro.columns))}: {EURO_TENOR} Government Bond Yields"
    _yield_lines(data.euro, title, EURO_SOURCE, EURO_NOTE)


def euro_spreads(data: BondYields) -> None:
    """France, Italy and Spain less Germany at ten years, each on days both markets traded."""
    base, *others = (str(country) for country in data.euro.columns)
    spreads = pd.DataFrame({country: data.euro[country] - data.euro[base] for country in others}).dropna(how="all")
    if spreads.empty:
        raise ValueError(f"No {EURO_TENOR} days on which {base} and another market both traded")
    _spread_lines(
        spreads,
        color=get_color_list(len(data.euro.columns))[1:],  # each country keeps its colour from euro_yields
        title=f"{_title_countries(others)} less {base}: {EURO_TENOR} Government Bond Spreads",
        note=EURO_SPREAD_NOTE,
        lfooter=_data_to_footer(spreads),
        rfooter=EURO_SOURCE,
    )


# --- table of contents, in run order
CHARTS = (
    (yields_10_year, ()),
    (yields_30_year, ()),
    (china_us, ()),
    (australia_us_spread, ()),
    (france, ()),
    (france_germany, ()),
    (france_germany_spread, ()),
    (euro_yields, ()),
    (euro_spreads, ()),
)
