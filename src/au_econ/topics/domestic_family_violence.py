"""Domestic and family violence in Australia: deaths, homicides, hospitalisations and police-recorded offences.

Working hypothesis: police-recorded incidence has risen substantially, while hard outcomes
(deaths, homicides) have not. Sources: ABS Causes of Death (3303.0) for assault deaths; the
AIHW Family, domestic and sexual violence workbook for AIC homicide monitoring (NHMP),
hospitalisations (NHMD) and ABS Recorded Crime - Victims (4510.0); and ERP (3101.0) for rates.
"""

# --- dependencies
from dataclasses import dataclass

import mgplot as mg
import numpy as np
import pandas as pd
import readabs as ra

from au_econ.series.population import get_erp
from au_econ.sources.aihw import get_fdsv_sheet

# --- module contract
RELEASE = ("dfv",)
TOPICS = ("families",)
TITLE = "Domestic and Family Violence"

# --- constants
COD_URL = "https://www.abs.gov.au/statistics/health/causes-death/causes-death-australia/latest-release"
COD_WORKBOOK, COD_SHEET = "Underlying causes of death (Australia)", "Table 1.2"
ASSAULT_ROW = "Assault (X85-Y09)"
SEXES = ("Males", "Females", "Persons")
SOURCE_DEATHS = "ABS: 3303.0"
SOURCE_NHMP = "AIC: NHMP; AIHW"
SOURCE_HOSP = "AIHW: NHMD"
SOURCE_POLICE = "ABS: 4510.0"
LFOOTER = "Australia. "
FDV_NOTE = "FDV = Family/Domestic Violence. "
TREND_NOTE = "Dashed lines = OLS linear trend."
DEATHS_NOTE = "ICD-10 X85-Y09. Underlying cause of death."
SEX_COLOURS = ["cornflowerblue", "hotpink"]
INDEX_COLOURS = ["black", "darkred", "darkorange", "navy", "steelblue"]
INDEX_STYLES = ["-", "-", "-", "--", "--"]
PER_100K = 100_000
JUNE_QUARTER = 2
BASE_YEAR = 2019
INDEX_START, INDEX_END = 2010, 2025
YEAR_HEADER_ROW, SEX_HEADER_ROW = 3, 4  # in Causes of Death table 1.2
NHMP_HEADER, NHMD_HEADER, RCV1_HEADER, RCV6_HEADER = 8, 14, 12, 7
RCV_RATE = "Victimisation rate (number per 100,000)"
NHMD_RATE_KEY = "per 100,000 population"


# --- data
@dataclass(frozen=True)
class ViolenceData:
    """The series behind the charts, each on an annual PeriodIndex."""

    assault: pd.DataFrame  # assault deaths, Males / Females / Persons
    population: pd.Series  # mid-year (June) ERP
    nhmp: pd.DataFrame  # NHMP 2: domestic homicide victims
    nhmd: pd.DataFrame  # NHMD 1: FDV hospitalisations, all ages and perpetrators
    rcv1: pd.DataFrame  # RCV 1: FDV-flagged recorded crime victims
    rcv6: pd.DataFrame  # RCV 6: all police-recorded sexual assault


def _assault_deaths() -> pd.DataFrame:
    """Assault deaths by year and sex, from Causes of Death table 1.2 (any release year)."""
    tables = ra.grab_abs_url(url=COD_URL, verbose=False)
    suffix = f"---{COD_SHEET}"
    candidates = [k for k in tables if COD_WORKBOOK in k and k.endswith(suffix)]
    if len(candidates) != 1:
        raise KeyError(f"Expected one sheet matching {COD_WORKBOOK!r} + {COD_SHEET!r}, found {candidates}")
    table = tables[candidates[0]]
    years = pd.Series(table.iloc[YEAR_HEADER_ROW].tolist()).ffill()  # merged year headers
    sexes = table.iloc[SEX_HEADER_ROW].tolist()
    matches = table.iloc[:, 0].astype(str).str.strip() == ASSAULT_ROW
    if not matches.any():
        raise KeyError(f"Row not found: {ASSAULT_ROW!r}")
    row = table[matches].iloc[0]
    frame = (
        pd.DataFrame(
            {sex: {int(years.iloc[c]): row.iloc[c] for c, s in enumerate(sexes) if s == sex} for sex in SEXES}
        )
        .astype(float)
        .sort_index()
    )
    frame.index = pd.PeriodIndex(frame.index.astype(int), freq="Y")
    return frame


def _mid_year_population() -> pd.Series:
    """Australian ERP at the June quarter, indexed by year."""
    erp, _units = get_erp()
    index = erp.index
    if not isinstance(index, pd.PeriodIndex):
        raise TypeError(f"Expected a PeriodIndex, got {type(index).__name__}")
    june = index.quarter == JUNE_QUARTER
    mid_year = erp[june].copy()
    mid_year.index = pd.PeriodIndex(index[june].year, freq="Y")
    return mid_year


def fetch() -> ViolenceData:
    """Fetch assault deaths, population and the four AIHW workbook sheets."""
    nhmd = get_fdsv_sheet("NHMD 1", NHMD_HEADER)
    nhmd = nhmd[
        (nhmd["Age group"] == "All ages")
        & (nhmd["Perpetrator's relationship to victim"] == "All FDV perpetrators")
    ].copy()
    nhmd["Value"] = nhmd["Value"].astype(str).str.replace(",", "").astype(float)
    return ViolenceData(
        assault=_assault_deaths(),
        population=_mid_year_population(),
        nhmp=get_fdsv_sheet("NHMP 2", NHMP_HEADER),
        nhmd=nhmd,
        rcv1=get_fdsv_sheet("RCV 1", RCV1_HEADER),
        rcv6=get_fdsv_sheet("RCV 6", RCV6_HEADER),
    )


# --- helpers
def _fy_end_year(fy: str) -> int:
    """Convert an AIHW financial year (e.g. '2019-20', written with an en dash) to its end year."""
    return int(fy.split("\N{EN DASH}", maxsplit=1)[0]) + 1


def _annual(frame: pd.DataFrame, year: str, columns: str, values: str = "Value") -> pd.DataFrame:
    """Pivot to year by column, on an annual PeriodIndex; one value per cell, or raise."""
    if frame.duplicated([year, columns]).any():
        raise ValueError(f"Duplicate {year} x {columns} rows")
    out = frame.pivot_table(index=year, columns=columns, values=values, aggfunc="first", dropna=False).sort_index()
    out.index = pd.PeriodIndex(out.index.astype(int), freq="Y")
    return out


def _numeric(values: pd.Series) -> pd.Series:
    """Strip comma thousands separators; 'n.a.' and 'n.p.' become NaN."""
    return pd.to_numeric(values.astype(str).str.replace(",", ""), errors="coerce")


def _fit_trend(series: pd.Series) -> pd.Series:
    """OLS linear trend across an annual series; returns the fitted values."""
    series = series.dropna()
    index = series.index
    if not isinstance(index, pd.PeriodIndex):
        raise TypeError(f"Expected a PeriodIndex, got {type(index).__name__}")
    x = index.year.to_numpy(dtype=float)
    slope, intercept = np.polyfit(x, series.to_numpy(dtype=float), 1)
    return pd.Series(slope * x + intercept, index=index)


def _rate_per_100k(counts: pd.Series, population: pd.Series, name: str) -> pd.Series:
    return (counts / population * PER_100K).dropna().rename(name)


def _by_sex_with_trend(
    data: pd.DataFrame,
    *,
    title: str,
    ylabel: str,
    rfooter: str,
    lfooter: str,
    rounding: int,
    legend_loc: str = "upper right",
) -> None:
    """Males and Females, each with its fitted linear trend dashed."""
    trend = pd.DataFrame(
        {"Males (trend)": _fit_trend(data["Males"]), "Females (trend)": _fit_trend(data["Females"])}
    )
    ax = mg.line_plot(data[["Males", "Females"]], color=SEX_COLOURS, width=2, annotate=True, rounding=rounding)
    mg.line_plot(trend, ax=ax, color=SEX_COLOURS, width=1, style="--", annotate=False)
    mg.finalise_plot(
        ax,
        title=title,
        ylabel=ylabel,
        rfooter=rfooter,
        lfooter=lfooter,
        legend={"loc": legend_loc, "fontsize": "small"},
    )


def _nhmp(data: ViolenceData, homicide_type: str, unit: str) -> pd.DataFrame:
    frame = data.nhmp.assign(YearEnd=data.nhmp["Period"].apply(_fy_end_year))
    sub = frame[(frame["Type of homicide"] == homicide_type) & (frame["Unit"] == unit)]
    return _annual(sub, "YearEnd", "Sex").astype(float)


def _nhmd(data: ViolenceData, unit: str) -> pd.DataFrame:
    frame = data.nhmd.assign(YearEnd=data.nhmd["Year"].apply(_fy_end_year))
    return _annual(frame[frame["Unit"] == unit], "YearEnd", "Sex")


def _nhmd_rate_unit(data: ViolenceData) -> str:
    """Return the NHMD rate's unit label, found by the part common to its names.

    The AIHW renamed it in 2026: "Rate per 100,000 population" became "Number per 100,000
    population".
    """
    labels = [str(u) for u in data.nhmd["Unit"].unique() if NHMD_RATE_KEY in str(u)]
    if len(labels) != 1:
        raise ValueError(f"Expected one NHMD unit containing {NHMD_RATE_KEY!r}, found {labels}")
    return labels[0]


def _rcv1(data: ViolenceData, offence: str, unit: str) -> pd.DataFrame:
    rcv = data.rcv1
    sub = rcv[(rcv["Location"] == "Australia") & (rcv["Offence"] == offence) & (rcv["Unit"] == unit)].copy()
    sub["Value"] = _numeric(sub["Value"])
    return _annual(sub, "Year", "Sex")


def _all_sexual_assault(data: ViolenceData) -> pd.Series:
    rcv = data.rcv6
    rows = rcv[
        (rcv["Characteristic"] == "Sex") & (rcv["Subcategory"] == "Persons") & (rcv["Unit"] == "Number")
    ].copy()
    rows["Value"] = _numeric(rows["Value"])
    series = rows.set_index("Year")["Value"].sort_index()
    series.index = pd.PeriodIndex(series.index.astype(int), freq="Y")
    return series


def _all_sexual_assault_by_sex(data: ViolenceData, unit: str) -> pd.DataFrame:
    rcv = data.rcv6
    rows = rcv[(rcv["Characteristic"] == "Sex") & (rcv["Subcategory"].isin(["Males", "Females"]))].copy()
    rows["Value"] = _numeric(rows["Value"])
    return _annual(rows[rows["Unit"] == unit], "Year", "Subcategory")[["Males", "Females"]]


def _assault_rate(data: ViolenceData) -> pd.Series:
    return _rate_per_100k(data.assault["Persons"], data.population, "Assault deaths per 100,000")


# --- charts
def assault_deaths(data: ViolenceData) -> None:
    """Assault deaths: the total, by sex, and as a rate per 100,000."""
    mg.bar_plot_finalise(
        data.assault["Persons"],
        title="Assault Deaths: Australia",
        ylabel="Number of deaths per year",
        rfooter=SOURCE_DEATHS,
        lfooter=LFOOTER + DEATHS_NOTE,
        annotate=True,
        rounding=0,
        label_rotation=0,
    )
    mg.line_plot_finalise(
        data.assault[["Males", "Females"]],
        title="Assault Deaths by Sex: Australia",
        ylabel="Number of deaths per year",
        rfooter=SOURCE_DEATHS,
        lfooter=LFOOTER + DEATHS_NOTE,
        color=SEX_COLOURS,
        marker="o",
        annotate=True,
        rounding=0,
    )
    mg.line_plot_finalise(
        _assault_rate(data),
        title="Assault Death Rate: Australia",
        ylabel="Deaths per 100,000 persons",
        rfooter="ABS: 3101.0, 3303.0",
        lfooter=LFOOTER + "ICD-10 X85-Y09. Mid-year ERP denominator.",
        marker="o",
        annotate=True,
        rounding=2,
    )


def homicide(data: ViolenceData) -> None:
    """Domestic and intimate partner homicide victims (AIC NHMP), counts and rates."""
    rate_unit = "Rate (Number per 100,000)"
    domestic, domestic_rate = _nhmp(data, "Domestic", "Number"), _nhmp(data, "Domestic", rate_unit)
    partner, partner_rate = _nhmp(data, "Intimate partner", "Number"), _nhmp(data, "Intimate partner", rate_unit)
    _by_sex_with_trend(
        domestic,
        title="Domestic Homicide Victims by Sex: Australia",
        ylabel="Victims per year",
        rfooter=SOURCE_NHMP,
        lfooter=LFOOTER + "Year ending 30 June. Includes intimate partner, family and other domestic "
        f"homicides. {TREND_NOTE}",
        rounding=0,
    )
    _by_sex_with_trend(
        domestic_rate,
        title="Domestic Homicide Rate by Sex: Australia",
        ylabel="Victims per 100,000\nsame-sex population",
        rfooter=SOURCE_NHMP,
        lfooter=LFOOTER + f"Year ending 30 June. Sex-specific crude rate. {TREND_NOTE}",
        rounding=2,
    )
    _by_sex_with_trend(
        partner,
        title="Intimate Partner Homicide Victims by Sex: Australia",
        ylabel="Victims per year",
        rfooter=SOURCE_NHMP,
        lfooter=LFOOTER + "Year ending 30 June. Intimate partner homicides only (subset of all "
        f"domestic). {TREND_NOTE}",
        rounding=0,
    )
    _by_sex_with_trend(
        partner_rate,
        title="Intimate Partner Homicide Rate by Sex: Australia",
        ylabel="Victims per 100,000\nsame-sex population aged 18+",
        rfooter=SOURCE_NHMP,
        lfooter=LFOOTER + f"Year ending 30 June. Sex-specific crude rate. {TREND_NOTE}",
        rounding=2,
    )
    mg.line_plot_finalise(
        domestic_rate["Persons"],
        title="Domestic Homicide Rate: Australia",
        ylabel="Victims per 100,000 population",
        rfooter=SOURCE_NHMP,
        lfooter=LFOOTER + "Year ending 30 June. Persons total (includes unknown sex).",
        annotate=True,
        rounding=2,
    )
    mg.line_plot_finalise(
        pd.DataFrame({"All domestic": domestic_rate["Persons"], "Intimate partner": partner_rate["Persons"]}),
        title="Domestic vs Intimate Partner Homicide Rate: Australia",
        ylabel="Victims per 100,000 population",
        rfooter=SOURCE_NHMP,
        lfooter=LFOOTER + "Year ending 30 June. Persons total. IPV is a subset of all domestic.",
        annotate=True,
        rounding=2,
    )


def hospitalisations(data: ViolenceData) -> None:
    """FDV hospitalisations by sex (AIHW NHMD): counts and rates."""
    for unit, title, ylabel, note, rounding in (
        (
            "Number",
            "FDV Hospitalisations by Sex: Australia",
            "Hospitalisations per year",
            "All ages. Year ending 30 June. Spouse/partner or family perpetrator.",
            0,
        ),
        (
            _nhmd_rate_unit(data),
            "FDV Hospitalisation Rate by Sex: Australia",
            "Hospitalisations per\n100,000 same-sex population",
            "All ages. Year ending 30 June. Crude rate.",
            1,
        ),
    ):
        mg.line_plot_finalise(
            _nhmd(data, unit)[["Male", "Female"]],
            title=title,
            ylabel=ylabel,
            rfooter=SOURCE_HOSP,
            lfooter=LFOOTER + FDV_NOTE + note,
            color=SEX_COLOURS,
            marker="o",
            annotate=True,
            rounding=rounding,
        )


def police_recorded(data: ViolenceData) -> None:
    """Police-recorded sexual assault (all and FDV-flagged) and FDV homicide, from ABS 4510.0."""
    fdv_count = _rcv1(data, "Sexual assault", "Number")
    all_count = _all_sexual_assault(data)
    _by_sex_with_trend(
        fdv_count,
        title="Police-Recorded FDV Sexual Assault Victims by Sex: Australia",
        ylabel="Police-recorded victims per year",
        rfooter=SOURCE_POLICE,
        lfooter=LFOOTER + FDV_NOTE + f"Calendar year. {TREND_NOTE}",
        rounding=0,
        legend_loc="upper left",
    )
    _by_sex_with_trend(
        _rcv1(data, "Sexual assault", RCV_RATE),
        title="Police-Recorded FDV Sexual Assault Rate by Sex: Australia",
        ylabel="Police-recorded victims per\n100,000 same-sex population",
        rfooter=SOURCE_POLICE,
        lfooter=LFOOTER + FDV_NOTE + f"Calendar year. Crude rate. {TREND_NOTE}",
        rounding=1,
        legend_loc="upper left",
    )
    mg.line_plot_finalise(
        pd.DataFrame({"All sexual assault": all_count, "FDV-flagged subset": fdv_count["Persons"]}),
        title="Police-Recorded Sexual Assault: All vs FDV-Flagged",
        ylabel="Victims per year (Persons)",
        rfooter=SOURCE_POLICE,
        lfooter=LFOOTER
        + FDV_NOTE
        + "Calendar year. FDV-flagged is a subset of all police-recorded sexual assault.",
        annotate=True,
        rounding=0,
    )
    mg.line_plot_finalise(
        (fdv_count["Persons"] / all_count * 100).dropna().rename("FDV-flagged % of all sexual assault"),
        title="FDV-Flagged Share of Police-Recorded Sexual Assault",
        ylabel="Per cent of all sexual assault victims",
        rfooter=SOURCE_POLICE,
        lfooter=LFOOTER + FDV_NOTE + "Calendar year. Rising share reflects changing police flagging practice.",
        marker="o",
        annotate=True,
        rounding=1,
    )
    not_fdv = "Calendar year. All police-recorded sexual assault (not FDV-restricted). "
    _by_sex_with_trend(
        _all_sexual_assault_by_sex(data, "Number"),
        title="Police-Recorded Sexual Assault by Sex: Australia",
        ylabel="Police-recorded victims per year",
        rfooter=SOURCE_POLICE,
        lfooter=LFOOTER + not_fdv + TREND_NOTE,
        rounding=0,
        legend_loc="upper left",
    )
    _by_sex_with_trend(
        _all_sexual_assault_by_sex(data, RCV_RATE),
        title="Police-Recorded Sexual Assault Rate by Sex: Australia",
        ylabel="Police-recorded victims per\n100,000 same-sex population",
        rfooter=SOURCE_POLICE,
        lfooter=LFOOTER + not_fdv + f"Crude rate. {TREND_NOTE}",
        rounding=1,
        legend_loc="upper left",
    )
    _by_sex_with_trend(
        _rcv1(data, "Homicide and related offences", "Number"),
        title="Police-Recorded FDV Homicide and Related Offences by Sex: Australia",
        ylabel="Police-recorded victims per year",
        rfooter=SOURCE_POLICE,
        lfooter=LFOOTER + FDV_NOTE + f"Calendar year. {TREND_NOTE}",
        rounding=0,
    )


def indexed_comparison(data: ViolenceData) -> None:
    """Hard outcomes against police-reported indicators, each a Persons rate indexed to 2019 = 100.

    NHMD starts in FY2020, so it is indexed to its first year.
    """

    def rebase(series: pd.Series) -> pd.Series:
        series = series.dropna()
        at_base = series[series.index == pd.Period(str(BASE_YEAR), freq="Y")]
        return series / (at_base.iloc[0] if not at_base.empty else series.iloc[0]) * 100

    raw = {
        "Assault deaths (rate)": _assault_rate(data),
        "Domestic homicide (rate)": _nhmp(data, "Domestic", "Rate (Number per 100,000)")["Persons"],
        "FDV hospitalisations (rate)": _rate_per_100k(
            _nhmd(data, "Number")["Persons"], data.population, "FDV hospitalisations (rate)"
        ),
        "All sexual assault, police-reported (rate)": _rate_per_100k(
            _all_sexual_assault(data), data.population, "All sexual assault (rate)"
        ),
        "FDV-flagged sexual assault, police-reported (rate)": _rcv1(data, "Sexual assault", RCV_RATE)["Persons"],
    }
    frame = pd.DataFrame({name: rebase(series) for name, series in raw.items()})
    mg.line_plot_finalise(
        frame.loc[pd.Period(str(INDEX_START), "Y") : pd.Period(str(INDEX_END), "Y")],
        title="Hard Outcomes vs Police-Reported Indicators: Indexed Comparison",
        ylabel=f"Index of rate per 100,000\n({BASE_YEAR} = 100)",
        rfooter="ABS: 3303.0, 4510.0; AIC: NHMP; AIHW: NHMD",
        lfooter=LFOOTER + "Persons total. NHMD rebased to FY2020.",
        color=INDEX_COLOURS,
        style=INDEX_STYLES,
        axhline={"y": 100, "color": "grey", "linestyle": ":"},
        annotate=False,
        legend={"loc": "upper left", "fontsize": "small"},
    )


# --- table of contents, in run order
CHARTS = (
    (assault_deaths, ()),
    (homicide, ()),
    (hospitalisations, ()),
    (police_recorded, ()),
    (indexed_comparison, ()),
)
