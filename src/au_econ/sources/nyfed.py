"""New York Fed: the ACM Treasury term premium, and the Global Supply Chain Pressure Index (GSCPI).

The ACM series are the Adrian-Crump-Moench term premium decomposition of the US Treasury
curve. Each is read from the Fed's workbook. The server sends no Last-Modified (a Last-Modified rule
would serve the first download forever), so the workbooks are cached for RECENT_MAX_AGE, with
the cached copy as a fallback when a download fails.
"""

import io

import pandas as pd

from au_econ.sources.http_cache import RECENT_MAX_AGE, get_recent

ACM_URL = "https://www.newyorkfed.org/medialibrary/media/research/data_indicators/ACMTermPremium.xls"
DAILY_SHEET = "ACM Daily"  # named: "ACM Monthly" comes first in the workbook
GSCPI_URL = "https://www.newyorkfed.org/medialibrary/research/interactives/gscpi/downloads/gscpi_data.xlsx"
GSCPI_SHEET = "GSCPI Monthly Data"  # named: "GSCPI Overview" comes first in the workbook
GSCPI_COLUMN = "GSCPI"


def get_acm_daily() -> pd.DataFrame:
    """Return the ACM daily sheet (e.g. ACMRNY05, ACMRNY10), numeric, on a DatetimeIndex."""
    workbook = get_recent(ACM_URL, None, "nyfed", RECENT_MAX_AGE, fallback=True)
    frame = pd.read_excel(io.BytesIO(workbook), sheet_name=DAILY_SHEET)
    dates = pd.to_datetime(frame["DATE"], format="%d-%b-%Y", errors="coerce")  # anything else is a footer row
    frame = frame.loc[dates.notna()].copy()
    frame.index = pd.DatetimeIndex(dates.loc[dates.notna()])
    frame = frame.drop(columns="DATE").apply(pd.to_numeric, errors="coerce")
    if frame.empty:
        raise ValueError(f"The NY Fed {DAILY_SHEET} sheet holds no dated rows")
    return frame


def get_gscpi() -> pd.Series:
    """Return the GSCPI (standard deviations from its average), numeric, on a monthly PeriodIndex."""
    workbook = get_recent(GSCPI_URL, None, "nyfed", RECENT_MAX_AGE, fallback=True)
    frame = pd.read_excel(io.BytesIO(workbook), sheet_name=GSCPI_SHEET)
    dates = pd.to_datetime(frame["Date"], format="%d-%b-%Y", errors="coerce")  # anything else is a banner row
    values = pd.to_numeric(frame.loc[dates.notna(), GSCPI_COLUMN], errors="coerce")
    months = pd.PeriodIndex(dates.loc[dates.notna()], freq="M")
    series = pd.Series(values.to_numpy(), index=months, name=GSCPI_COLUMN).dropna()
    if series.empty:
        raise ValueError(f"The NY Fed {GSCPI_SHEET} sheet holds no dated rows")
    return series
