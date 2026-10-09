# au-econ: Australian Economic Data Charts

Charts of key Australian economic and social statistics, drawn from the latest data
published by the ABS, the RBA and other sources.

This README is the practical how-to. How the code works, how to add a new chart or series,
and the chart conventions are in [docs/how-it-works.md](docs/how-it-works.md).

## Setting up (a new machine, or after a while away)

You need [uv](https://docs.astral.sh/uv/) and this folder.

```bash
cd ~/au-econ
uv sync                      # installs Python packages and the au_econ package itself
uv run run.py --list         # if this prints a table of modules, the install works
```

API keys live in `KEYS/` (not in git): `fred.api` (FRED) and `EIA-API-KEY.txt` (EIA). Copy
the folder across if you move machines.

## Everyday commands

```bash
uv run run.py --list            # every module, with its release names and topics
uv run run.py cpi               # one module, by short name ...
uv run run.py 6401              # ... or by catalogue number
uv run run.py economy           # a topic: every module in it
uv run run.py --topics          # the topic words
uv run run.py somp --list       # the charts in one module
uv run run.py rba-fx --charts long_run_exchange_rates   # selected charts only
uv run run.py --all             # everything (takes a while)
```

Charts land in `CHARTS/<release> - <title>/`, or `CHARTS/<topic>/<release> - <title>/`
for a topic run. Look at one with `open "CHARTS/6202 - Labour Force/<file>.png"`.

What a run does to your existing charts:
- A full run of a module first fetches its data. **Only if that succeeds** does it delete
  the module's old images and draw new ones. If a source cannot be reached, the old charts
  stay where they were.
- A `--charts` run deletes nothing; it redraws only the charts you named.
- A full topic run also empties folders in `CHARTS/<topic>/` that belong to modules no
  longer in the topic.

The summary at the end says `ok` or `FAIL` for each module, with the reason for each
failure.

## Checking data availability (`--check`)

`--check` makes a complete test run that cannot touch your charts. It runs everything
normally but draws into `scratch/check/` instead of `CHARTS/`, which it empties first.
Nothing in `CHARTS/` is read, deleted or written.

```bash
uv run run.py --all --check         # can every source be reached? (takes a while)
uv run run.py economy --check       # just one topic
uv run run.py lfs --check           # just one module
```

Read the summary at the end:
- `ok    6202 - Labour Force (N charts)`: the source was reached and every chart drew.
- `FAIL  ...: fetch() failed: ConnectionError ...`: the module's main source could not be
  reached (blocked, down, or no network).
- `FAIL  ...: <chart>: ...` on some charts only: those charts use another source (often a
  shared series such as the CPI or the cash rate) that could not be reached, or the data
  changed shape.
- A `WARNING: could not download fresh data ... may be out of date` line above the
  summary: an ABS or RBA file could not be refreshed, so the chart used your last download
  (see "Offline" below).

When travelling: run `uv run run.py --all --check` before you leave, so you know what
works at home, then again on arrival. Any module that newly fails is blocked from where you
are. A VPN usually fixes that.

`--check` draws every chart rather than just fetching, because many charts fetch extra
series (CPI, population, rates) inside the chart itself. Drawing them all is the only way
to test every source.

## Offline, or behind a firewall

- **ABS and RBA** (through readabs, cached in `.readabs_cache/`): if a download fails,
  readabs uses the cached copy and prints a WARNING. The charts still draw, from the data
  you last downloaded.
- **Most other providers** (FRED, OECD, BIS, World Bank, DB.nomics, Yahoo, EIA and others,
  cached in `CACHE/`): a failed download usually means the module FAILs. Its old charts
  are kept, because charts are only cleared after a successful fetch. Exceptions that fall
  back to the cache: the AOFM, Bank of England, Bundesbank, Japan's Ministry of Finance,
  ChinaBond, the NY Fed, ASIC and AFSA.
- Yahoo Finance, and some Western sites, are often blocked from China without a VPN. The
  ABS and RBA sites may be slow.

To refresh the caches before going away, run `uv run run.py --all` (or `--check`) on a good
connection.

## The weekly job

A launchd job (`~/Library/LaunchAgents/com.bryanpalmer.yahoo-commodities-update.plist`)
runs `yahoo-commodities-update.sh` every Sunday at 08:00. That runs the `energy` topic
(`aip` and `energy-markets`), then `yahoo` and `asx`, so their charts land in
`CHARTS/energy/aip - Fuel Terminal Gate Prices/`, `CHARTS/energy/energy-markets - Energy Markets/`,
`CHARTS/yahoo - Commodity Futures/` and `CHARTS/asx - ASX Indices/`. Its output and errors
go to `LOGS/yahoo-commodities-log.log` and `LOGS/yahoo-commodities-err.log`. It runs only
while you are logged in; if the Mac was asleep at 08:00, launchd runs it when the Mac wakes.

## When something fails

| What you see | What it usually means | What to do |
|---|---|---|
| `fetch() failed: ConnectionError`, `ReadTimeout`, `HTTPError 403` | The site could not be reached, or refused the request | Check the network or VPN; try again later. Old charts are kept. |
| `ValueError: ... no ... found`, `KeyError` naming a description | The ABS renamed a series or table | Search the metadata (see docs/how-it-works.md, "A new ABS publication") and update the description in the module |
| `HttpError ... 404` on an ABS history or landing page | A release moved or was discontinued | Check the release on the ABS site; update the URL or catalogue in the module |
| A FRED module fails with an authorisation error | The key in `KEYS/fred.api` is missing or invalid | Get a new key from FRED and save it in `KEYS/fred.api` |
| `run.py` stops before running, listing problems | A module breaks the contract (duplicate name, unknown topic) | Fix the module named; add a new topic word to `src/au_econ/run_sets.py` |
| One chart fails, others in the module work | That chart's extra data or its calculation broke | Run just that chart with `--charts <name>` and read the traceback above the summary |

A full traceback for every failure is printed above the summary. Run a single module to
keep the output short.

## Making changes

- Lint and type checks: `uv run ruff check src/au_econ`, `uv run ruff format src/au_econ`,
  `uv run mypy src/au_econ`.
- Test without touching your charts: `uv run run.py <name> --check`.
- See what a change did to a module's charts, pixel by pixel:
  `tools/pass.sh <module path> <run name> "<chart folder under CHARTS/>"`.
- How to add a chart, a module or a series: [docs/how-it-works.md](docs/how-it-works.md),
  section 6.

## Where things live

| Folder | What |
|---|---|
| `src/au_econ/` | the package: sources, series, analysis, charting, releases, topics, runner |
| `CHARTS/` | the charts |
| `CACHE/`, `.readabs_cache/`, `.sdmxabs_cache/` | downloaded data; safe to delete (refetched next run) |
| `KEYS/` | API keys (never commit) |
| `LOGS/` | the weekly job's output |
| `scratch/` | throwaway work; `scratch/check/` holds `--check` runs |
| `tools/` | chart comparison and footer checks |
| `docs/` | how-it-works.md, and restructure-spec.md (the design record) |
| `notebooks/` | the old Jupyter notebooks, frozen until they are deleted; never edit |

## The old world

The charts used to come from Jupyter notebooks in `notebooks/` (with helper modules beside
them, writing to `notebooks/CHARTS/`). Each notebook has been recreated in `src/au_econ/`,
checked pixel-for-pixel against the notebook's charts, then brought to the chart
conventions; two were dropped as superseded (Census ad hoc, DB.nomics GDP). A few charts
wait on the ABS's modernised labour force releases (late October 2026): the quarterly
industry and occupation charts, industry job vacancy rates, and household dynamics. The
notebooks stay frozen until they are deleted in one go. The design, the decisions behind
it and the record of every conversion are in
[docs/restructure-spec.md](docs/restructure-spec.md).
