"""Shared pieces of the National Accounts module: tables, descriptions and windows."""

# --- dependencies
from au_econ.charting.footers import SERIES_TYPE_NOTES, data_to

__all__ = ["data_to"]  # re-exported: the module's chart files take it from here

# --- tables
KEY_AGGS = "5206001_Key_Aggregates"
EXPENDITURE_VOLUME = "5206002_Expenditure_Volume_Measures"
EXPENDITURE_CP = "5206003_Expenditure_Current_Price"
DEFLATORS = "5206005_Expenditure_Implicit_Price_Deflators"
INDUSTRY_GVA = "5206006_Industry_GVA"
INCOME_FROM_GDP = "5206007_Income_From_GDP"
HFCE_TABLE = "5206008_Household_Final_Consumption_Expenditure"
CAPITAL_ACCOUNT = "5206012_National_Capital_Account"
NFC_INCOME = "5206013_NFC_Income"
HOUSEHOLD_INCOME = "5206020_Household_Income"
TAXES = "5206022_Taxes"
ANALYTICAL = "5206024_Selected_Analytical_Series"
SFD_SUMMARY = "5206025_SFD_Summary"

# --- series types, price measures and units
SEASONALLY_ADJUSTED, ORIGINAL = "Seasonally Adjusted", "Original"
CVM, CP = "Chain volume measures", "Current prices"
MILLIONS = "$ Millions"
INDEX_NUMBERS = "Index Numbers"
QUARTERS_PER_YEAR = 4

# --- lfooter notes: "Australia. <series type> <price measure> <chart notes> Data to <period>."
AUSTRALIA = "Australia. "
SA_NOTE = f"{SERIES_TYPE_NOTES[SEASONALLY_ADJUSTED]} "
SA_SHORT = "Seas adj. "  # only where the full note would collide with the right footer
ORIGINAL_NOTE = f"{SERIES_TYPE_NOTES[ORIGINAL]} "
CVM_NOTE, CP_NOTE = "Chain volume measures. ", "Current prices. "
