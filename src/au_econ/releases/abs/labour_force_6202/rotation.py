"""Labour Force charts of the rotation groups: the incoming group against the one it replaced.

An eighth of the Labour Force sample is replaced each month. Each release's commentary reports
the incoming group, the outgoing group it replaced (the previous month's outgoing group) and
the published estimate (Original), from July 2020; sources.abs.get_rotation_groups reads them.
"""

# --- dependencies
from mgplot import bar_plot_finalise, line_plot_finalise

from au_econ.charting.footers import SERIES_TYPE_NOTES
from au_econ.releases.abs.labour_force_6202.common import ORIGINAL
from au_econ.sources.abs import ESTIMATE, INCOMING, OUTGOING, REPLACED, get_rotation_groups
lazy from au_econ.sources.abs import AbsRelease

# --- constants
UNEMPLOYMENT = "Unemployment rate"
GROUP = "Group"  # the index level naming the rotation group
GROUP_LABELS = {
    INCOMING: "Incoming group",
    REPLACED: "Replaced group (previous month's outgoing)",
    OUTGOING: "Outgoing group",
    ESTIMATE: "Published estimate",
}
LFOOTER = f"Australia. {SERIES_TYPE_NOTES[ORIGINAL]} Rotation groups from the ABS release commentary. "
NO_REPLACED_NOTE = "No outgoing group in Jul 2026, so none replaced in Aug. "
AVERAGE_LINE = {"color": "black", "linestyle": "--", "linewidth": 0.75}
ZERO_LINE = {"x": 0, "color": "black", "linewidth": 0.75}


# --- charts
def rotation_unemployment(release: AbsRelease) -> None:
    """Unemployment rate of the incoming rotation group, the group it replaced and the estimate; and the gap."""
    rates = get_rotation_groups()[UNEMPLOYMENT].unstack(GROUP)
    shown = (INCOMING, REPLACED, ESTIMATE)
    line_plot_finalise(
        rates[list(shown)].rename(columns=GROUP_LABELS),
        title="Unemployment Rate: Incoming and Replaced Rotation Groups",
        ylabel="Per cent",
        annotate=True,
        rounding=1,
        legend={"loc": "best", "fontsize": "x-small"},
        lfooter=LFOOTER,
        rfooter=release.source,
    )
    gap = (rates[INCOMING] - rates[REPLACED]).rename("Incoming less replaced group")
    average = gap.mean()
    bar_plot_finalise(
        gap,
        title="Unemployment Rate: Incoming less Replaced Rotation Group",
        ylabel="Percentage points",
        annotate=False,
        axhline={"y": average, **AVERAGE_LINE, "label": f"Average {average:.2f}pp"},
        legend={"loc": "best", "fontsize": "x-small"},
        lfooter=f"{LFOOTER}{NO_REPLACED_NOTE}",
        rfooter=release.source,
    )


def rotation_latest(release: AbsRelease) -> None:
    """Each rotation group less the published estimate, for every measure, in the latest month."""
    groups = get_rotation_groups()
    month = groups.index.get_level_values("Month").max()
    latest = groups.loc[month]
    if ESTIMATE not in latest.index:
        raise ValueError(f"ABS rotation groups {month}: no published estimate")
    difference = (latest.drop(index=ESTIMATE) - latest.loc[ESTIMATE]).T.rename(columns=GROUP_LABELS)
    bar_plot_finalise(
        difference,
        horizontal=True,
        annotate=True,
        rounding=1,
        title=f"Rotation Groups less the Published Estimate:\n{month.strftime('%b %Y')}",
        xlabel="Percentage points",
        axvline=ZERO_LINE,
        legend={"loc": "best", "fontsize": "x-small"},
        lfooter=LFOOTER,
        rfooter=release.source,
    )


# --- table of contents, in run order
CHARTS = (
    (rotation_unemployment, ()),
    (rotation_latest, ()),
)
