"""Labour productivity: real GDP per Labour Account hour worked."""

# --- dependencies
import readabs as ra
from mgplot import line_plot_finalise, series_growth_plot_finalise
from readabs import metacol as mc

from au_econ.releases.abs.labour_account_6150.common import DETAIL_TABLE, SEASONALLY_ADJUSTED, LabourAccountData
from au_econ.series.gdp import GDP_CATALOGUE, get_gdp

# --- constants
HOURS_WORKED = "Volume; Labour Account hours actually worked in all jobs ;  Australia ;  Total all industries ;"
DOLLARS_PER_MILLION, HOURS_PER_THOUSAND = 1_000_000, 1_000
TITLE = "Labour Productivity: GDP per Hour Worked"


# --- charts
def labour_productivity(data: LabourAccountData) -> None:
    """Chain volume GDP per hour actually worked, and its growth."""
    gdp, _units = get_gdp("CVM", "SA")
    _table, hours_id, _hours_units = ra.find_abs_id(
        data.account.meta,
        {DETAIL_TABLE: mc.table, HOURS_WORKED: mc.did, SEASONALLY_ADJUSTED: mc.stype},
        verbose=False,
    )
    hours = data.account.data[DETAIL_TABLE][hours_id] * HOURS_PER_THOUSAND
    productivity = (gdp * DOLLARS_PER_MILLION / hours).rename("Labour Productivity (CVM, GDP($) per hour worked)")
    rfooter = f"ABS: {GDP_CATALOGUE}, {data.account.source.removeprefix('ABS: ')}"
    lfooter = (
        f"Australia. {SEASONALLY_ADJUSTED.capitalize()}. GDP: Chain volume measures. "
        "Hours: Total actual hours worked. "
    )
    line_plot_finalise(productivity, dropna=True, title=TITLE, ylabel="$", rfooter=rfooter, lfooter=lfooter)
    series_growth_plot_finalise(productivity, title=f"Growth in {TITLE}", rfooter=rfooter, lfooter=lfooter)


# --- table of contents, in run order
CHARTS = ((labour_productivity, ()),)
