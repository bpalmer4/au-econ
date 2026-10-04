"""National Accounts wages and unit labour costs: calculated and official ULC, hourly COE, real wages."""

# --- dependencies
from typing import TYPE_CHECKING, Any

import pandas as pd
import readabs as ra
from mgplot import (
    calc_growth,
    chart_subdir,
    growth_plot_finalise,
    line_plot_finalise,
    multi_start,
    postcovid_plot_finalise,
    series_growth_plot_finalise,
)
from readabs import metacol as mc

from au_econ.charting.windows import quarterly_plot_times
from au_econ.releases.abs.national_accounts_5206.common import (
    ANALYTICAL,
    AUSTRALIA,
    CP_NOTE,
    DEFLATORS,
    INCOME_FROM_GDP,
    KEY_AGGS,
    ORIGINAL,
    QUARTERS_PER_YEAR,
    SA_NOTE,
    SEASONALLY_ADJUSTED,
    data_to,
)
from au_econ.series.prices import get_wage_index

if TYPE_CHECKING:
    from au_econ.sources.abs import AbsRelease

# --- constants
SUBDIR = "Wages-ULC"
SA = SEASONALLY_ADJUSTED
PERCENT = 100
GROWTH_FROM = quarterly_plot_times[1]
MILLION = 1_000_000

ULC_TABLE = "5206042_Unit_Labour_Costs"
COE_DID = "Compensation of employees ;"
GDP_CVM_DID = "Gross domestic product: Chain volume measures ;"
HOURS_DID = "Hours worked: Index ;"
HFCE_DID = "Households ;  Final consumption expenditure ;"
HOURLY_COE_DIDS = (
    "Compensation of employees per hour: Current prices ;",
    "Non-farm compensation of employees per hour: Current prices ;",
)
REAL_WAGE_DIDS = (
    "Average compensation per employee: Current prices ;",
    "Compensation of employees per hour: Current prices ;",
)
WAGES_DID = "Compensation of employees - Wages and salaries ;"
COE_HOURS_NOTE = "Cost of Employees: employees only; hours: all jobs incl. self-employed"
WPI_CATALOGUE = "6345.0"


# --- helpers
def _analytical_row(release: AbsRelease, did: str) -> pd.Series:
    """Return the seasonally adjusted metadata row for an exact description in the analytical table."""
    meta = release.meta
    return meta[(meta[mc.table] == ANALYTICAL) & (meta[mc.stype] == SA) & (meta[mc.did] == did)].iloc[0]


def _coe(release: AbsRelease) -> pd.Series:
    """Return compensation of employees, current prices, seasonally adjusted."""
    _, coe_id, _ = ra.find_abs_id(
        release.meta,
        {INCOME_FROM_GDP: mc.table, SA: mc.stype, COE_DID: mc.did},
        exact_match=True,
        verbose=False,
    )
    return release.data[INCOME_FROM_GDP][coe_id].dropna()


def _household_deflator(release: AbsRelease) -> pd.Series:
    """Return the household consumption deflator, rebased to 1 in the latest quarter."""
    meta = release.meta
    ident = meta[(meta[mc.did] == HFCE_DID) & (meta[mc.table] == DEFLATORS)][mc.id].iloc[0]
    series = release.data[DEFLATORS][ident]
    return series / series.iloc[-1]


# --- charts
def ulc_calculated(release: AbsRelease) -> None:
    """Chart unit labour costs calculated as COE over real GDP: level, growth, and against the official index."""
    _table, gdp_id, _units = ra.find_abs_id(
        release.meta, {KEY_AGGS: mc.table, SA: mc.stype, GDP_CVM_DID: mc.did, "$": mc.unit}, verbose=False
    )
    gdp = release.data[KEY_AGGS][gdp_id].dropna()
    ulc = (_coe(release) / gdp).dropna()
    ulc.name = "Calculated Nominal ULC"

    common: dict[str, Any] = {
        "rfooter": f"{release.source}",
        "lfooter": f"{AUSTRALIA}{SA_NOTE}ULC = COE / GDP(CVM). {data_to(ulc)}",
        "pre_tag": "ulc-calc-",
    }
    with chart_subdir(SUBDIR):
        multi_start(
            ulc,
            function=line_plot_finalise,
            starts=quarterly_plot_times,
            title="Calculated Nominal Unit Labour Costs",
            ylabel="Ratio (COE / GDP CVM)",
            annotate=True,
            **common,
        )
        growth = calc_growth(ulc)
        growth_plot_finalise(
            growth,
            title="Calculated Unit Labour Costs Growth",
            ylabel="Per cent growth",
            plot_from=GROWTH_FROM,
            tag="growth",
            **common,
        )
        line_plot_finalise(
            growth[growth.columns[0]],
            title="Calculated Unit Labour Costs Growth (YoY)",
            ylabel="Per cent growth",
            y0=True,
            tag="growth-annual",
            **common,
        )

        # against the official nominal ULC index (whole economy, not non-farm)
        meta = release.meta
        table42 = meta[(meta[mc.table] == ULC_TABLE) & (meta[mc.stype] == SA)]
        dids = table42[mc.did]
        official_rows = table42[
            dids.str.contains("Nominal", case=False, na=False)
            & dids.str.contains("unit labour cost", case=False, na=False)
            & ~dids.str.contains("Non-farm", case=False, na=False)
            & ~dids.str.contains("Percentage", case=False, na=False)
        ]
        if official_rows.empty:
            raise ValueError(f"No official nominal ULC series in {ULC_TABLE}")
        official = release.data[ULC_TABLE][official_rows[mc.id].iloc[0]].dropna()
        labels = ("Calculated (COE/GDP)", "Official (Table 42)")
        compare = pd.DataFrame(
            {
                labels[0]: ulc / ulc.iloc[0] * PERCENT,
                labels[1]: official / official.iloc[0] * PERCENT,
            }
        ).dropna()
        line_plot_finalise(
            compare,
            title="ULC Comparison: Calculated vs Official Index",
            ylabel="Index (start = 100)",
            annotate=True,
            legend={"loc": "best", "fontsize": 9},
            tag="vs-official",
            lfooter=f"{AUSTRALIA}{SA_NOTE}Calculated = COE/GDP(CVM). Official = Table 42 Nominal ULC. "
            f"{data_to(compare)}",
            rfooter=f"{release.source}",
            pre_tag="ulc-calc-",
        )
        growth_compare = pd.DataFrame(
            {
                labels[0]: ulc.pct_change(periods=QUARTERS_PER_YEAR) * PERCENT,
                labels[1]: official.pct_change(periods=QUARTERS_PER_YEAR) * PERCENT,
            }
        ).dropna()
        line_plot_finalise(
            growth_compare,
            title="ULC Growth Comparison: Calculated vs Official",
            ylabel="Per cent (YoY)",
            annotate=True,
            y0=True,
            legend={"loc": "best", "fontsize": 9},
            tag="growth-vs-official",
            lfooter=f"{AUSTRALIA}{SA_NOTE}{data_to(growth_compare)}",
            rfooter=f"{release.source}",
            pre_tag="ulc-calc-",
        )


def ulc_official(release: AbsRelease) -> None:
    """Every seasonally adjusted series in the official unit labour costs table: level and growth."""
    meta = release.meta
    rows = meta[(meta[mc.table] == ULC_TABLE) & (meta[mc.stype] == SA)]
    with chart_subdir(SUBDIR):
        for _, row in rows.iterrows():
            series = release.data[ULC_TABLE][row[mc.id]].dropna()
            common: dict[str, Any] = {
                "rfooter": release.source,
                "lfooter": f"{AUSTRALIA}{SA_NOTE}{CP_NOTE if 'Nominal' in row[mc.did] else ''}{data_to(series)}",
                "pre_tag": "ulc-official-",
            }
            title = row[mc.did].replace(" ;", "").strip()
            multi_start(
                series,
                function=line_plot_finalise,
                starts=quarterly_plot_times,
                title=title,
                ylabel=row[mc.unit],
                annotate=True,
                **common,
            )
            series_growth_plot_finalise(
                series, title=f"{title} growth", plot_from=GROWTH_FROM, tag="growth", **common
            )


def hourly_coe(release: AbsRelease) -> None:
    """Compensation of employees per hour, all sectors and non-farm: level, COVID recovery and growth."""
    data = release.data[ANALYTICAL]
    footers: dict[str, Any] = {"rfooter": release.source, "pre_tag": "hourly-coe-"}
    lfooter = f"{AUSTRALIA}{SA_NOTE}{CP_NOTE}"
    with chart_subdir(SUBDIR):
        for did in HOURLY_COE_DIDS:
            row = _analytical_row(release, did)
            series = data[row[mc.id]].dropna()
            common = footers | {"lfooter": f"{lfooter}{data_to(series)}"}
            title = did.replace(": Current prices ;", "").strip()
            multi_start(
                series,
                function=line_plot_finalise,
                starts=quarterly_plot_times,
                title=title,
                ylabel=row[mc.unit],
                annotate=True,
                **common,
            )
            postcovid_plot_finalise(
                series,
                title=title,
                ylabel=row[mc.unit],
                tag="covid",
                annotate=[False, True],
                **common,
            )
            series_growth_plot_finalise(
                series, title=f"{title} growth", plot_from=GROWTH_FROM, tag="growth", **common
            )

        all_row, nonfarm_row = (_analytical_row(release, did) for did in HOURLY_COE_DIDS)
        comparison = pd.DataFrame(
            {"All sectors": data[all_row[mc.id]], "Non-farm": data[nonfarm_row[mc.id]]}
        ).dropna()
        common = footers | {
            "lfooter": f"{lfooter}COE = compensation of employees. {data_to(comparison)}",
        }
        line_plot_finalise(
            comparison,
            title="Hourly COE: All sectors vs Non-farm",
            ylabel=all_row[mc.unit],
            annotate=True,
            **common,
        )
        line_plot_finalise(
            (comparison.pct_change(periods=QUARTERS_PER_YEAR) * PERCENT).dropna(),
            title="Hourly COE Growth (YoY): All sectors vs Non-farm",
            ylabel="Per cent",
            tag="growth-comparison",
            annotate=True,
            y0=True,
            **common,
        )


def real_wages(release: AbsRelease) -> None:
    """Compensation per employee and per hour, deflated by the household consumption deflator."""
    deflator = _household_deflator(release)
    with chart_subdir(SUBDIR):
        for did in REAL_WAGE_DIDS:
            row = _analytical_row(release, did)
            series = (release.data[ANALYTICAL][row[mc.id]] / deflator).dropna()
            title = did.split(":")[0].strip()
            series.name = title
            suffix = "" if "per hour" in did else " / Qtr"
            common: dict[str, Any] = {
                "title": f"Real {title}",
                "ylabel": f"{row[mc.unit]} (inflation adjusted){suffix}",
                "rfooter": release.source,
                "lfooter": f"{AUSTRALIA}{SA_NOTE}{CP_NOTE}Deflated by the household consumption deflator. "
                f"{data_to(series)}",
                "pre_tag": "wages-",
            }
            line_plot_finalise(series, annotate=True, **common)
            postcovid_plot_finalise(series, tag="covid", annotate=[False, True], **common)


def coe_vs_wpi(release: AbsRelease) -> None:
    """Compensation of employees per hour worked: its growth, and against the Wage Price Index."""
    _, hours_id, _ = ra.find_abs_id(
        release.meta, {KEY_AGGS: mc.table, SA: mc.stype, HOURS_DID: mc.did}, verbose=False
    )
    hours = release.data[KEY_AGGS][hours_id].dropna()
    hourly = (_coe(release) / hours).dropna()  # $ per index point: only its growth matters

    with chart_subdir(SUBDIR):
        multi_start(
            hourly,
            function=series_growth_plot_finalise,
            starts=quarterly_plot_times,
            title="Cost of Employees/Hour: Growth",
            tag="growth",
            rheader=COE_HOURS_NOTE,
            rfooter=release.source,
            lfooter=f"{AUSTRALIA}{SA_NOTE}{CP_NOTE}Cost of Employees per total hour worked. {data_to(hourly)}",
            pre_tag="wage-inflation-",
        )

        wpi = get_wage_index("WPI")[0]
        compare: dict[str, Any] = {
            "rheader": COE_HOURS_NOTE,
            "rfooter": f"{release.source}, {WPI_CATALOGUE}",
            "lfooter": f"{AUSTRALIA}{SA_NOTE}{CP_NOTE}WPI = Wage Price Index (total hourly rates excl. bonuses). "
            f"{data_to(pd.concat([hourly, wpi], axis=1).dropna())}",
            "pre_tag": "wage-inflation-",
            "annotate": True,
            "legend": {"loc": "best", "fontsize": 8},
        }
        base = hourly.index.intersection(wpi.index).min()
        index = pd.DataFrame(
            {
                "Cost of Employees/Hour (incl. bonuses, overtime, super)": hourly / hourly.loc[base] * PERCENT,
                "WPI (excl. bonuses)": wpi / wpi.loc[base] * PERCENT,
            }
        ).dropna()
        multi_start(
            index,
            function=line_plot_finalise,
            starts=quarterly_plot_times,
            title="Wage Growth: Cost of Employees/Hour vs WPI",
            ylabel=f"Index ({base} = 100)",
            tag="index",
            **compare,
        )
        growth = pd.DataFrame(
            {
                "Cost of Employees/Hour (TTY)": (hourly / hourly.shift(QUARTERS_PER_YEAR) - 1).mul(PERCENT),
                "WPI (TTY)": (wpi / wpi.shift(QUARTERS_PER_YEAR) - 1).mul(PERCENT),
            }
        ).dropna()
        multi_start(
            growth,
            function=line_plot_finalise,
            starts=quarterly_plot_times,
            title="Wage Inflation: Cost of Employees/Hour vs WPI",
            ylabel="Annual growth (%)",
            y0=True,
            tag="growth-overlay",
            **compare,
        )


def wages_per_capita(release: AbsRelease) -> None:
    """Wages and salaries per person (implicit population), deflated by the household consumption deflator."""
    meta, data = release.meta, release.data
    _table, wages_id, wage_units = ra.find_abs_id(
        meta, {INCOME_FROM_GDP: mc.table, WAGES_DID: mc.did, SA: mc.stype}, verbose=False
    )
    _table, ipd_id, _units = ra.find_abs_id(
        meta, {DEFLATORS: mc.table, HFCE_DID: mc.did, SA: mc.stype}, verbose=False
    )
    ipd = data[DEFLATORS][ipd_id]
    _table, gdp_id, _units = ra.find_abs_id(
        meta,
        {KEY_AGGS: mc.table, "Gross domestic product: Current prices ;": mc.did, ORIGINAL: mc.stype, "$": mc.unit},
        verbose=False,
    )
    _table, gdp_pc_id, _units = ra.find_abs_id(
        meta,
        {KEY_AGGS: mc.table, ORIGINAL: mc.stype, "GDP per capita: Current prices ;": mc.did},
        verbose=False,
    )
    population = data[KEY_AGGS][gdp_id] / data[KEY_AGGS][gdp_pc_id] * MILLION
    real_pc, unit = ra.recalibrate(data[INCOME_FROM_GDP][wages_id] / population / (ipd / ipd.iloc[-1]), wage_units)
    common: dict[str, Any] = {
        "rfooter": release.source,
        "lfooter": f"{AUSTRALIA}{SA_NOTE}Deflated by the household consumption deflator. "
        f"Per head of implicit population. {data_to(real_pc)}",
        "pre_tag": "wages-",
        "title": "Real wages and salaries per capita",
        "ylabel": f"{unit} - {population.index[-1]} prices\nper Quarter",
    }
    with chart_subdir(SUBDIR):
        line_plot_finalise(real_pc, annotate=True, **common)
        postcovid_plot_finalise(real_pc, tag="covid", **common)


# --- table of contents, in run order
CHARTS = (
    (ulc_calculated, ()),
    (ulc_official, ()),
    (hourly_coe, ()),
    (real_wages, ()),
    (coe_vs_wpi, ()),
    (wages_per_capita, ()),
)
