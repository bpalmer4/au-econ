# Type stubs for the parts of adjustText this project uses (adjustText ships no type information).
# Add a declaration here when the package starts using another part of adjustText.

from typing import Any

from matplotlib.axes import Axes
from matplotlib.text import Text

def adjust_text(
    texts: list[Text],
    *,
    ax: Axes | None = None,
    arrowprops: dict[str, Any] | None = ...,
) -> Any: ...
