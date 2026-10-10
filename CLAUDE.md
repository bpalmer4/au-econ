# Claude Code Project Configuration

## Project Overview
Charts of Australian economic and social statistics, from the latest data published by the
ABS, the RBA and other sources (OECD, BIS, FRED, World Bank, DB.nomics, Yahoo, EIA, and
Australian agencies). The charts come from the Python package `src/au_econ/`, run with
`uv run run.py <name>`. How it works, its decisions and what is still to do are in
`docs/how-it-works.md`.

## Running
```bash
uv run run.py --list            # every module, with its release names and topics
uv run run.py cpi               # one module, by release name or catalogue number (6401)
uv run run.py economy           # a topic: every module in it
uv run run.py somp --list       # the charts in a module
uv run run.py rba-fx --charts long_run_exchange_rates   # selected charts only
uv run run.py --topics          # the topic words
uv run run.py --variables       # the shared short names for --charts
uv run run.py --all             # everything
uv run run.py --all --check     # test run into scratch/check/; CHARTS/ untouched
```
Each module writes to `CHARTS/<first release name> - <TITLE>/`; a topic run writes to
`CHARTS/<topic>/<first release name> - <TITLE>/`. A full run of a module
clears its folder only after `fetch()` succeeds, so an unreachable source keeps the old
charts; a `--charts` run clears nothing. API keys live in `KEYS/`, downloads are cached in
`CACHE/` (both gitignored). The user-facing guides are `README.md` (how-to) and
`docs/how-it-works.md` (explainer); keep them in step with any change to the runner or the
conventions.

## Development Setup
- Python environment managed with uv (`uv sync`); virtual environment in `.venv/`.
- Lint and type checks: `uv run ruff check`, `uv run ruff format`, `uv run mypy src/au_econ`.

## Package layout and layers
```
src/au_econ/
  paths.py  runner.py  run_sets.py (topics)  variables.py (short names for --charts)
  sources/    one file per provider: fetching, caching, parsing; no combining
  series/     economic concepts wanted by more than one module (cached getters)
  analysis/   transforms: decompose, henderson, government epochs
  charting/   mgplot helpers: footers, windows, titles, targets, backplane, epochs
  releases/   one module (or subpackage) per publication, e.g. releases/abs/
  topics/     chart sets that combine publications or providers
```
Imports point down only: `releases`/`topics` → `charting`, `series` → `analysis`,
`sources`. `analysis` imports no first-party code; `sources` only `paths` and
`http_cache`; releases and topics never import each other. Logic shared by two modules
moves down to `series/` or `charting/`. A calculation that combines providers lives in
`series/`, in a function named for what the result means. Chart modules never call
`requests.get` or read a URL themselves: that belongs in `sources/`.

## Chart modules
Fixed section order, marked by comments: docstring, `# --- dependencies`,
`# --- module contract`, `# --- constants`, `# --- data`, `# --- charts`,
`# --- table of contents, in run order`.
- `RELEASE`: tuple of lowercase names, release number first (`("6202", "lfs")`); a topic
  module has just its run name (`("recessions",)`). Names are unique across modules.
- `TOPICS`: words from `run_sets.TOPICS`; a new word is added there, with its meaning,
  the first time a module uses it.
- `TITLE`: short readable name; the chart folder is `<first release name> - <TITLE>`.
- `fetch()`: no arguments; returns what every chart function receives (`AbsRelease` for
  ABS releases, a frozen dataclass when the module parses its own data). Validates what it
  fetched. Importing a module must never fetch.
- Chart functions take the `fetch()` result and return `None`; they are named for their
  subject (`unemployment`, not `plot_unemployment`); they raise on failure.
- `CHARTS = ((function, extra_short_names), ...)`. The second element is short names for
  `--charts`, never arguments.
- Large modules become a subpackage: `__init__.py` holds the contract and gathers
  `CHARTS`; each file holds chart functions and its own `CHARTS`; shared pieces go in
  `common.py`, which must not define `fetch` (the runner would treat it as a module).
- File names: `<short_name>_<catalogue>.py` (`labour_force_6202.py`).
- No `SHOW`, no `show=`.

## Coding practice

- Think Before Coding: Don't assume. Don't hide confusion. Surface tradeoffs.
- Simplicity First: Minimum code that solves the problem. Nothing speculative.
- Surgical Changes: Touch only what you must. Clean up only your own mess.
- Goal-Driven Execution: Define success criteria. Loop until verified.
- One concern per change: Do what was asked and nothing else. Lint, formatting and
  unrelated tidy-ups are separate pieces of work - raise them, never bundle them in.
  For lines the task did not require you to touch, this overrides the global instruction
  to fix pre-existing lint errors in files you are working on.
- Do not over-correct: If told a change was out of scope, stop there - do not then revert
  it unasked. The revert is itself another unrequested change, and it throws away the
  verification the work had already passed. Ask which way to go.
- Check rewritten lines against all of CLAUDE.md: after a refactor every line you rewrote
  is yours, so check it against the whole file - Data Handling and Charting included -
  not just the rules that prompted the refactor. Narrow framing is how conventions
  outside the current task get missed.
- **Functions, not classes**: a class only where it is plainly the obvious model (a frozen
  dataclass holding fetched data is). Data passes as arguments; no module-level state
  beyond constants.
- **No magic numbers**: named UPPER_CASE constants. The chart window names
  (`plot_times`, `quarterly_plot_times`, `monthly_plot_times`) stay lowercase.
- **No duplicate code**: two functions that differ only in their series and title are one
  function with arguments; logic used by two modules moves to `series/` or `charting/`.
- **Small private helpers** (leading underscore) sit above the chart functions that use them.
- **Cached getters**: a `series/` getter caches a private `@functools.cache` function and
  returns a copy, so a caller cannot corrupt the cache.
- **Diagnostic prints** that report data state to the reader (splice reports, recency,
  "latest ...") are deliberate and stay.
- **Docstrings say what the code does now**; never narrate a change.

## Data Handling
- **Series by label, never by ID in code**: ABS series are selected by description
  (`find_abs_id` / `select` / `search_abs_meta` with `metacol` selectors) - never store an
  ABS series ID, not even in a table. Providers whose APIs select only by ID (FRED,
  DB.nomics, OECD, RBA, EIA) keep their IDs in one `{label: ID}` table per module, and code
  reaches an ID only through its label.
- **Never launder an existing hardcoded ID**: resolve it by description or leave the line
  byte-for-byte as found. Do not promote it to a constant, rename, relocate or comment it.
- **Recalibrate units before plotting**: `ra.recalibrate()` for human-readable units; fix
  big-number labels there, not in plot formatting.
- **Validate fetched data**: check for empty frames or unexpected nulls inside the fetch
  function, next to the fetch it guards.
- **COVID year exclusion in decomposition**: `ignore_years=(2020, 2021)` when seasonal
  estimates would be distorted.
- **Splicing**: `ra.select` / `ra.splice` (see the readabs reference below); `rebase=True`
  only for ratio-scale indexes; audit the splice report.
- **readabs exceptions**: readabs raises its own `HttpError` and `CacheError`
  (`readabs.download_cache`), which are not `OSError`.

## Charting conventions
- **mgplot only**: never pandas `.plot()`. Prefer `*_finalise` functions; layer with
  `ax=` and close with `finalise_plot()` for composite charts.
- **Left footer**: starts "Australia. " (state charts too: the state is in the title),
  then the series type in standard wording from `charting.footers.SERIES_TYPE_NOTES`
  ("Original series.", "Seasonally adjusted.", "Trend."), then "Chain volume measures." or
  "Current prices." where it applies, then other notes, appended on the right. An SA
  against trend chart needs no series-type note.
- **Right footer**: the source only, no table numbers, no closing full stop. One prefix per
  provider, catalogues sorted, providers separated by semicolons, ABS first:
  `ABS: 6345.0, 6401.0; RBA: F1`. "Census" (and similar non-catalogue sources) last.
- **Acronyms**: define an acronym in the lfooter only when it appears in the title.
- **Titles**: colons, never " - " or em dashes.
- **Footer collisions**: check grown footers with `tools/footer_gaps.py`; shorten notes
  ("seas adj", "orig" are fine when tight) rather than let them collide.
- **Windows**: quarterly recent window `charting.windows.quarterly_plot_times` (five
  years); `monthly_plot_times` (18 months) for monthly annotated bar-and-line charts;
  monthly line charts keep their own windows. Never pass a literal to `starts=`.
- **Line widths**: left to mgplot (2.0 up to 151 points, 1.0 beyond). `width=` only to
  give the lines of one chart different widths, to highlight one.
- **Colours**: mgplot defaults. Purposeful ties (a series keeping one colour across charts)
  come from `mgplot.utilities.get_color_list`. State colours, party colours,
  Males cornflowerblue / Females hotpink, and gradients are kept.
- **Units on dollar flows**: "/Quarter" (or per month) on flow y-axes.
- **Showing a chart** to the user means `open` on the PNG.

## Verifying changes
- A chart change is verified by pixel comparison, with a predicted footprint stated first
  (which charts, which part: title band, footer strip, plot area):
  `tools/pass.sh <module path> <run name> "<chart folder under CHARTS/>"` lints, snapshots
  the folder to `scratch/prev`, reruns and reports the changed regions.
- `tools/compare_charts.py <dir a> <dir b>` compares two chart folders;
  `tools/footer_gaps.py <dir>` reports footer clearances.
- A refactor that should change nothing is verified as "N of N identical".
- `scratch/` is gitignored throwaway.

## Shared getters and helpers (`series/`, `analysis/`, `charting/`)
Every getter is cached for the run and returns copies. Most return `(series, units)` or
`(series, units, series_type)`.

| Module | Getters / helpers |
|---|---|
| `series.gdp` | `get_gdp(measure="CP"\|"CVM", series_type="SA"\|"T"\|"O")`, `get_table(table)` (any 5206 table), `get_compensation_per_hour` |
| `series.prices` | `get_cpi("headline"\|"headline_sa"\|"trimmed"\|"weighted")`, `get_monthly_cpi` (+ splice report), `get_living_cost_index`, `get_wage_index("WPI"\|"AWOTE")`, `get_price_deflator("DFD"\|"GNE"\|"HFCE"\|"GDP")` |
| `series.population` | `get_erp`, `get_state_erp`, `get_implicit_population`, `get_civ15(state)`, `get_adult21`, `get_adult21_monthly`, `smoothed_monthly_pop_growth`, `interp_21_share`, `interp_civ15_to_total`, `erp_age_sum`, `get_smoothed_civ15_gap` |
| `series.nom` | `get_nom`, `get_nom_forward_proxy`, `get_civ15_migration_split`, `get_nom_by_age`, `get_population_growth_proxy` |
| `series.labour` | `get_unemployment_rate` (spliced to 1950, + splice report and backcast stats) |
| `series.productivity` | `get_productivity_index` (GDP per hour worked to 1966, + splice report) |
| `series.housing` | `get_house_price_index(extend_bis=, real=, seasonally_adjusted=)`, splice report |
| `series.rates` | `get_cash_rate`, `get_daily_cash_rate`, `get_interbank_rate`, `get_aud_usd`, `get_aud_usd_monthly_average` |
| `analysis` | `decompose.decompose`, `decompose.seasonally_adjust`, `henderson.hma`, `epochs` (government table and by-government measures), `turning_points.local_extremes` |
| `charting` | `footers` (`SERIES_TYPE_NOTES`, `data_to`), `windows`, `titles.fix_abs_title`, `targets` (CPI target markers), `inflation_backplane`, `epochs.epoch_vlines`, `international`, `daily_prices`, `abs_rows`, `turning_points` (`label_extremes`, `turning_points_plot`) |
| `sources.abs` | `fetch_release(cat)` → `AbsRelease`, `get_pivot_cube`, `landing_page_workbook`; `sources.abs_workbook` parses the Excel-only GFS/taxation layout |

## readabs Package Reference

The `readabs` package (source in `~/readabs`) fetches ABS and RBA data. Key patterns:

### Efficient Data Fetching
```python
import readabs as ra
from readabs import metacol as mc

# ALWAYS use single_excel_only to fetch just one table (much faster)
data, meta = ra.read_abs_cat("6401.0", single_excel_only="64010Appendix1a")
```

### Finding Series by Description (robust to ID changes)
```python
_, series_id, _ = ra.find_abs_id(meta, {
    "64010Appendix1a": mc.table,
    "Index Numbers": mc.did,
    "All groups CPI, seasonally adjusted": mc.did,
})
series = data["64010Appendix1a"][series_id]
```

### metacol Column Names
- `mc.did` - Data Item Description
- `mc.id` - Series ID
- `mc.stype` - Series Type (Original, Seasonally Adjusted)
- `mc.table` - Table name
- `mc.unit` - Unit (Percent, Number, etc.)
- `mc.freq` - Frequency (Monthly, Quarterly)

### Key ABS Tables
- CPI Quarterly (Appendix): `64010Appendix1a` in catalog `6401.0`
- CPI Monthly: `640106` in catalog `6401.0`
- WPI: `634501` in catalog `6345.0`
- Labour Force: `62020001` in catalog `6202.0`
- National Accounts: `5206001_Key_Aggregates` in catalog `5206.0`

### Splicing Mixed-Frequency / Multi-Vintage Series (`select` + `splice`)

For a concept spread across frequencies/releases, use the four composable splice
functions. **Highest priority first**: the first segment wins on overlap; gaps are left
honest (no interpolation unless asked).

| Function | Role |
|----------|------|
| `select_one(data, meta, selector)` | One series from `(data, meta)`; ABS unit kept on `.attrs["unit"]` |
| `select(sources, *, require_same_units=True)` | Iterable of `(data, meta, selector)` → `list[Series]`; **raises on mixed units** unless `require_same_units=False` |
| `splice(segments, *, target=None, rebase=False, agg="mean", output=None, fill=None, name=None)` | Splice ordered series → `(series, report)` |
| `select_and_splice(sources, *, ...same splice kwargs..., require_same_units=True)` | `select` then `splice` (no-transform case) → `(series, unit, report)` |

- A *selector* is the `{search_value: column}` form used by `find_abs_id`.
- **`rebase`** (default `False`): multiplicatively rescales lower-priority segments onto the
  running result's level. ONLY for **ratio-scale / index-like** series across
  reference-period changes. WRONG for rates, balances, zero-crossing or additive series -
  splice the comparable values instead (e.g. Y/Y growth per source, `rebase=False`).
- `target` = common grid freq; `output` = optional final resample freq; `agg="mean"` for
  levels, `"sum"` for flows; `fill` is `None`/`"ffill"`/`"interpolate"`.
- The returned `report` DataFrame logs every rebase factor and overlap junction - audit it.

## mgplot Package Reference

The `mgplot` package (source in `~/mgplot`) wraps matplotlib for economic data charting.
**Prefer `*_finalise` functions** for simple single-layer charts. For composite charts,
layer mgplot functions with `ax=` chaining, then call `finalise_plot()`. Avoid raw
matplotlib (`ax.plot()`, `ax.fill_between()`, etc.) when an mgplot function exists.

### Architecture
```python
# Simple charts: use *_finalise (one-step convenience)
line_plot_finalise(data, **kwargs)        # line_plot() then finalise_plot()

# Composite charts: layer mgplot functions, then finalise
ax = fill_between_plot(band_data, color="red", alpha=0.1, label="90% CI")
line_plot(history, ax=ax, color=["navy"])
finalise_plot(ax, title="...", ylabel="...")

# finalise_plot() does NOT support plot-level kwargs like annotate, width, color.
```
The runner sets the chart directory; a module writes into a subfolder with
`with mg.chart_subdir("States"): ...`.

### All *_finalise Functions
```python
mg.line_plot_finalise(df, ...)           # Line charts
mg.bar_plot_finalise(df, ...)            # Bar charts (grouped or stacked)
mg.growth_plot_finalise(growth_df, ...)  # QoQ bars + TTY line
mg.series_growth_plot_finalise(s, ...)   # Calculates growth from index, then plots
mg.fill_between_plot_finalise(df, ...)   # Shaded area between two columns
mg.postcovid_plot_finalise(s, ...)       # Line with post-COVID projection
mg.revision_plot_finalise(df, ...)       # ABS data revisions
mg.run_plot_finalise(s, ...)             # Highlights runs in a series
mg.seastrend_plot_finalise(df, ...)      # Seasonal + trend overlay
mg.summary_plot_finalise(df, ...)        # Z-score summary (creates 2 plots)
```

### Line Plot Parameters (LineKwargs)
```python
mg.line_plot_finalise(
    data,                # Series or DataFrame (PeriodIndex or RangeIndex)
    width=2,             # Line width (float or list per series). NOT lw.
    color=["blue"],      # Colors (str or list per series)
    style="-",           # Line style (str or list)
    alpha=1.0, marker=None, markersize=None, drawstyle=None,
    annotate=True,       # Add endpoint value labels
    rounding=1, fontsize="small", annotate_color=None,
    plot_from=None,      # Start index (int offset or Period)
    label_series=None, dropna=True,
    # ... plus all Finalise kwargs below
)
```

### Finalise Parameters (FinaliseKwargs)
```python
title="Chart Title",       # Also used for the file name (sanitised to [a-z0-9-])
suptitle=..., ylabel=..., xlabel=...,
rfooter="ABS: 6401.0", lfooter="Australia. ", rheader="", lheader="",
xlim=..., ylim=..., xticks=..., yticks=...,
legend=True,               # or a dict of matplotlib legend kwargs
axhline={"y": 2.5, "color": "red", "linestyle": "--"},   # dict or list of dicts
axvline=..., axhspan=..., axvspan=...,
y0=True,                   # Horizontal line at y=0 if data crosses zero
tag="mytag", pre_tag="prefix",   # file name: prefix-title-mytag.png
file_type="png", dpi=300, figsize=(9, 4.5), dont_save=False, dont_close=False,
```

### Bar Plot Specific (BarKwargs)
```python
mg.bar_plot_finalise(df, stacked=False, annotate=True, width=0.8, above=True,
                     label_rotation=0, horizontal=False, color=[...])
```

### Multi-Plot Functions
```python
mg.multi_start(df, function=mg.line_plot_finalise, starts=quarterly_plot_times, title="Chart")
mg.multi_column(df, function=mg.line_plot_finalise, title="Chart")
mg.plot_then_finalise(data, function=mg.line_plot, title="Chart")
```

### Utility Functions
```python
mg.get_color("NSW")              # State / party colour
mg.abbreviate_state("Victoria")  # → "Vic."
mg.colorise_list(parties)        # party colours for a list
mg.contrast("blue")              # Contrasting color for text
```
A log y-axis needs `line_plot` + `ax.set_yscale("log")` + explicit `set_yticks` before
`finalise_plot`; `yscale=` alone gives scientific-notation labels and no gridlines.
