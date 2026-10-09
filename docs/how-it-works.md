# How au-econ works

This explains how the code is organised, what happens when you type `uv run run.py ...`,
how to add a new chart or series, and the conventions the charts follow. For everyday
commands and troubleshooting, see the [README](../README.md). The full design record,
with every decision and conversion, is [restructure-spec.md](restructure-spec.md).

## 1. The big picture

Everything lives in one Python package, `src/au_econ/`. Data flows down a short chain:

```
provider website / API  ->  sources/   (download, cache, parse; one file per provider)
                         ->  series/    (named economic concepts, e.g. "the cash rate")
                         ->  analysis/  (pure transforms: seasonal adjustment, epochs)
                         ->  releases/ and topics/  (the chart modules: one per publication
                                                     or theme; they draw the PNGs)
                              charting/ (shared chart pieces: footers, windows, markers)
```

`run.py` is a thin wrapper around `au_econ/runner.py`. The runner finds every chart
module, checks it, picks the ones you asked for, fetches their data and calls their chart
functions. Each chart function draws PNG files with `mgplot` (a wrapper around
matplotlib) into `CHARTS/`.

## 2. Where things are

```
au-econ/
  run.py                     the command: uv run run.py <name>
  CHARTS/                    every chart the package draws
  CACHE/                     downloaded files (http_cache); safe to delete, refetched
  .readabs_cache/            ABS and RBA files cached by readabs; safe to delete
  KEYS/                      API keys: fred.api, EIA-API-KEY.txt (never commit these)
  LOGS/                      output of the weekly launchd job
  scratch/                   throwaway work; scratch/check/ holds --check runs
  tools/                     chart comparison and footer checks (section 9)
  docs/                      this file and the design spec
  notebooks/                 the old Jupyter world, frozen; never edit
  src/au_econ/
    paths.py                 every folder location, anchored to the project root
    runner.py                discovery, selection, clearing, running, summary
    run_sets.py              the topic words (economy, jobs, prices, ...)
    variables.py             shared short names for --charts (currently empty)
    sources/                 one file per provider: abs.py, rba.py, fred.py, oecd.py, ...
    series/                  gdp.py, prices.py, population.py, labour.py, rates.py, ...
    analysis/                decompose.py, henderson.py, epochs.py, turning_points.py
    charting/                footers.py, windows.py, titles.py, targets.py, ...
    releases/abs/            one module per ABS publication, e.g. labour_force_6202/
    releases/rba/, oecd/, fred/, ...   publications from other providers
    topics/                  cross-source chart sets, e.g. recessions.py, political/
```

### What each directory holds

The directories under `src/au_econ/` are layers; the import rules between them are in
section 4.

- **`sources/`: getting raw data.** One file per provider: `abs.py`, `rba.py`, `fred.py`,
  `oecd.py`, `yahoo.py`, `eia.py`, `bis.py`, `nyfed.py`, `opec.py`, `bundesbank.py`,
  `boe.py`, `chinabond.py` and others. Each fetches, caches and parses one provider's data
  and never combines it with another's. This is the only place that touches URLs.
  `http_cache.py` is the download cache; `abs_workbook.py` parses the Excel-only GFS and
  taxation workbooks.
- **`analysis/`: pure transforms.** Maths that does not care where the data came from:
  `decompose.py` (seasonal adjustment, with the auto-ARIMA extension), `henderson.py`
  (Henderson moving averages), `epochs.py` (the table of governments and measures by
  government), `turning_points.py`.
- **`series/`: shared economic concepts.** When more than one chart module needs the same
  concept, it gets a cached getter here: GDP (`gdp.py`), the CPI, wages and deflators
  (`prices.py`), population and NOM (`population.py`, `nom.py`), the long-run
  unemployment rate (`labour.py`), productivity, house prices (`housing.py`), the cash rate
  and the AUD (`rates.py`). A calculation that combines providers also lives here, named
  for what the result means. Getters are cached for the run and return copies.
- **`charting/`: shared chart pieces.** The furniture the chart modules share:
  `footers.py` (standard series-type wording, "data to"), `windows.py`
  (`quarterly_plot_times` and the other windows), `titles.py`, `targets.py` (CPI target
  markers), `inflation_backplane.py`, `epochs.py` (vertical lines at changes of
  government), `international.py`, `daily_prices.py`, `abs_rows.py`, `turning_points.py`.
- **`releases/`: one module per publication.** The chart modules, grouped by publisher.
  `abs/` holds the ABS catalogues, each named `<subject>_<catalogue>.py`
  (`wage_price_index_6345.py`); the big ones are subpackages, such as
  `consumer_price_index_6401/`, `labour_force_6202/` and `national_accounts_5206/`.
  `rba/` holds exchange rates, interest rates, bond yields, money and credit, and the SoMP
  forecasts; `oecd/` unemployment, inflation, population, GDP, business R&D and government
  debt. Smaller providers have a folder each: `fred/`, `worldbank/`, `bis/`, `nyfed/`,
  `aip/`, `asic/`, `afsa/`, `dcceew/`.
- **`topics/`: chart sets that span publications.** Modules tied to no single release,
  because they combine publications or providers: `recessions.py`, `stagflation.py`,
  `neutral_rate.py`, `au_vs_us.py`, `bond_yields.py`, `energy_markets.py`,
  `house_price_drawdowns.py`, `wage_measures.py`, and the `political/` subpackage.

Every module in `releases/` and `topics/` follows the same contract (section 5).

## 3. What `run.py` does

`uv run run.py lfs` runs these steps:

1. **Parse the command line.** One run set (a release name such as `lfs`, a release
   number such as `6202`, or a topic such as `jobs`), or `--all`. Options: `--charts` (run
   only some charts), `--check` (a test run), `--list`, `--topics`.
2. **Set up.** Matplotlib is put in file-only mode (no windows; this is also what lets the
   weekly launchd job run). The cache folders are set before anything is imported, so
   readabs uses `.readabs_cache/`.
3. **Discover.** Every module under `releases/` and `topics/` is imported and its contract
   is read: `RELEASE`, `TOPICS`, `TITLE`, `fetch` and `CHARTS` (section 5). Importing a
   module must not fetch anything, so this is quick.
4. **Check the contracts.** Release names must be unique; every topic word must be in
   `run_sets.TOPICS`; every `CHARTS` entry must be well formed. If anything is wrong the
   runner lists the problems and stops before touching any chart.
5. **Select.** Your run set picks modules: a release name or number picks one module, a
   topic picks every module that lists it. `--charts` narrows to named chart functions.
6. **Run each module, one at a time:**
   - **Fetch.** `fetch()` is called once. If it fails (site blocked, server down, a table
     renamed), the module is marked FAIL and its existing charts are **left as they were**.
   - **Clear.** Only after a successful fetch, and only on a full run (not `--charts`), the
     images in the module's folder are deleted, so charts the module no longer draws do not
     linger.
   - **Draw.** Each chart function in `CHARTS` is called with what `fetch()` returned. A
     chart that fails is recorded; the others still run.
7. **Summarise.** One line per module: `ok` with its chart count, or `FAIL` with each
   failed chart and the reason. The exit code is 0 if everything worked, 1 if anything
   failed, 2 if the run was refused.

### Where the charts go

- A release or `--all` run: `CHARTS/<first release name> - <TITLE>/`, e.g.
  `CHARTS/6202 - Labour Force/`.
- A topic run: `CHARTS/<topic>/<first release name> - <TITLE>/`, e.g.
  `CHARTS/jobs/6202 - Labour Force/`. On a full topic run, folders in `CHARTS/<topic>/`
  that belong to no module in the topic (a module that has since left it) are emptied.
- Large modules write some charts into subfolders (`mg.chart_subdir("States")`).

### The check run (`--check`)

`--check` is a complete test run that cannot harm your charts. It does everything a normal
run does, but draws into `scratch/check/` instead of `CHARTS/`, and empties
`scratch/check/` at the start so what you see afterwards is only this run's work.
`CHARTS/` is never read, cleared or written.

It draws rather than only fetching because a module's data does not all come through
`fetch()`. Many chart functions call shared getters themselves (the CPI, population, the
cash rate), so the only way to be sure every source is reachable is to run every chart.
The summary at the end tells you which modules worked; a `FAIL ... fetch() failed:` line
names the source that could not be reached.

Typical uses: `uv run run.py --all --check` before travelling or after a change to a
shared getter; `uv run run.py economy --check` for one topic.

## 4. Layers and why

Imports only point down the chain in section 1:

- `sources/` imports nothing of ours except `paths` and `http_cache`.
- `series/` may use `sources/` and `analysis/`.
- `analysis/` imports nothing of ours (pure pandas/numpy).
- `charting/` may use `series/` where a chart element needs data (the inflation backplane).
- `releases/` and `topics/` may use anything below them, but **never each other**.

Why: when the ABS renames a table, the fix is in one place. When two modules need the CPI,
they call the same cached getter instead of each parsing the CPI their own way. When a
chart module breaks, nothing else breaks with it.

Rules of thumb:
- *How to get data from a website* belongs in `sources/`. Chart modules never call
  `requests.get` or read a URL themselves.
- *A series wanted by two or more modules* gets a named getter in `series/`.
- *A calculation that combines providers* (an ABS series divided by an RBA series) lives in
  `series/`, in a function named for what the result means.
- *Logic used by two chart modules* moves to `charting/` (or `series/`).

### Caching

- **On disk, across runs.** Both caches ask the server whether it has a newer file (its
  `Last-Modified` date) and download only if so. They differ when the server cannot be
  reached:
  - readabs (ABS and RBA, cached in `.readabs_cache/`) falls back to the cached copy and
    prints `WARNING: could not download fresh data ... this data may be out of date.` The
    charts still draw, from the last data you downloaded.
  - `sources/http_cache.py` (FRED, OECD, BIS, World Bank, DB.nomics and the other
    providers, cached in `CACHE/`) mostly raises instead, so those modules FAIL. A few
    sources ask it for a fallback (`fallback=True`) and use the cached copy.
- **In memory, within one run.** The `series/` getters are cached with
  `functools.cache`, so ten modules asking for the cash rate in one run download it once.
  They return copies, so a chart that changes its data cannot corrupt the cache.

## 5. A chart module

Every module looks like this, in this order:

```python
"""Example Release (1234.0): what the charts show, in one line."""

# --- dependencies
import mgplot as mg
import readabs as ra
from readabs import metacol as mc

from au_econ.charting.footers import SERIES_TYPE_NOTES
from au_econ.charting.windows import quarterly_plot_times
from au_econ.sources.abs import AbsRelease, fetch_release

# --- module contract
RELEASE = ("1234", "example")     # release number, then a short name: run.py example
TOPICS = ("economy",)             # words from run_sets.TOPICS
TITLE = "Example Release"         # chart folder: CHARTS/1234 - Example Release/

# --- constants
CATALOGUE = "1234.0"
TABLE = "1234001"
HEADLINE_DID = "Something ;  Australia ;"   # a data item description, never a series ID
SA = "Seasonally Adjusted"


# --- data
def fetch() -> AbsRelease:
    """Fetch the release once; every chart function receives it."""
    return fetch_release(CATALOGUE)


# --- charts
def headline(release: AbsRelease) -> None:
    """Chart the headline series: full history and the last five years."""
    selector = {TABLE: mc.table, HEADLINE_DID: mc.did, SA: mc.stype}
    table, series_id, units = ra.find_abs_id(release.meta, selector)
    series, units = ra.recalibrate(release.data[table][series_id], units)
    mg.multi_start(
        series,
        function=mg.line_plot_finalise,
        starts=quarterly_plot_times,
        title="Something: headline",
        ylabel=units,
        rfooter=release.source,                         # "ABS: 1234.0"
        lfooter=f"Australia. {SERIES_TYPE_NOTES[SA]} ",  # "Australia. Seasonally adjusted. "
    )


# --- table of contents, in run order
CHARTS = (
    (headline, ()),
)
```

The contract the runner checks:

- `RELEASE`: lowercase names, unique across all modules. A topic module has just its run
  name (`RELEASE = ("recessions",)`).
- `TOPICS`: each word must be in `src/au_econ/run_sets.py`; add a new word there, with its
  meaning, the first time you use it.
- `TITLE`: short and readable; no `/` or `:`.
- `fetch()`: no arguments. Returns whatever the charts need: `AbsRelease` (data
  dictionary, metadata, source label, recent date) for ABS releases; a small frozen
  dataclass when the module parses its own workbook; for a topic built on `series/`
  getters it can return almost nothing (Political returns the government table).
  It should fail loudly (raise) when the data are empty.
- Chart functions: take the `fetch()` result, return `None`, are named for their subject
  (`headline`, not `plot_headline`), and raise on failure.
- `CHARTS`: the module's table of contents, in run order. The second element of each pair
  is a tuple of extra short names for `--charts` (from `variables.py`); it is **not** a
  place for arguments. A chart that needs arguments becomes a small wrapper function.

Large modules become a subpackage (`releases/abs/national_accounts_5206/`): `__init__.py`
holds the contract and gathers `CHARTS = (*headline.CHARTS, *savings.CHARTS, ...)`; each
file holds chart functions and its own `CHARTS`; shared pieces go in `common.py`, which must
not define `fetch` (the runner would take it for a module).

## 6. Adding things

### A chart to an existing module

1. Write the chart function in the module (or the right file of its subpackage).
2. Add it to that file's `CHARTS`.
3. Run just that chart: `uv run run.py <module> --charts <function_name>`.
4. Check it (section 9), then run the whole module.

### A new ABS publication

1. Find the catalogue number and table names: `ra.read_abs_cat("1234.0")` once in a Python
   shell, or `uv run python -c "import readabs as ra; d, m = ra.read_abs_cat('1234.0');
   print(m[['Table', 'Data Item Description', 'Series Type']].drop_duplicates())"`.
2. Copy the template in section 5 to `src/au_econ/releases/abs/<short_name>_<number>.py`
   (e.g. `retail_trade_8501.py`).
3. Set `RELEASE`, `TOPICS`, `TITLE`, `CATALOGUE`, and the descriptions you need.
4. Select every series by its description (`find_abs_id` with `metacol` selectors). Never
   paste a series ID: the ABS changes them.
5. `uv run run.py --list` should now show it; then `uv run run.py <short name>`.
6. Lint and type-check (section 9).

An ABS release that is not in the time-series directory (Excel-only, e.g. 5512.0 or
5506.0) is read from its landing page: see `sources.abs.landing_page_workbook` and
`sources/abs_workbook.py`, and the 5512 and 5506 modules.

### A series wanted by more than one module

Put it in the right `series/` file (or a new one), following the existing pattern:

```python
@cache
def _thing() -> tuple[pd.Series, str]:
    """Fetch the thing (cached; not for mutation)."""
    data, meta = ra.read_abs_cat("1234.0", single_excel_only="1234001", verbose=False)
    ...
    if series.empty:
        raise ValueError("ABS 1234.0: no thing")
    return series, units


def get_thing() -> tuple[pd.Series, str]:
    """Return the thing, quarterly, and its units."""
    series, units = _thing()
    return series.copy(), units
```

### A new provider

Add `src/au_econ/sources/<provider>.py` that downloads through
`au_econ.sources.http_cache.get_file(url, params, prefix="<provider>")` and returns a
pandas object. Keep provider IDs (FRED codes, OECD keys) in a `{label: ID}` table in the
module that uses them, and look IDs up by label. API keys go in `KEYS/` and are read
through `paths.KEYS_DIR`.

### A topic module

Same shape as a release module, in `src/au_econ/topics/`, with
`RELEASE = ("<run name>",)`. Use it when the charts combine several publications or
providers (`recessions`, `au-vs-us`, `political`).

## 7. Conventions, and why

These keep a few thousand charts (from about 490 chart functions) consistent, so a reader
always knows where to look.

- **Left footer**: `Australia. ` first, then the series type in standard wording
  (`SERIES_TYPE_NOTES`: "Original series.", "Seasonally adjusted.", "Trend."), then
  "Chain volume measures." or "Current prices." where relevant, then any other notes.
  An SA-against-trend chart needs no series-type note; its legend says it.
- **Right footer**: the source only, no table numbers, no full stop. One prefix per
  provider, catalogues sorted, providers separated by semicolons, ABS first:
  `ABS: 6345.0, 6401.0; RBA: F1`. Non-catalogue sources ("Census") go last.
- **Acronyms**: define one in the left footer only if it appears in the title.
- **Titles**: colons, never " - " or dashes.
- **Footer collisions**: long footers can run into the right footer. `tools/footer_gaps.py`
  finds them; shorten the note.
- **Windows**: quarterly charts pair full history with the last five years
  (`charting.windows.quarterly_plot_times`); monthly bar-and-line growth charts use
  `monthly_plot_times` (18 months). Never write a literal like `starts=(0, -17)`.
- **Line widths**: leave them to mgplot (2.0 up to 151 points, 1.0 beyond). Set `width=`
  only to make one line stand out from the others in the same chart.
- **Colours**: mgplot's defaults. Deliberate colours are kept where they carry meaning:
  state colours, party colours, Males cornflowerblue / Females hotpink, colour gradients,
  and a colour tied to one series across a set of charts (`mgplot.utilities.get_color_list`).
- **Units**: recalibrate large numbers with `ra.recalibrate` (thousands, millions,
  billions) rather than formatting axes; dollar flows say "/Quarter" or "per month".
- **Data by description, never by ID**: ABS series are always selected by description.
  Other providers' IDs sit in a `{label: ID}` table, reached by label.
- **Seasonal adjustment**: `analysis.decompose.seasonally_adjust` (multiplicative,
  ARIMA-extended) for positive levels; pass `ignore_years=(2020, 2021)` to `decompose`
  where COVID would distort the seasonal factors.
- **mgplot only**: never pandas `.plot()`.

## 8. Code style

- Functions, not classes (a frozen dataclass to carry fetched data is fine).
- No magic numbers: named UPPER_CASE constants.
- No duplicated code: two functions that differ only in a series and a title become one
  function with arguments.
- Small private helpers (leading underscore) sit above the charts that use them.
- Docstrings say what the code does.
- Lint and types must pass: `uv run ruff check`, `uv run ruff format`,
  `uv run mypy src/au_econ`. Fix types with `isinstance` checks, not `cast` or
  `# type: ignore`.

## 9. Checking your work

- **Does it run at all?** `uv run run.py <name> --check`: a full test run into
  `scratch/check/`, leaving `CHARTS/` alone (section 3).
- **Lint and types**: `uv run ruff check src/au_econ`, `uv run ruff format src/au_econ`,
  `uv run mypy src/au_econ`.
- **What did a change do to the charts?** Before changing code, decide which charts should
  change and where (title, footer, plot area). Then:
  `tools/pass.sh <module path> <run name> "<chart folder under CHARTS/>"`
  lints, copies the current charts to `scratch/prev/`, reruns, and prints how many charts
  are identical and the pixel rows and columns that changed. A refactor that should change
  nothing must report "N of N identical".
- `uv run python tools/compare_charts.py <folder a> <folder b>` compares any two chart
  folders; `uv run python tools/footer_gaps.py <folder>` reports footer clearances
  ("COLLISION" when the footers touch).
- To look at a chart: `open "CHARTS/<folder>/<file>.png"`.
