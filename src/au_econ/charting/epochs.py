"""Election markers for charts drawn by government epoch."""

import mgplot as mg
import pandas as pd
from pandas import DataFrame


def epoch_vlines(govts: DataFrame, freq: str, loc: str = "auto right") -> list[dict[str, object]]:
    """Return thin vertical lines at each election, carrying the epoch name, for finalise_plot().

    finalise_plot() treats "text"/"loc" in an axvline dict as a label for the line, taking
    the line's colour, so colouring the line by party colours the label to match. `loc`
    takes an edge ("auto", "top", "bottom") and a side ("left", "right"); "auto" sends each
    label to whichever end has more clearance near its own election.
    """
    return [
        {
            "x": pd.Period(row["start"], freq=freq).ordinal,
            "text": str(name),
            "loc": loc,
            "color": mg.get_color(row["party"]),
            "linewidth": 0.5,
        }
        for name, row in govts.iterrows()
    ]
