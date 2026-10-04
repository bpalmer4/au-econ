"""Standard wording for chart footers."""

import pandas as pd

# lfooter wording for each ABS series type. A chart comparing seasonally adjusted with
# trend needs no note: its legend says so.
SERIES_TYPE_NOTES = {
    "Original": "Original series.",
    "Seasonally Adjusted": "Seasonally adjusted.",
    "Trend": "Trend.",
}


def data_to(data: pd.Series | pd.DataFrame) -> str:
    """Return the lfooter note naming the last period with data ("Data to 2026Q2.")."""
    present = data.dropna() if isinstance(data, pd.Series) else data.dropna(how="all")
    return f"Data to {present.index[-1]}."
