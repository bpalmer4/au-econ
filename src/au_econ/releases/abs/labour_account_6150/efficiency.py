"""The efficient unemployment rate u* = sqrt(uv), after Michaillat and Saez (2022), NBER Working Paper 30211.

Unemployment and vacancy rates take the Labour Account where it has data and the Labour
Force Survey and Job Vacancies Survey before it. The Beveridge elasticity d ln v / d ln u is
estimated as in Michaillat and Saez (2021), with Bai-Perron structural breaks, and printed.
"""

# --- dependencies
import numpy as np
import pandas as pd
import readabs as ra
from matplotlib.ticker import NullFormatter, StrMethodFormatter
from mgplot import fill_between_plot, finalise_plot, line_plot, line_plot_finalise
from statsmodels.regression.linear_model import OLS
from statsmodels.tools.tools import add_constant

from au_econ.releases.abs.labour_account_6150.common import (
    JVS_CATALOGUE,
    LA_LABOUR_FORCE,
    LA_UNEMPLOYED,
    LA_VACANCIES,
    LFS_CATALOGUE,
    LFS_LABOUR_FORCE,
    LFS_UNEMPLOYED,
    PER_CENT,
    LabourAccountData,
    jvs_vacancies,
    la_series,
    lfs_quarterly_mean,
)

# --- constants
U_RATE, V_RATE, U_STAR = "Unemployment rate u", "Vacancy rate v", "Efficient rate u* = √uv"
EFFICIENT_TIGHTNESS = 1.0
TIGHTNESS_HEADROOM = 1.1  # keeps the efficiency line off the top edge of the chart
RATE_YLABEL = "Per cent of labour force"
LOG_YTICKS = (0.5, 1, 2, 4, 8)
BP_TRIM = 0.15  # minimum segment length, as a share of the sample
BP_MAX_BREAKS = 5
BP_PARAMS_PER_SEGMENT = 2  # intercept and slope
HAC_LAGS = 4  # Newey-West lags for quarterly data
PRE_COVID_END = pd.Period("2019Q4", freq="Q-DEC")


# --- helpers
def _rates(data: LabourAccountData) -> tuple[pd.DataFrame, pd.Period]:
    """Spliced unemployment and vacancy rates, and u*; and the first Labour Account quarter.

    The rates are per cent of the labour force, with the vacancy-survey gap left as NaN.
    """
    la_force = la_series(data, LA_LABOUR_FORCE)
    lfs_force = lfs_quarterly_mean(data, LFS_LABOUR_FORCE)
    segments = {
        U_RATE: (la_series(data, LA_UNEMPLOYED) / la_force, lfs_quarterly_mean(data, LFS_UNEMPLOYED) / lfs_force),
        V_RATE: (la_series(data, LA_VACANCIES) / la_force, jvs_vacancies(data) / lfs_force),
    }
    rates = {}
    for name, (la_rate, old_rate) in segments.items():
        # Labour Account first, so it wins wherever it has data; rates, so no rebase
        rates[name], _report = ra.splice(
            [(la_rate * PER_CENT).dropna(), (old_rate * PER_CENT).dropna()], rebase=False, name=name
        )
    frame = pd.DataFrame(rates)
    frame = frame.loc[frame[V_RATE].first_valid_index() :]
    # splice drops quarters that no segment covers; reinstate them as NaN
    index = frame.index
    if not isinstance(index, pd.PeriodIndex):
        raise TypeError(f"Expected a PeriodIndex, got {type(index).__name__}")
    frame = frame.reindex(pd.period_range(index[0], index[-1], freq=index.freqstr))
    frame[U_STAR] = (frame[U_RATE] * frame[V_RATE]) ** 0.5
    if frame[U_STAR].dropna().empty:
        raise ValueError("No overlapping unemployment and vacancy data")
    first_la = la_force.dropna().index[0]
    if not isinstance(first_la, pd.Period):
        raise TypeError(f"Expected a Period, got {type(first_la).__name__}")
    return frame, first_la


def _source(data: LabourAccountData) -> str:
    return f"{data.account.source}, {LFS_CATALOGUE}, {JVS_CATALOGUE}"


def _source_change(junction: pd.Period) -> dict[str, object]:
    return {"x": junction, "color": "grey", "linestyle": ":", "lw": 0.75, "label": f"Source change {junction}"}


def _segment_ssr(y: np.ndarray, x: np.ndarray) -> float:
    """Sum of squared residuals from an OLS regression of y on a constant and x."""
    design = np.column_stack([np.ones_like(x), x])
    coef = np.linalg.lstsq(design, y, rcond=None)[0]
    resid = y - design @ coef
    return float(resid @ resid)


def _bai_perron_breaks(y: np.ndarray, x: np.ndarray) -> list[int]:
    """Break positions minimising BIC, by Bai-Perron dynamic programming.

    Each segment is its own regression of y on x, at least BP_TRIM of the sample long.
    Returns the positions (row numbers) where each new segment starts.
    """
    n = len(y)
    h = int(BP_TRIM * n)
    cost = np.full((n, n + 1), np.inf)  # cost[i, j]: SSR of the segment y[i:j]
    for i in range(n):
        for j in range(i + h, n + 1):
            cost[i, j] = _segment_ssr(y[i:j], x[i:j])

    # best[j]: the lowest SSR for y[:j] with k breaks, and those breaks
    best: dict[int, tuple[float, list[int]]] = {j: (cost[0, j], []) for j in range(h, n + 1)}
    candidates = {0: best[n]}
    for k in range(1, BP_MAX_BREAKS + 1):
        best = {
            j: min(
                ((best[b][0] + cost[b, j], [*best[b][1], b]) for b in range(k * h, j - h + 1) if b in best),
                key=lambda option: option[0],
            )
            for j in range((k + 1) * h, n + 1)
        }
        if n in best:
            candidates[k] = best[n]

    bic = {
        k: n * np.log(ssr / n) + ((BP_PARAMS_PER_SEGMENT + 1) * k + BP_PARAMS_PER_SEGMENT) * np.log(n)
        for k, (ssr, _breaks) in candidates.items()
    }
    return candidates[min(bic, key=lambda k: bic[k])][1]


def _beveridge_elasticities(rates: pd.DataFrame, end: pd.Period | None) -> pd.DataFrame:
    """Beveridge elasticity for the whole sample and within each Bai-Perron segment."""
    logs = pd.DataFrame(np.log(rates[[U_RATE, V_RATE]].loc[:end])).dropna()
    breaks = _bai_perron_breaks(logs[V_RATE].to_numpy(), logs[U_RATE].to_numpy())
    spans = [(0, len(logs)), *zip([0, *breaks], [*breaks, len(logs)], strict=True)]
    rows = {}
    for number, (start, stop) in enumerate(spans):
        segment = logs.iloc[start:stop]
        forward = OLS(segment[V_RATE], add_constant(segment[U_RATE])).fit(
            cov_type="HAC", cov_kwds={"maxlags": HAC_LAGS}
        )
        reverse = OLS(segment[U_RATE], add_constant(segment[V_RATE])).fit()
        span = f"{segment.index[0]}\N{EN DASH}{segment.index[-1]}"
        rows["No breaks: " + span if number == 0 else span] = {
            "Quarters": len(segment),
            "OLS ε": forward.params[U_RATE],
            "HAC se": forward.bse[U_RATE],
            "Reverse ε": 1 / reverse.params[V_RATE],
            "R²": forward.rsquared,
        }
    return pd.DataFrame(rows).T.round(2)


# --- charts
def efficient_unemployment(data: LabourAccountData) -> None:
    """Chart u, v and u*, the unemployment gap and tightness; print the Beveridge elasticities."""
    rates, junction = _rates(data)
    lfooter = (
        f"Australia. Seasonally adjusted. Labour Account from {junction}, JVS/LFS before. "
        "US-calibrated benchmark. "
    )
    source_change = _source_change(junction)

    # Michaillat and Saez figure 4A: u, v and u*
    line_plot_finalise(
        rates[[U_RATE, U_STAR, V_RATE]],
        dropna=False,
        title="Efficient Unemployment Rate",
        ylabel=RATE_YLABEL,
        axvline=source_change,
        legend=True,
        lfooter=lfooter + "u* = √(u × v). ",
        rfooter=_source(data),
    )

    # Michaillat and Saez figure 4B: u against u*, with the gap shaded
    ax = fill_between_plot(rates[[U_STAR, U_RATE]], label="Unemployment gap u \N{MINUS SIGN} u*")
    line_plot(rates[[U_RATE, U_STAR]], ax=ax, dropna=False)
    finalise_plot(
        ax,
        title="Unemployment Gap",
        ylabel=RATE_YLABEL,
        axvline=source_change,
        legend=True,
        lfooter=lfooter + "u* = √(u × v). ",
        rfooter=_source(data),
    )

    # Michaillat and Saez figure 3B: tightness against the efficient level of 1
    tightness = (rates[V_RATE] / rates[U_RATE]).rename("Tightness θ = v/u")
    line_plot_finalise(
        tightness,
        dropna=False,
        title="Labour Market Tightness",
        ylabel="Vacancies per unemployed person",
        ylim=(0, max(tightness.max(), EFFICIENT_TIGHTNESS) * TIGHTNESS_HEADROOM),
        axhline={
            "y": EFFICIENT_TIGHTNESS,
            "color": "black",
            "linestyle": "--",
            "lw": 0.75,
            "label": "Efficient: θ = 1",
        },
        axvline=source_change,
        legend=True,
        lfooter=lfooter + "θ = v/u. ",
        rfooter=_source(data),
    )

    for label, end in (("Pre-COVID", PRE_COVID_END), ("Full sample", None)):
        print(f"\nBeveridge elasticities, {label}")
        print(_beveridge_elasticities(rates, end).to_string())


def log_rates(data: LabourAccountData) -> None:
    """Unemployment and vacancy rates on a log scale (Michaillat and Saez figure 1B).

    With a unit-elastic Beveridge curve and a stable uv, the two lines would be mirror images
    on this scale.
    """
    rates, junction = _rates(data)
    axes = line_plot(rates[[U_RATE, V_RATE]], dropna=False)
    axes.set_yscale("log")  # resets the locators, so set the ticks after this
    axes.set_yticks(LOG_YTICKS)
    axes.yaxis.set_major_formatter(StrMethodFormatter("{x:g}"))
    axes.yaxis.set_minor_formatter(NullFormatter())
    finalise_plot(
        axes,
        title="Unemployment and Vacancy Rates",
        ylabel="Per cent of labour force (log scale)",
        axvline=_source_change(junction),
        legend=True,
        lfooter=f"Australia. Seasonally adjusted. Labour Account from {junction}, JVS/LFS before. ",
        rfooter=_source(data),
    )


# --- table of contents, in run order
CHARTS = (
    (efficient_unemployment, ()),
    (log_rates, ()),
)
