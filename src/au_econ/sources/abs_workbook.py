"""Parsing for ABS Excel-only annual releases laid out for reading (5506.0, 5512.0).

Each release is a set of workbooks whose identifier changes every release, so a workbook is
found by what its Contents sheet says. In a table, column 0 holds the row label and the other
columns one financial year each, labelled "2015-16" on a header row; the units row follows it.
"""

# --- dependencies
from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:
    from collections.abc import Callable

# --- constants
YEAR_LABEL_LENGTH = 7  # "2015-16"
YEARS_TO_TEST = 3
UNIT_NAMES = {
    "$m": "Dollars (Millions)",
    "$M": "Dollars (Millions)",
    "$b": "Dollars (Billions)",
    "$B": "Dollars (Billions)",
    "$": "Dollars",
}


def find_workbook(tables: dict[str, pd.DataFrame], matches: Callable[[str], bool]) -> str:
    """Return the prefix of the first workbook (in name order) with a Contents cell that matches."""
    for prefix in sorted({k.split("---")[0] for k in tables}):
        contents = tables.get(f"{prefix}---Contents")
        if contents is None:
            continue
        for cell in contents.to_numpy().flatten():
            if isinstance(cell, str) and matches(cell):
                return prefix
    raise KeyError("No workbook's Contents sheet matched")


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    """Drop empty rows and columns, keeping the original row labels."""
    return raw.dropna(how="all").dropna(axis=1, how="all")


def header_row(raw: pd.DataFrame) -> int:
    """Return the label of the row holding the financial-year headers ('2015-16' after the label column)."""
    for index, row in raw.iterrows():
        labels = [str(v) for v in row.to_numpy()[1:] if isinstance(v, str)]
        if labels and all("-" in v and len(v) == YEAR_LABEL_LENGTH for v in labels[:YEARS_TO_TEST]):
            if not isinstance(index, int):
                raise TypeError(f"Expected an integer row index, got {type(index).__name__}")
            return index
    raise ValueError("No financial-year header row")


def row_values(raw: pd.DataFrame, label: int) -> list[Any]:
    """Return the values after the label column of the row with this index label."""
    return raw[raw.index == label].iloc[0].iloc[1:].tolist()


def financial_years(labels: list[Any]) -> list[pd.Period]:
    """Map '2015-16' to the year ending June 2016."""
    return [pd.Period(str(int(str(y).split("-")[0]) + 1), freq="Y-JUN") for y in labels]


def long_units(units: str) -> str:
    """Map an ABS short unit ('$m') to the long form ra.recalibrate understands."""
    return UNIT_NAMES.get(units.strip(), units)
