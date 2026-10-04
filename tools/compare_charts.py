"""Compare same-named PNGs in two folders: differing pixel counts and files present in one only."""

import sys
from pathlib import Path

import numpy as np
from PIL import Image

a, b = Path(sys.argv[1]), Path(sys.argv[2])
names_a, names_b = {p.name for p in a.glob("*.png")}, {p.name for p in b.glob("*.png")}
for name in sorted(names_a - names_b):
    print("only in", a, name)
for name in sorted(names_b - names_a):
    print("only in", b, name)
same = 0
for name in sorted(names_a & names_b):
    x, y = np.asarray(Image.open(a / name)), np.asarray(Image.open(b / name))
    if x.shape != y.shape:
        print("SHAPE", name, x.shape, y.shape)
        continue
    diff = int((x != y).any(axis=-1).sum())
    if diff:
        print("DIFF", name, diff)
    else:
        same += 1
print(f"{same} of {len(names_a & names_b)} identical")


def bbox(name: str) -> None:
    """Print the bounding box (x0, y0, x1, y1) of the differing pixels in one chart."""
    x, y = np.asarray(Image.open(a / name)), np.asarray(Image.open(b / name))
    rows, cols = np.nonzero((x != y).any(axis=-1))
    print(name, "rows", rows.min(), rows.max(), "cols", cols.min(), cols.max(), "of", x.shape[:2])


for name in sys.argv[3:]:
    bbox(name)
