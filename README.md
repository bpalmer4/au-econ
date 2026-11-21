# au-econ: Australian Economic Data Charts

Charts of key Australian economic and social statistics, drawn from the latest data
published by the ABS, the RBA and other sources.

This README is the practical how-to. How the code works, how to add a new chart or series,
and the chart conventions are in [docs/how-it-works.md](docs/how-it-works.md).

## Setting up

You need [uv](https://docs.astral.sh/uv/) and a copy of this repository.

```bash
cd au-econ
uv sync                      # installs Python packages and the au_econ package itself
uv run run.py --list         # if this prints a table of modules, the install works
```

API keys live in `KEYS/` (not in git): `fred.api` (FRED), `EIA-API-KEY.txt` (EIA) and
`webstat.api` (Banque de France).

## Everyday commands

```bash
uv run run.py --list            # every module, with its release names and topics
uv run run.py cpi               # one module, by short name ...
uv run run.py 6401              # ... or by catalogue number
uv run run.py economy           # a topic: every module in it
uv run run.py --topics          # the topic words
uv run run.py somp --list       # the charts in one module
uv run run.py --all --list      # every chart in every module, with its short names
uv run run.py rba-fx --charts long_run_exchange_rates   # just these charts; the rest of the folder is kept
uv run run.py --all             # everything (takes a while)
```

Charts land in `CHARTS/<release> - <title>/`, or `CHARTS/<topic>/<release> - <title>/`
for a topic run.

What a run does to your existing charts:
- A full run of a module first fetches its data. **Only if that succeeds** does it delete
  the module's old images and draw new ones. If a source cannot be reached, the old charts
  stay where they were.
- A `--charts` run deletes nothing; it redraws only the charts you named.
- A full topic run also empties folders in `CHARTS/<topic>/` that belong to modules no
  longer in the topic.

The summary at the end says `ok` or `FAIL` for each module, with the reason for each
failure.

## Quick price charts (`tools/quote.py`)

A one-off chart of any Yahoo Finance ticker (shares, indexes, currencies, crypto), outside
the module runs:

```bash
uv run tools/quote.py                      # defaults: NVDA, US market, 2 years, daily closes
uv run tools/quote.py bhp ASX 6mo          # market sets the suffix: US, ASX, LSE, TSX, HK, TYO
uv run tools/quote.py BTC-USD              # a symbol with a suffix or "=" is used as given
uv run tools/quote.py ANT US 2d 5m         # interval: 1m, 5m, 15m, 30m, 1h, 1d, 1wk
uv run tools/quote.py CBA ASX --raw        # prices not adjusted for dividends; saved as ...-raw.png
                                           # (intraday charts add the bar size: ...-5m.png, ...-5m-raw.png)
```

By default past prices are adjusted for dividends (scaled down by later payouts), so the
change shown is close to a total return; `--raw` leaves out the dividend adjustment but is
still adjusted for splits and capital changes such as demergers (Yahoo scales earlier prices
down, so a demerger shows no drop), so it matches the prices actually traded only since the
last such event. The left footer states which when a dividend falls inside the chart's
window; otherwise (crypto, currencies, shares paying nothing) the two are the same and the
footer says nothing. Splits Yahoo records inside the chart's
window are marked with dotted vertical lines, labelled with the ratio in the legend;
demergers are not recorded, so they are not marked.

The period is a number and a unit (`d`, `w`, `mo`, `y`). Yahoo keeps 1-minute bars for
about 8 days, 5 to 30 minutes for 60 days and hourly for 730 days. Intraday charts run on
clock time, with mgplot's axis: closed hours take their real width. On charts of a week or
less they are left blank, as are gaps in Yahoo's data, so the line breaks at each close;
longer charts join across closes, as daily charts do across weekends. Intraday and weekly axes need mgplot 0.3.5 or
later. Bars with no volume and no price movement,
such as the offer price Yahoo shows before a new listing's first trade, are left out of the
line; when that bar opens the series, the offer price is drawn as a dashed reference line and
the footer adds the return on it. The
chart is saved to `CHARTS/quote/` and its path printed.

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
| `scratch/check/` | `--check` runs |
| `tools/` | chart comparison, footer checks and quick price charts (`quote.py`) |
| `docs/` | how-it-works.md |
