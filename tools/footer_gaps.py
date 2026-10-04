"""Report the gap between the left and right footer text of each PNG in a folder; flag gaps under 40 px.

The footer strip is the bottom FOOTER_ROWS rows. Ink is any pixel with a channel below INK.
The widest blank run between the first and last inked columns is the left/right gap; a
gap of about a word space (~16 px at 2700 wide) means the footers overlap.
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image

FOOTER_ROWS, INK, TIGHT = 45, 200, 40
MIN_INKED = 2  # inked columns needed before there can be a gap between them

folder = Path(sys.argv[1])
names = sys.argv[2:] or sorted(p.name for p in folder.glob("*.png"))
for name in names:
    pixels = np.asarray(Image.open(folder / name).convert("RGB"))
    strip = pixels[-FOOTER_ROWS:]
    inked = np.nonzero((strip < INK).any(axis=-1).any(axis=0))[0]
    if len(inked) < MIN_INKED:
        print(f"{'NO TEXT':>9} {name}")
        continue
    gaps = np.diff(inked)
    widest = int(gaps.max()) - 1
    flag = "COLLISION" if widest < TIGHT else ""
    print(f"{widest:>6} px {flag:9} {name}")
