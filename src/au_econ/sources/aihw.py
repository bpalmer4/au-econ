"""AIHW: the Family, domestic and sexual violence (FDSV) all-data workbook.

One workbook carries the AIHW's collation of several collections, each on its own sheet:
the AIC National Homicide Monitoring Program (NHMP), the National Hospital Morbidity
Database (NHMD) and ABS Recorded Crime - Victims (RCV). Downloaded through http_cache.
"""

import io

import pandas as pd

from au_econ.sources.http_cache import BROWSER_HEADERS, get_file

FDSV_URL = "https://www.aihw.gov.au/getmedia/f4a9196a-9797-4b03-acc8-d72a5b83d370/AIHW-FDSV-all-data-download.xlsx"


def get_fdsv_sheet(sheet: str, header: int) -> pd.DataFrame:
    """Return one sheet of the FDSV workbook (e.g. "NHMP 2"), with its column headers on row `header`."""
    content = get_file(FDSV_URL, prefix="aihw", headers=BROWSER_HEADERS)
    frame = pd.read_excel(io.BytesIO(content), sheet_name=sheet, header=header)
    if frame.empty:
        raise ValueError(f"AIHW FDSV {sheet}: no rows")
    return frame
