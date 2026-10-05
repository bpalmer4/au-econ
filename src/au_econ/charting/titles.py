"""Chart titles from ABS data item descriptions."""

from mgplot import abbreviate_state, state_names

TITLE_MEASURES = (  # removed from titles and noted in the footer instead
    "Chain volume measures",
    "Chain Volume Measures",
    "Chain Volume Measure",
    "Current prices",
    "Current Prices",
    "Current Price",
    "Total (State)",
    "Total (Industry)",
    "CORP",
    "TOTAL (SCP_SCOPE)",
)


def fix_abs_title(title: str, lfooter: str) -> tuple[str, str]:
    """Simplify an ABS data item description for a title, moving its price measure to the footer."""
    for measure in TITLE_MEASURES:
        if measure in title:
            title = title.replace(f"{measure} ;", "")
            lfooter += f"{measure}. "
    for state in state_names:
        title = title.replace(state, abbreviate_state(state))
    title = (
        title.replace(";", "")
        .replace(" - ", " ")
        .replace("    ", " ")
        .replace("   ", " ")
        .replace("  ", " ")
        .strip()
        .removesuffix(":")  # left behind when the price measure was the last part
        .strip()
    )
    return title, lfooter
