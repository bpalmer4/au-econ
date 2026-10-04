"""Redraw a chart module with mgplot's 0.3.0 palette, to test whether the palette explains diffs with a notebook.

Usage: uv run python tools/old_palette.py <module path, e.g. au_econ.releases.abs.families_6224> <out folder>
"""

import importlib
import sys
from pathlib import Path

import matplotlib as mpl

mpl.use("Agg")
import mgplot as mg

OLD_COLORS = {  # mgplot 0.3.0 defaults, before the 2026-10-02 palette change
    1: ["blue"],
    5: ["darkblue", "darkorange", "cornflowerblue", "brown", "gray"],
    9: [
        "darkblue",
        "darkorange",
        "forestgreen",
        "#dd0000",
        "purple",
        "gold",
        "lightcoral",
        "lightseagreen",
        "gray",
    ],
}
module = importlib.import_module(sys.argv[1])
out = Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
mg.set_chart_dir(str(out) + "/")
mg.set_setting("colors", OLD_COLORS)
data = module.fetch()
for function, _names in module.CHARTS:
    function(data)
