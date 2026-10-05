# Restructure spec: notebooks to a Python package

Status: agreed; in progress. Done 2026-10-02: steps 1, 3, 3a, the step 5 pilot (6302)
and conversions of 6345, 6427, 6467 and 6401 (CPI measures and expenditure classes),
with the step 4 pieces they need. Done 2026-10-03, both stages unless noted: every
non-ABS notebook - FRED (Commodity Prices, Stagflation, GDP International), OECD (GDP as `oecd-gdp`, UR CPI as `oecd-ur`, `oecd-cpi`, `oecd-pop`,
`oecd-berd`), World Bank (Commodity Prices, Global Savings Glut), BIS policy rates, AIP
petrol prices, DCCEEW (Petroleum Statistics, greenhouse gas `nggi`), ASIC, AFSA, Home
Affairs visa workforce, Bonds (`bonds`, `rstar`), Yahoo (`energy`, `yahoo`, `asx`;
stage one only) and RBA Selected Tables (`rba-rates` and `rba-bonds` stage one only;
`rba-fx`, `rba-money`) with SOMP (`somp`). Done 2026-10-04, both stages: 6202 Labour
Force (`lfs`, topic `jobs`), with `series.labour` (the long-run unemployment rate) and
`series.population.smoothed_monthly_pop_growth`; its revisions charts (re-enabled now the
modernised release has enough new-schema prints) and state growth charts are new. The
World Bank savings glut module is now `wb-current-account`; the comparison scripts are
in `tools/` (section 10). Also done 2026-10-04, both stages: the monthly charts of the
ceased 6291.0.55.001 (final release March 2026), folded into `lfs` - age groups (6202
Table 011), capital cities against the rest (LMS2) and country of birth (LMS4), the cubes
read by `sources.abs.get_pivot_cube`. Its quarterly industry and occupation charts wait
for those tables to resume in 6202 (September 2026 reference period, released late
October 2026, occupation recoded to OSCA); its duration of job search charts are dropped,
as the ABS no longer publishes them. The SDMX 6202 notebook's only unique charts (not in
the labour force, underemployed, underutilisation rate) were added to `lfs`. Also done
2026-10-04, both stages: 6354 Job Vacancies (`jv`) and 6150 Labour Account (`la`), both
topic `jobs`; `asx` gained the topic `equities`. Shared: `charting/abs_rows.py` (one chart
per metadata row) and statsmodels stubs for OLS. The 6354 industry vacancy rates (21
images) wait for industry employment to return to 6202; the Labour Account releases too
late to stand in. `ABS LFS - Household dynamics` (6291 FM2, relationship in household)
is on hold: the ABS stopped publishing FM1-FM4 in April 2026, so it waits on what the
modernisation brings back. Also done 2026-10-04, both stages: 6224 Labour Force Status of
Families (`lfs-families`), topics `jobs` and the new `families` (which 3310 marriages and
divorces and Domestic and Family Violence should join). Also done 2026-10-04, both
stages: 3310 Marriages and Divorces (`marriages`, topic `families`), the notebook's one
chart plus four new ones (divorces, crude rates, median age at marriage, marriage
duration). Also done 2026-10-04, both stages: 6321 Industrial Disputes (`disputes`,
topic `jobs`). Also done 2026-10-04, both stages: Domestic and Family Violence (`dfv`,
topic `families`, in `topics/`), with `sources/aihw.py` for the AIHW family, domestic and
sexual violence workbook (the AIHW renamed the NHMD rate unit in 2026, so it is matched by
"per 100,000 population"). mgplot 0.3.4 (int accepted for float; no stray period before a
short chart's data) is now in use. Also done 2026-10-04, both stages: `ABS Wages` as
`wage-measures` (topic `wages`, in `topics/`), with new shared getters
`series.prices.get_wage_index` (WPI, AWOTE) and `series.gdp.get_compensation_per_hour`;
`series.gdp` now reads every 5206.0 table through one cached single-table reader (never the
whole release), to be widened when 5206 is converted. Also done 2026-10-04: 6337 Earnings
by Education (`earnings-education`, topic `wages`), in one stage, as the notebook's chart
folder was empty: the numbers were checked and the conventions applied from the start.
That completes the convertible jobs, families and wages notebooks; what remains there
waits on the ABS (see above). Also done 2026-10-04, both stages: 5206 National Accounts
(`5206`, `gdp`; topics `activity` (new), `wages`, `prices`), a subpackage of 14 files and
44 chart functions in `releases/abs/national_accounts_5206/`. Stage one matched all 755
notebook charts pixel for pixel. Stage two: "Australia." lfooters with the series type,
price measure and "Data to", source-only rfooters, the five-year quarterly window, mgplot
line widths, colon titles (no trailing colons), and mgplot colours except where a colour
has a purpose (the GDP-composition component colours are kept: they tie each component
across the stacked, boxplot, benchmark and single-component charts). Shared
additions: `series.population.get_state_erp` and a statsmodels `hpfilter` stub.
`uv run run.py --list` shows the 42 modules.
Also done 2026-10-04, both stages: the CPI wrap-up, at the user's direction as part of the
CPI release rather than a topic module: `releases/abs/consumer_price_index_6401/related.py`,
10 chart functions, the 30 remaining charts of `ABS Inflation multi-measure` (the 6484
splices, CPI beside PPI/WPI/deflators, goods/services and tradeables, headline v trimmed
mean, Phillips curves, nominal GDP per capita, misery index, CPI/rents/wages/income
rebased). Stage one matched all 30; 6401 now draws 272 charts. `data_to` moved to
`charting.footers`. That completes the inflation notebook.
Also done 2026-10-04, both stages: the Modellers' Database (`1364`, `mdb`, new topic
`productivity`; `releases/abs/modellers_database_1364/`, 18 chart functions, 60 charts), from
the `ABS Quarterly National Accounts 5206 No 2` notebook. The notebook's 2 Oct chart folder
lacked nine charts, so stage one used a fresh run of a scratch copy of the notebook: 60 of 60
identical. The 1966 spliced GDP per hour worked index (RBA OP8 hours) now lives in the module.
Done 2026-10-05: stage two for the backlog (`energy`, `yahoo`, `asx`, `rba-rates`,
`rba-bonds`), in six passes, each confined to its predicted pixels: source-rule rfooters
(Yahoo as "Yahoo", matching `somp`), "Australia. " lfooters, colon titles, mgplot line
widths, mgplot colours (energy's reference lines and annotations take theirs from
`mgplot.utilities.get_color_list`, so they still match their lines), and the standard
quarterly window for E13 (all its series are quarterly-indexed). That clears the stage-two
backlog. The launchd job already runs `run.py` (`energy`, `yahoo`, `asx`) through
`yahoo-commodities-update.sh`, which the plist still calls.
Also done 2026-10-05: topics reorganised at the user's direction. 5206 and 1364 are now in
one topic, `economy` (replacing `activity`, `wages` and `prices` for 5206, and
`productivity` for 1364; `activity` and `productivity` were removed, being empty). New
topics `building` (construction, building activity, capital expenditure, housing),
`trade` and `business` are added as their first modules arrive. Also done 2026-10-05,
both stages: 8755 Construction Work Done (`cwd`, topic `building`), 7 chart functions,
37 charts; stage one matched a same-day run of the notebook 37 of 37. Stage two: the
GDP-share rfooter `ABS: 5206.0, 8755.0`, and `quarterly_plot_times` for the recent and
growth windows (the notebook used `0, -20` and `-19`); the state colours are kept.
Also done 2026-10-05, both stages: 5625 Capital Expenditure (`capex`, topic `building`),
5 chart functions, 130 charts; stage one matched a same-day notebook run 130 of 130.
Stage two: "Seasonally adjusted." wording in the data-centre lfooters; mgplot line widths
on the IMT equipment v buildings chart, which is also recalibrated ($ Billions, not a
hard-coded "$ million (CVM)"); `quarterly_plot_times` for the recent and growth windows
(the notebook used `0, -29` and `-19`).
Also done 2026-10-05, both stages: 5302 Balance of Payments (`bop`, new topic `trade`),
7 chart functions, 36 charts; stage one matched a same-day notebook run 36 of 36 (the
re-referencing down-weight in the net exports contribution runs only while the balance of
payments leads GDP, so it was not exercised). The 5206 current-account charts stay in
5206, at the user's direction. `series.gdp` gained `get_table` (any 5206.0 table, through
its cached reader). Stage two: source-rule rfooters (`ABS: 5302.0`; `ABS: 5206.0, 5302.0`
with GDP), "Seasonally adjusted." / "Current prices." wording, mgplot line widths,
"/Quarter" on the dollar-flow levels (not the end-of-period debt stock), and
`quarterly_plot_times` (already `0, -21`).
Also done 2026-10-05, both stages: 5676 Business Indicators (`bi`, new topic `business`),
7 chart functions, 61 charts; stage one matched a same-day notebook run 61 of 61 (the
re-referencing down-weight is not exercised, as for 5302). `fix_abs_title` moved from
`national_accounts_5206/common.py` to `charting/titles.py` (releases may not import each
other); 5206 redrew all 755 charts identical. Stage two: source-rule rfooters; lfooters
built from the description ("Seasonally adjusted.", the price measure in standard
wording, "Companies." for profit before income tax), dropping the ABS scope codes
(Total (State), Total (Industry), TOTAL (SCP_SCOPE), CORP) that `fix_abs_title` moved
there; `quarterly_plot_times` (the notebook used `0, -29`, `0, -17` and `-19`); "/Quarter"
on the dollar flows (profits, wages, the inventory change), not the inventory stocks. The
headline charts' file-name prefix, meant to put them first in the folder, is now
`TOP_OF_LIST = "AAA"` ("aaa-"): the notebook's `pre_tag="!"` did not work, as mgplot
drops punctuation from file names and wrote "untitled-".
Also done 2026-10-05, both stages: 5232 Financial Accounts (`fa`, topic `economy`), 8
chart functions, 109 charts; stage one matched a same-day notebook run 109 of 109. New
shared getters: `series.population.get_implicit_population` (GDP / GDP per capita, CVM,
Original) and `series.prices.get_price_deflator` (DFD, GNE, HFCE, GDP), both reading
5206.0 through `series.gdp.get_table`. Stage two: source-rule rfooters; lfooter tidy (the
notebook's double space and doubled full stops; "Original series." on the net wealth
charts; the GDP note shortened to "GDP = current prices, 4Q rolling sum.", which also
cleared six footer collisions inherited from the notebook); mgplot line widths;
`quarterly_plot_times` (the notebook used `0, -17`). Balance sheet items are stocks, so
no "/Quarter". That completes the National Accounts partial indicators (5302, 5625, 5676,
8755, 5232).
Also done 2026-10-05, both stages: `ABS Population` is split by catalogue, at the user's
direction, into 3401 Overseas Movements (`movements`) and 3101 Population (`erp`, still to
do), both topic `migration`. 3401: `releases/abs/overseas_movements_3401.py`, 5 chart
functions, 72 charts: the notebook's 70 `arr-` charts plus net permanent and long-term
arrivals against NOM (it tests 3401's proxy against the official count). Stage one: 72
of 72 identical to the same-named charts of a same-day notebook run. New
`series/nom.py` (`get_nom`, official NOM through the year). Stage two: rfooter
`ABS: 3101.0, 3401.0`; colon titles on the seasonal decomposition charts; "Seasonally
adjusted." wording. The monthly windows stay (monthly line charts keep their own), as
do the two widths that highlight a trend or the official series. File names keep the
notebook's `arr-` and `multi-` prefixes.
Also done 2026-10-05, both stages: 3101 Population (`erp`, topic `migration`), the rest of
`ABS Population`: `releases/abs/population_3101/` (`common`, `erp`, `ages`, `growth`), 22
chart functions, 115 charts. Stage one: 115 of 115 identical to the same-named charts of the
same-day notebook run, including the three age-distribution charts, redrawn with mgplot
`line_plot` in place of the notebook's pandas `df.plot` (mgplot needs a RangeIndex of age).
New shared code: `series.population.get_civ15`, `erp_age_sum`, `interp_june` and the now
public `complete_trailing_quarter`; `series.nom.get_nom_forward_proxy`. Stage two: source-
rule rfooters (no table numbers, "ABS Cat." or "Calculated from"; the life tables cited as
3302.0.55.001; charts drawing only on 3101.0 data no longer cite 5206.0 and 6202.0);
lfooters for the state ERP and median-age-by-gender charts, which had none; the migration
and intercensal-discrepancy lfooters shortened, clearing five collisions inherited from the
notebook; mgplot line widths where a single width highlighted nothing; mgplot colours (the
proxy lines still share a colour, from `get_color_list`); `quarterly_plot_times` for the
quarterly charts (the state growth charts' file names change from `-growth--13` to
`-growth--21`). Monthly charts keep their own windows. Added after
the conversion, at the user's request: "Population Growth: 6202 Forward Proxy", the NOM
forward proxy chart's twin for total ERP growth (`series.nom.get_population_growth_proxy`:
the NOM proxy plus natural increase, held at its latest value past the last official
quarter); both charts share `_forward_proxy_chart`.
Also done 2026-10-05, both stages: 6416 Residential Property Prices (`rppi`, topic
`building`; the release was discontinued in 2021), 3 chart functions, 6 charts; stage one
matched a same-day notebook run 6 of 6. New `series/housing.py`: `get_house_price_index`
and its splice report (6432.0 mean dwelling price over the 6416.0 RPPI and established-
house index, from 1986Q2). Its BIS extension, CPI deflation and seasonal adjustment, which
`ABS Real Estate` and `ABS Political` use, were added with the Real Estate conversion. Stage two: source-rule rfooters; series types in the
lfooters; mgplot widths and colours; `quarterly_plot_times` (the notebook used `0, -41`).
Also done 2026-10-05, both stages: 8752 Building Activity (`activity`, topic `building`),
6 chart functions, 59 charts; stage one matched a same-day notebook run 59 of 59. ERP comes
from `series.population.get_erp(project_quarters=2)`; the 8731 approvals and the 6202
state civilian-population tables are read in the module. Stage two: source-rule rfooters
(the notebook wrote `ABS: 8752 8731 3101`); per-state charts' lfooters start "Australia."
(the state is in the title); the completions-per-new-adult lfooter shortened, clearing
five collisions; mgplot widths and colours (the dashed approvals line and the state
colours stay); `quarterly_plot_times` for the quarterly charts (the notebook used
`0, -20`); the monthly charts keep their 61-month window.
Also done 2026-10-05, both stages: 8731 Building Approvals (`approvals`, topic `building`),
7 chart functions, 42 charts; stage one matched a same-day notebook run 42 of 42. State ERP
comes from `series.population.get_state_erp`, GDP from `get_gdp`; the statsmodels stubs gained
`rsquared_adj`, `resid`, `predict`, `summary`, `has_constant` and `durbin_watson` for the
approvals model. Stage two: source-rule rfooters (no table numbers or "&"); "Australia." on
the seasonally adjusted v trend headline charts, which had no lfooter, and standard wording
on the growth charts; `monthly_plot_times` for the growth charts (already 19 months) and
`quarterly_plot_times` for the quarterly charts (the notebook used 2020Q4 and 40 quarters);
the monthly line charts keep their December 2020 start.
Also done 2026-10-05, both stages: `ABS Real Estate` as `topics/house_price_drawdowns.py`
(`house-drawdowns`, topic `building`: it combines ABS and BIS data), 2 charts, nominal and
real drawdowns from each previous peak; stage one matched a same-day notebook run 2 of 2,
which also checks the new shared code against `abs_prices`: `series.housing`'s
`extend_bis`, `real` and `seasonally_adjusted` options (BIS WS_SPP via
`sources.bis.get_residential_property_prices`, trimmed to a year of overlap) and
`series.prices.get_cpi("headline")`, the headline CPI rebuilt from 1948Q4 from the quarterly
change. Stage two: rfooter `ABS: 6401.0, 6416.0, 6432.0; BIS: WS_SPP`; standard lfooter
order; mgplot line widths.
Also done 2026-10-05, both stages: 6432 Dwelling Stock (`dwellings`, topic `building`),
`releases/abs/dwelling_stock_6432/` (`common`, `plots`, `stock`, `breakeven`, `revisions`,
`value`), 24 chart functions, 72 charts (48, and 24 in `states/`); stage one, done by a
background agent and checked here, matched a same-day notebook run 72 of 72. New in
`series.population`: `get_civ15(state)`, `get_adult21`, `interp_21_share`,
`interp_civ15_to_total` (each verified equal to `abs_population`). The notebook defined
`get_extended_dwellings_count` twice (the second runs) and drew the preliminary
affordability charts twice; the module ports the second and draws once. Stage two:
rfooters through one `sources()` helper (ABS catalogues ordered, Census last, `; RBA: F5`);
lfooters start "Australia." (per-state charts too), standard wording, and a shorter
extended-history note, which cleared a collision inherited from the notebook; mgplot
widths where one highlighted nothing; mgplot colours, with ties from `get_color_list`
(state colours, surplus/deficit shading and the vintage colour gradient kept);
`quarterly_plot_times` for the recent breakeven and completions charts (the notebook used
40 quarters). The revisions loop now stops on readabs' `HttpError`/`CacheError` rather
than any exception; the same two were added to 5302's and 5676's history fallbacks, which
caught only `OSError` and so would have crashed on a missing past release. Left as found:
the 2019Q4 index charts write "Q4-2019" where the common-start chart writes "2019Q4".
Also done 2026-10-05, both stages: `ABS Yearly National Accounts` as
`releases/abs/national_accounts_5204.py` (`asna`, topic `economy`), 3 chart functions, 13
charts; stage one matched a same-day notebook run 13 of 13. The notebook tagged the two
productivity charts with `str(f)`, so their file names carried a memory address that
changed every run; the module tags them `bar` and `line` (compared by pairing). Stage two:
rfooter `ABS: 5204.0` (table numbers dropped from the capital-stock charts); "Original
series." on the growth and productivity lfooters; mgplot line widths (the bar width is
kept).
Also done 2026-10-05, both stages: `ABS Yearly State Accounts` as
`releases/abs/state_accounts_5220.py` (`state-accounts`, topic `economy`), 3 chart
functions, 4 charts; stage one matched a same-day notebook run 4 of 4, with state ERP from
`series.population.get_state_erp`. Stage two: rfooter `ABS: 3101.0, 5220.0` on the
per-capita chart (it divides by state ERP); lfooters in the standard wording ("Original
series. Chain volume measures.", replacing descriptions that restated the title).
Also done 2026-10-05, both stages: `ABS Yearly Government Finance Statistics 5512` as
`releases/abs/government_finance_5512.py` (`gfs`, new topic `government`), 6 chart
functions, 10 charts; stage one matched a same-day notebook run 10 of 10. An Excel-only
release: `fetch()` finds each sector's workbook from its Contents sheet and parses the
operating statements and balance sheets (net debt) once, into a frozen `GfsData`; a
missing headline item now raises rather than printing and skipping. Stage two: rfooter
`ABS: 5512.0` (`ABS: 3101.0, 5512.0` on the per-head charts); lfooters gain "Original
series." and "GFS = Government Finance Statistics." (in every title), and shorter notes to
clear collisions (net debt as "debt liabilities less matching assets"; the net-lending
note dropped, its sign convention being in the title); mgplot colours on the two growth
bar charts and mgplot widths on the headline charts (the black, wider Commonwealth line
among the state colours is kept as a highlight).
Also done 2026-10-05, both stages: `ABS Yearly Taxation Revenue 5506` as
`releases/abs/taxation_revenue_5506.py` (`tax`, topic `government`), 4 chart functions, 4
charts; stage one matched a same-day notebook run 4 of 4. The workbook parsing it shares
with 5512 (find a workbook from its Contents sheet, the financial-year header row, short
units) moved to `sources/abs_workbook.py`; 5512 re-verified 10 of 10 unchanged. Stage two:
rfooter `ABS: 5506.0`; "Original series." on every lfooter; mgplot line widths.
Also done 2026-10-05, both stages: `ABS Political` as `topics/political/` (`political`, topic
`economy`: `common`, `prices`, `labour`, `incomes`, `policy`, `population`), 48 chart
functions, 59 charts; stage one matched a same-day notebook run 59 of 59 (the five chart
files were ported in parallel by agents to one spec and checked together). New shared
pieces, each verified equal to the notebook helpers: `analysis/epochs.py` (the government
table and `political.py`'s epoch maths), `charting/epochs.py` (`epoch_vlines`),
`series/productivity.py` (GDP per hour worked spliced back to 1966 over RBA OP8 hours),
`series.rates.get_interbank_rate` (F1.1, by label), and `analysis.decompose.seasonally_adjust`
(made public from `series.housing`, which now uses it; house-drawdowns re-verified). Stage
two: source-rule rfooters; the series type straight after "Australia." in standard wording
(Original for the CPI, tax and balance; seasonally adjusted for house prices, rents,
incomes, wages and the wage share); a shorter household-income footer, which cleared a
collision inherited from the notebook; mgplot line widths (the segments were all 1.5).
Party colours and the election markers are kept.
Runner, 2026-10-05: a full run now clears a module's folder only after its `fetch()`
succeeds (an unreachable source keeps the old charts), and a full topic run empties only
the folders of modules no longer in the topic, rather than the whole topic folder first.
New `--check`: a complete run into `scratch/check/` (`paths.CHECK_DIR`, emptied first) that
never touches `CHARTS/`, for testing which sources can be reached. User guides: `README.md`
(how-to) and `docs/how-it-works.md` (explainer).
Not converted, decided 2026-10-05: `ABS Census - Ad Hoc` (dropped from the rebuild);
`DB.nomics GDP International` (an earlier search for international GDP data: its charts
are the ones `fred-gdp` and `oecd-gdp` draw, `oecd-gdp` covers all its countries but
Singapore, and its main source, IMF IFS on DBnomics, stopped at 2025Q1-Q2 when the IMF
retired IFS, with China and Russia no longer served).
Also done 2026-10-05, both stages: `ABS Recession` as `topics/recessions.py`
(`recessions`, topic `economy`: it combines 1364.0.15.003 and 5206.0), 2 chart functions,
8 charts; stage one matched a same-day notebook run 8 of 8, and the naive recession
probability print is kept (13%). The notebook joined a set of catalogues for the rfooter,
whose order can vary by run; the module sorts it. Stage two: colon titles; rfooter
`ABS: 1364.0.15.003, 5206.0`; lfooters "Australia. Seasonally adjusted." with "Chain volume
measures." on the GDP charts (replacing a longer note, and a stray double space); mgplot
colours and widths (the orange recession shading and the summary chart's solid/dashed
styles kept).
Also done 2026-10-05, both stages: the three household spending notebooks (`ABS
Monthly+Quarterly Household Spending`, `ABS Real Household Spending per Adult`,
`ABS-SDMX-Monthly-Household-Spending-Indicator-5682`) as
`releases/abs/household_spending_5682/` (`hsi`, topic `economy`: `common`, `headline`,
`categories`, `per_adult`), 9 chart functions, 76 charts. Stage one matched same-day runs
of the first two notebooks 41 of 41. New shared getters, each verified equal to the
notebook: `series.prices.get_monthly_cpi` (monthly SA CPI spliced over the 6484.0
indicator and the interpolated quarterly CPI, with its splice report) and
`series.population.get_adult21_monthly` (with `get_smoothed_civ15_gap`); the diagnostic
prints are kept. The SDMX notebook's unique charts (`categories.py`, 35 charts) were
rebuilt from the spreadsheets to the conventions and checked by eye against it (same
data; Tasmania per person differs by $1 in rounding). Stage two: colon titles from the
category ("Real household spending: ..." for the quarterly chain volume measures;
renames 30 files); sorted rfooters without a full stop; standard series-type wording;
`monthly_plot_times` for monthly growth charts (the monthly level line keeps its 3-year
window) and `quarterly_plot_times` for quarterly charts.
Also done 2026-10-05, both stages, each matching a same-day notebook run exactly in stage
one: 5368 International Trade in Goods (`goods`, topic `trade`, 4 charts); 8165 Business
Entries and Exits (`business-counts`, topic `business`, 4 charts); 6524 Personal Income by
Remoteness (`income-remoteness`, topic `wages`, 3 charts; its workbooks found from their
landing pages by the new `sources.abs.landing_page_workbook`); 5601 Lending Indicators
(`lending`, topics `building` and `business`, 19 charts; the RBA discounted variable rate
selected by its F5 title, not its series ID). 8165 stays pinned to its jul2020-jun2024
page: the quarterly TS13 series is published and kept current only there (the
latest-release page carries just the annual data cube). Stage two: rfooters without table
numbers (`ABS: 5601.0; RBA: F5`; `ABS: 6524.0.55.002, ASGS Edition 3`); standard
series-type wording, with "SITC = Standard International Trade Classification." on 5368;
colon titles in 5601's `fix_title`; `quarterly_plot_times` for 5601's paired charts;
mgplot colours and widths (5368's stacked bands from `get_color_list`, with the legend
framed so it reads over them). 6524 now takes its years from the table rather than a
hardcoded list.
Also done 2026-10-05, both stages: `Productivity AU vs US` as `topics/au_vs_us.py`
(`au-vs-us`, topic `international`), 7 chart functions, 9 charts; stage one matched a
same-day notebook run 9 of 9. All data come through the existing layers (`sources.fred`,
`sources.dbnomics`, `sources.rba`, `series.rates`, `series.gdp`, `series.prices`), with
FRED, OECD, EIA and RBA series in label-to-ID tables (the archived 2013 F2 workbook has
no Title row, so RBA series are by ID). `sources.dbnomics.get_series` gained a
keyword-only `timeout` (default unchanged), which the EIA electricity series needs at 120
seconds when DBnomics serves it cold, as the notebook had found. The country colours
(Australia blue, US dark orange) are kept as a tie across all the charts. Stage two:
source-rule rfooters (`ABS: 5206.0; DBnomics: OECD PDB; FRED: OPHNFB`, ...); "Seasonally
adjusted." leading the lfooters that had "SA" mid-sentence; mgplot widths where both
lines had the same width (the trend charts keep thin trends under thick actuals).
That completes the `building` topic.
Package: `au_econ` (project and GitHub repository `au-econ`).

## 0. Decisions

| # | Decision | Status |
|---|----------|--------|
| D1 | Package lives in the same repo, under `~/au-econ/src/` | agreed |
| D2 | Names: GitHub repository and `pyproject` project `au-econ`; import package `au_econ` | agreed |
| D3 | Layers: `sources`, `series`, `analysis`, `charting`, `releases`, `topics` | agreed |
| D4 | Charts written to `~/au-econ/CHARTS/` | agreed |
| D5 | Chart folders are named by the run set the command selected: `CHARTS/<module folder>/` for a release run (or `--all`), `CHARTS/<topic>/<module folder>/` for a topic run, where the module folder is `<first release name> - <TITLE>` (e.g. `6302 - Average Weekly Earnings`); modules may add subfolders to group similar charts (section 6) | agreed |
| D6 | Entry point `run.py <run set>`, one run set per command; each module declares its own names (`RELEASE`) and the shared broad words it joins (`TOPICS`); a run set is either kind, and topics overlap | agreed |
| D7 | No `SHOW`; modules only write files | agreed |
| D8 | Narrow and broad run sets, enforced by the runner: a release number (`6202`) and a short release name (`lfs`) go in `RELEASE` and belong to one module only; broad words (`jobs`, `inflation`) go in `TOPICS`, must be listed with their meaning in the shared `run_sets.TOPICS`, and gather related modules, including topic modules | agreed |
| D9 | `sdmxabs` used for the CPI hierarchy codelist only; nothing else | agreed |
| D10 | No notebook fallback: `run.py` runs converted modules only; notebooks run as they do now until converted | agreed |
| D11 | No PyMC (or arviz, jax, numpyro) in this project; Bayesian work belongs in MacroModels | agreed |
| D12 | One entry point (`run.py`), no collection of run shell scripts | agreed |
| D13 | Functions, not classes, unless a class is plainly the obvious model | agreed |
| D14 | Module shape: `fetch()` + chart functions + `CHARTS` tuple; no `main()` (section 4) | agreed |
| D15 | `--charts <name>...` runs selected charts only, without clearing, within the modules selected by run set. Exact matching on names listed beside each chart in `CHARTS`; short economic names (`u`, `pi`) come from one shared list and may cover several measures (section 7) | agreed |
| D16 | No test suite for now: build first, chart production is the test; runner behaviour checked by hand in the pilot | agreed |
| D17 | The old world (`notebooks/`, its helpers, caches, keys and scripts) is frozen: never moved, trimmed or repointed. Everything is recreated in the package, which keeps its own keys and caches at the root. When all of it works, the old world is deleted in one go | agreed |

## 1. Goals and non-goals

Goals
- Logic lives in an installed package that ruff and mypy check directly.
- One function per concept, written once, used by every chart that needs it.
- One command produces the charts for a release or topic: `uv run run.py 6202`.
  `run.py` is the only way to run things: no per-job shell scripts. Scheduled jobs
  (launchd) call `uv run run.py <name>` directly.
- File locations (charts, caches, keys) do not depend on the working directory.
- Migration is a rebuild beside a frozen old world (D17): notebooks and modules
  coexist, the notebooks keep working untouched, and the old world is deleted in
  one go once the new one does everything it did.

Non-goals
- No change to chart content, titles or styling during migration. A converted
  module must reproduce its notebook's charts.
- No changes to the old world (D17): its caches, keys and input data stay where
  they are; the package has its own copies (section 5).
- No cleanup of stale folders (old `.ipynb_checkpoints/`). The micromamba setup
  was removed separately on 2026-10-02.
  Separate piece of work.
- No new charts or analysis bundled into migration steps.
- No Bayesian modelling (PyMC, arviz, jax, numpyro). That lives in MacroModels.

## 2. Repository layout (end state)

```
~/au-econ/
  pyproject.toml            # gains [build-system]; package installed editable by uv sync
  run.py                    # thin CLI wrapper, calls au_econ.runner.main()
  CHARTS/                   # all chart output (D4)
  LOGS/                     # launchd logs (exists)
  KEYS/                     # API keys: fred.api, EIA-API-KEY.txt (gitignored)
  CACHE/                    # http_cache downloads (gitignored)
  .readabs_cache/ .sdmxabs_cache/   # reader caches (gitignored)
  docs/                     # this spec
  src/au_econ/
    __init__.py
    paths.py                # every filesystem location, anchored to the project root
    runner.py               # discovery, run-set and chart selection, execution
    variables.py            # shared short economic names for --charts (u, pi, y, ...)
    run_sets.py             # shared broad words (topics) for run sets (wages, jobs, ...)
    sources/                # one provider each; fetch + cache; no combining
      http_cache.py  abs.py  rba.py  bis.py  fred.py  oecd.py  yahoo.py
      worldbank.py  aip.py  ...   # section 3, "Sources, shared series and caching"
    series/                 # economic concepts; may combine sources
      gdp.py  prices.py  population.py  labour.py  productivity.py  nom.py  rates.py  ...
    analysis/               # transforms: decompose, henderson, political epochs
    charting/               # mgplot helpers, inflation backplane, footer/source helpers
    releases/
      abs/  rba/  ...       # one module per publication
    topics/                 # cross-source chart sets
```

`notebooks/` (the old world) is not part of the end state: it stays untouched until
it is deleted (D17).

Where each old helper's logic is recreated, as modules need it (section 9). The old
helpers themselves stay untouched:

| Old world (`notebooks/`) | Package equivalent |
|---|---|
| `common.py` | `sources/http_cache.py` |
| `abs_structured_capture.py` | `sources/abs.py` (or `sources/abs_structured.py`) |
| `abs_helper.py` | split: fetch part to `sources/abs.py`, chart-dir part removed (runner owns it, section 6), CPI target constants to `charting/` |
| `abs_gdp.py` | `series/gdp.py` |
| `abs_prices.py` | `series/prices.py` |
| `abs_population.py` | `series/population.py` |
| `abs_nom.py` | `series/nom.py` |
| `abs_spliced_series.py` | split: `series/labour.py` (unemployment), `series/productivity.py` |
| `decompose.py`, `henderson.py` | `analysis/` |
| `political.py` | `analysis/` |
| `pymc_helper.py` | not recreated (D11); deleted in step 3a, before D17. It was used only by two `OLD/` notebooks (`Model - Joint NAIRU+r-star`, `Model - Neutral Rate`), which no longer run |
| `abs_plotting.py`, `abs_inflation_backplane.py` | `charting/` |

## 3. Layers and import rules

Imports point down only:

```
releases, topics
      |
   charting      series
      |         /    \
      |   analysis   sources
      |
   (mgplot, readabs, ... third party)
```

- `sources` imports no first-party code except `paths` and `http_cache`.
- `series` may import `sources`, `analysis`.
- `analysis` imports no first-party code.
- `charting` may import `series` only where a chart element needs data
  (the inflation backplane fetches trimmed-mean CPI).
- `releases`, `topics` may import anything below them; never each other.
- A calculation that combines providers (ABS series divided by an RBA series) lives
  in `series/`, in a function named for what the result means.
- ABS series are selected by description (`find_abs_id` / `select`), never by series
  ID; other providers name series by label (section 4, Coding practice).
  Existing CLAUDE.md data-handling rules carry over unchanged.

### Sources, shared series and caching

Three rules decide where fetching code goes:

1. **How to get data from a provider lives in `sources/`, one file per provider**:
   URL, API key, caching, parsing. Chart modules never call `requests.get` or
   `pd.read_csv` / `pd.read_excel` on a URL themselves.
2. **A module's `fetch()` only names what it wants** ("RBA table F2", "BIS policy
   rates for these countries") and calls `sources/` to get it. It fetches only the
   module's own data.
3. **A series wanted by two or more modules gets a named getter in `series/`**, and
   chart functions call it directly. For example the cash rate: besides the RBA
   notebooks, seven ABS notebooks call `read_rba_table` / `read_rba_ocr`, so it
   becomes `series/rates.py: get_cash_rate()`.

Providers, as built (2026-10-03):

| Provider | `sources/` file |
|---|---|
| ABS | `abs.py`: `readabs` (`read_abs_cat`), cached by readabs; `sdmxabs` for the CPI hierarchy only; data cubes (not time-series tables) through `http_cache` |
| RBA | `rba.py`: `readabs` for the current tables; the historical workbooks readabs lacks, and the SOMP forecast pages (cached forever), through `http_cache` |
| BIS, FRED, OECD, DB.nomics | `bis.py`, `fred.py` (key from `paths.KEYS_DIR`), `oecd.py`, `dbnomics.py`, through `http_cache` |
| World Bank, AIP, DCCEEW, ASIC, AFSA, Home Affairs | `worldbank.py`, `aip.py`, `dcceew.py`, `asic.py`, `afsa.py`, `homeaffairs.py`, through `http_cache` |
| Yahoo | `yahoo.py`: `yfinance` |
| Energy markets | `eia.py`, `opec.py`, `cme.py`, `oilprice.py` |
| Bond yields and term premia | `mof.py`, `bundesbank.py`, `boe.py`, `chinabond.py`, `aofm.py`, `nyfed.py` (the old `common.py` `get_file` calls, moved to their providers) |

Each new provider gets its own `sources/` file when its first notebook is converted.

`fetch()` returns whatever shape suits the module. `AbsRelease` (data dictionary,
metadata, source label, recent date) is the shape for ABS releases, because they
all share it. An RBA module might return a table and its metadata; a FRED module a
DataFrame of the series it asked for. The only requirement is that every chart
function in the module accepts what `fetch()` returns. A topic module that draws
entirely on `series/` getters may have a `fetch()` that returns `None`, and its
chart functions call the getters.

Caching, two levels:
- **On disk, across runs**: the readabs and sdmxabs caches, and `http_cache` for
  every other provider (`paths.CACHE_DIR`).
- **In memory, within a run**: `functools.cache` on the `series/` getters, so ten
  modules asking for the cash rate in one run fetch it once. Getters return copies,
  so a caller mutating its result cannot corrupt the cache (as `abs_population`
  does now).

## 4. Chart modules (`releases/`, `topics/`)

### Shape

```python
"""Labour Force, Australia (6202.0): headline, state and hours charts."""

# --- dependencies
from mgplot import chart_subdir, line_plot_finalise, multi_start

from au_econ.sources.abs import AbsRelease, fetch_release

# --- module contract
RELEASE = ("6202", "lfs")
TOPICS = ("jobs",)
TITLE = "Labour Force"

# --- constants
TABLE = "62020001"
plot_times = 0, -61
STATES_SUBDIR = "States"


# --- data
def fetch() -> AbsRelease:
    """Fetch the release once; every chart function receives it."""
    return fetch_release("6202.0")


# --- charts
def unemployment(release: AbsRelease) -> None:
    """Unemployment rate: national, SA and trend."""
    ...


def states(release: AbsRelease) -> None:
    """Unemployment rate by state."""
    with chart_subdir(STATES_SUBDIR):
        ...


# --- table of contents, in run order
CHARTS = (
    (unemployment, ("u",)),
    (states, ()),
)
```

Fixed section order: docstring, imports, module contract, constants, `fetch()`,
chart functions, `CHARTS` last.

### Contract

- `RELEASE`: non-empty tuple of lowercase strings, at the top of the module: the
  module's own names, a release number and short release name (`6202`, `lfs`).
  The runner refuses to start if two modules share a release name, so `run.py 6202`
  runs the Labour Force module and nothing else (D8). The first release name also
  starts the module's chart folder name (section 6). Release names and topics become
  folder names, so each must match `[a-z0-9][a-z0-9._-]*`.
- `TITLE`: short readable name (`"Average Weekly Earnings"`, `"Labour Force"`). The
  module's chart folder is `<first release name> - <TITLE>`, so people who do not
  remember the codes can find it. No surrounding spaces, `/` or `:` (Finder shows
  `:` as `/`). Release names are unique, so folder names are too.
- `TOPICS`: tuple of lowercase strings (may be empty): the broad words the module
  joins (`jobs`, `inflation`). Each must be in `run_sets.TOPICS`, a shared dict of
  word to meaning that starts small and gains a word, with its meaning, the first
  time a module uses it. This stops one idea being filed under several words
  (`jobs` / `labour` / `employment`). A topic module that uses the CPI joins
  `inflation`, not `6401`. No word may be both a release name and a topic.
  `--list` shows both; `--topics` prints the shared list.
- `fetch()`: no arguments; returns the data every chart function receives, in
  whatever shape suits the module (section 3). Fetches the module's own data only.
  Called once per run, and only if at least one chart is selected. Fetch
  validation lives here or in the source function it calls (existing rule).
- Chart functions: take exactly the value `fetch()` returns, return `None`, write
  chart files. Raise on failure; never swallow exceptions. A chart function's name
  is always one of its `--charts` names (section 7), so it names the subject
  (`unemployment`, `states`, `deflators`), not the action (`plot_states`).
- `CHARTS`: tuple of `(chart function, extra names)` pairs in run order. Extra names
  are short economic names from the shared list (`variables.py`, section 7); the
  function's own name is implicit and not repeated. The runner iterates `CHARTS`;
  there is no `main()`. It is the module's table of contents: reading it tells you
  everything the module produces and what each chart answers to.
- No module-level work beyond constants and definitions: importing a module must
  not fetch data. Discovery imports every module to read its contract, and does so only
  after setting the cache environment variables (section 7).
- No `SHOW`, no `show=` arguments.

### Coding practice

- **Functions, not classes.** A class only where it is plainly the most obvious way
  to model the problem. Data stored on `self` and shared between methods recreates
  the cross-cell-variable problem.
- **Data passes as an argument.** The `fetch()` result replaces the notebook globals
  `abs_dict`, `meta`, `source`, `RECENT`. `AbsRelease` is a small frozen dataclass
  holding those four (a data container, which is the obvious use of a class).
  A chart function sees only what it is given.
- **Data from other releases comes from `series/`.** A chart that needs the CPI or
  population calls the cached getter (`get_cpi()`) itself rather than having
  `fetch()` gather it.
- **Series are named by readable labels, never by IDs in code** (stated 2026-10-03).
  Two reasons: the ABS has changed series IDs often enough to be a repeated trap;
  and, for every provider, good practice is code the reader understands. A label
  ("Coal - Australia", "New Zealand") says what a series is; an ID
  (`NAEXKP01NZQ657S`) does not.
  - ABS: never store a series ID, not even in a table; select by description
    (`find_abs_id` / `select`).
  - Providers whose API selects only by ID (FRED, DBnomics): the IDs sit in one
    table per module, keyed by label (`{label: ID}`), and code reaches an ID only by
    looking up its label. No ID appears inline in logic, and no logic keys on an ID:
    a set of special-case IDs becomes a set of labels.
  - A series wanted by two or more modules moves to a named getter in `series/`
    (section 3), which becomes the lookup.
- **Small private helpers** (leading underscore) sit above the chart functions that
  use them. Logic shared by two modules moves to `charting/` or `series/`.
- **Large releases become a subpackage, one file per chart subfolder.** For example
  `releases/abs/national_accounts_5206/` with `deflators.py`, `productivity.py`,
  `savings.py`; each file holds its chart functions; `__init__.py` holds `RELEASE`,
  `TOPICS`, `fetch()` and a `CHARTS` tuple gathering them
  (`CHARTS = (*deflators.CHARTS, *productivity.CHARTS, ...)`). Chart function names
  must be unique across the whole module, since each is a `--charts` name; the
  runner checks. Short economic names may repeat (several charts can answer to `pi`).

Module file naming: `<short_name>_<catalogue>.py`, e.g. `labour_force_6202.py`
(identifiers cannot start with a digit or contain dots).

## 5. Paths (`paths.py`)

One module defines every location, anchored to the project root found from the
file's own position (`Path(__file__).resolve().parents[2]`), never the cwd.

```python
PROJECT_ROOT
CHARTS_DIR      = PROJECT_ROOT / "CHARTS"
LOGS_DIR        = PROJECT_ROOT / "LOGS"
KEYS_DIR        = PROJECT_ROOT / "KEYS"             # fred.api, EIA-API-KEY.txt
CACHE_DIR       = PROJECT_ROOT / "CACHE"            # http_cache downloads
READABS_CACHE   = PROJECT_ROOT / ".readabs_cache"
SDMXABS_CACHE   = PROJECT_ROOT / ".sdmxabs_cache"
```

Nothing points into `notebooks/` (D17), so deleting the old world cannot break the
package. The keys in `KEYS/` are copies of the old world's (made 2026-10-02); all four
locations are gitignored. The caches fill on first use; anything the old caches held
is refetched once. An input-data constant is added when a module first needs an
input file (today only `OLD/` notebooks read `ABS-Data/` and `govt-budget/`).

Third-party caches:
- **readabs** reads `READABS_CACHE_DIR` from the environment once, at import
  (`download_cache.py:22`, default `./.readabs_cache`). `runner.py` sets it to
  `READABS_CACHE` before importing any chart module. Notebooks run from
  `notebooks/` and keep using their own cache there.
- **sdmxabs** is used for exactly one thing: the CPI hierarchy codelist (D9).
  Only `sources/abs.py` may import it. Three notebooks use it today; the
  replacement column says how the package covers each (the notebooks themselves
  are left alone):

  | Notebook | What sdmxabs supplies | Replacement |
  |---|---|---|
  | `ABS-SDMX-Monthly-Labour-Force-6202` | LF, LF_HOURS, LF_UNDER flows: headline, hours, underemployment | Same series are in the 6202.0 spreadsheets that `ABS Monthly Labour Force 6202` already reads. Notebook is an SDMX experiment duplicating it; not recreated. Checked 2026-10-04: its only unique charts (not in the labour force, underemployed total and its growth, underutilisation rate) were added to `lfs` from the spreadsheets (Tables 001 and X28) |
  | `ABS-SDMX-Monthly-Household-Spending-Indicator-5682` | HSI_M / HSI_Q flows; state ERP via `fetch_state_pop` | 5682.0 is already read by `readabs` in two notebooks (`ABS Monthly+Quarterly Household Spending`, `ABS Real Household Spending per Adult`); state ERP from `series.population`. Checked 2026-10-05: the state-by-category monthly series are in the spreadsheets (tables 5682003-010), so its unique charts (national categories, state totals, spending per person by state) are in `hsi`'s `categories.py`; its headline and quarterly charts duplicate `headline.py` and are not recreated |
  | `ABS Inflation multi-measure` | The CPI `INDEX` codelist: parent links of group / sub-group / class (cached 14 days in `CACHE/ABS_cpi_hierarchy/`) | None: no spreadsheet equivalent. Stays on `sdmxabs.code_list_for("CPI", "INDEX")`, recreated in `sources/abs.py` |

  sdmxabs reads `SDMXABS_CACHE_DIR` from the environment at import
  (`download_cache.py:19`, default `./.sdmxabs_cache`), the same mechanism as
  readabs. The runner sets it to `SDMXABS_CACHE`, alongside `READABS_CACHE_DIR`.
  sdmxabs is the user's own package, so it can be changed if anything further is needed.

## 6. Charts

Location: `~/au-econ/CHARTS/` (D4), for converted modules. Notebooks are left alone:
they keep writing to `notebooks/CHARTS/`, and nothing there is moved or edited.
`notebooks/CHARTS/` goes when the old world is deleted.

### Folder scheme (D5)

One run set per command, and it names the folder. Each module's own folder is
`<first release name> - <TITLE>`, so `run.py 6302` and `run.py awe` share a folder:

| Command | Charts go to |
|---|---|
| `run.py 6302` / `run.py awe` | `CHARTS/6302 - Average Weekly Earnings/` |
| `run.py wages` | `CHARTS/wages/6302 - Average Weekly Earnings/`, `CHARTS/wages/6345 - Wage Price Index/`, ... (one subfolder per module, so chart file names from different modules cannot collide) |
| `run.py --all` | `CHARTS/<module folder>/` for every module |

Modules declare no folder: it is built from `RELEASE` and `TITLE`, both literals, so
nothing is looked up (no ABS catalogue fetch) when a module is imported. The code
comes first so folders sort by code; the title is there for people who do not
remember the codes. Topic folders are the bare topic word (`wages/`).

The same charts can exist in two places: after `run.py 6302` and `run.py wages`, the
AWE charts are in `CHARTS/6302 - Average Weekly Earnings/` and in
`CHARTS/wages/6302 - Average Weekly Earnings/`, each from its own run. Each folder is
simply the output of the command that names it.

Where a module produces many charts, it groups similar ones in subfolders with
`mgplot.chart_subdir()` (as `5206`, `6432`, `6150` and the inflation notebook do now:
`Deflators/`, `Productivity/`, `ExpenditureClasses/`). Subfolder names are named
constants in the module.

### Clearing

A full run (no `--charts`) deletes image files before drawing, recursively,
including subfolders:
- a release run (or `--all`): each module's own folder, `CHARTS/<module folder>/`;
- a topic run: the whole topic folder, `CHARTS/<topic>/`, so a module that has left
  the topic leaves no stale subfolder behind.

A folder is only ever filled by the command that names it, and that command redraws
everything in it, so clearing cannot delete charts it will not replace. A `--charts`
run clears nothing: selected charts overwrite their own files.

Recursive clearing replaces today's per-subfolder `chart_subdir(..., clear=True)`.
mgplot's `clear_chart_dir()` only clears the top level, so a subfolder a notebook
stops writing to (after a rename, say) keeps stale charts indefinitely. The runner
does the recursive clear itself (image extensions only, as mgplot does); modules
call `chart_subdir(name)` without `clear=`.

Chart footers, title style and colour conventions carry over unchanged.

## 7. `run.py` and the runner

### Usage

```
uv run run.py 6202                # one name
uv run run.py jobs                # a topic: every module that joined it
uv run run.py --list              # table: module, release, topics
uv run run.py --all               # every module
uv run run.py jobs --charts u     # unemployment-rate charts in the jobs modules
uv run run.py lfs --charts u      # the same, in the LFS module only
uv run run.py 5206 --charts deflators productivity
uv run run.py --all --charts pi   # every inflation chart in every module
uv run run.py --variables         # the shared list of short economic names
uv run run.py --topics            # the shared list of broad words
uv run run.py jobs --list         # the charts in the selected modules
```

`run.py` at the project root is a few lines calling `au_econ.runner.main()`.
All logic is in `runner.py` so it is linted and typed.

### Name resolution

- Names are case-insensitive.
- One run set per command (or `--all`); a second name is an error.
- A run set selects every module whose `RELEASE` or `TOPICS` contains it (topics
  overlap by design; release names never do).
- An unknown name is an error, with close-match suggestions (`difflib`); nothing
  runs.
- Before running, the runner prints the modules selected and why
  (`jobs -> labour_force_6202, ...`).

### Chart selection (`--charts`)

- **Scoped by run set.** `--charts` filters within the modules the run set
  selected; it never selects modules itself. `--charts` with no run set is an
  error; `--all --charts u` is the way to search every module.
- **Exact matching**, case-insensitive. A chart answers to its function name and
  to the extra names beside it in `CHARTS`. No prefixes or partial matches:
  `u` never selects `underemployment`.
- **Shared short names.** `src/au_econ/variables.py` holds one dict of short
  economic names and their meanings:

  ```python
  VARIABLES = {
      "u": "Unemployment rate",
      "pi": "Inflation (any measure)",
  }
  ```

  - One name may cover several measures: headline, trimmed mean and weighted
    median charts can all answer to `pi`.
  - ASCII only (`pi`, not `π`), so names type easily at the shell.
  - Every extra name in any module's `CHARTS` must be in `VARIABLES`; the runner
    refuses to start otherwise. This catches typos and stops a name meaning
    different things in different modules.
  - The list starts empty and grows as modules are converted: a name is added
    the first time a chart uses it, with its meaning.
  - A short name must not equal any chart function name, so a name cannot be both.
- A module with no matching chart is skipped entirely: not fetched, folder not touched.
- A name matching nothing in the selected modules is an error, listing the chart
  names available there; nothing runs.
- The selected charts are printed before running, as module selection is.
- Without `--charts`, every chart in `CHARTS` runs.

### Execution

Once, before any chart module is imported: select matplotlib's `Agg` backend, and
set `READABS_CACHE_DIR` and `SDMXABS_CACHE_DIR`.

`Agg` because the runner only writes files (D7) and never needs a window: it is the
renderer Jupyter's inline backend uses, so modules reproduce their notebooks' charts
exactly, and it works in launchd jobs, which have no window session. Under the macOS
default backend the 6302 pilot's charts came out shifted by a few pixels throughout
(found 2026-10-02; the cause inside that backend was not traced). Notebooks that
import `au_econ` keep their own backend: the runner sets it, not the package.

Full topic run only: clear image files in the whole topic folder (section 6).

For each selected module, in a stable order (sorted by module path):
1. point mgplot at the module's folder for this command (section 6),
2. full release run (or `--all`) only: clear image files in the folder and all its
   subfolders. A `--charts` run does **not** clear: it would delete the charts it
   did not redraw. Selected charts overwrite their own files,
3. call `fetch()` once,
4. call each selected chart function with the result, in `CHARTS` order; a failing
   chart is recorded (exception and traceback) and the next chart still runs,
5. record success or failure per chart; continue to the next module.

A failure in `fetch()` fails all of that module's charts.

At the end: a summary per module, listing each failed chart with its exception type
and message (ok modules on one line),
then exit code 0 if all succeeded, 1 otherwise. Output goes to stdout/stderr;
launchd redirects it to `LOGS/` as it does today. No logging framework.

### Unconverted notebooks (D10)

`run.py` knows only converted modules. Every notebook keeps running as it does now
(Jupyter, or `nbconvert`), converted or not, until the old world is deleted. The
launchd job keeps calling `yahoo-commodities-update.sh` until then; switching it to
`uv run run.py yahoo` (the plist sets the working directory) is part of the final
step.

## 8. Packaging and tooling

`pyproject.toml`:
- add `[build-system]` using uv's build backend, with
  the project name changed from `abs` to `au-econ`, from which uv derives the
  import package `au_econ` (no `module-name` setting needed);
  `uv sync` then installs the package editable, importable from any directory and
  from notebook kernels.
- `[tool.ruff] src = ["src", "notebooks", "."]` during migration; `notebooks`
  drops out when the old world is deleted.
- Notebook-only ruff ignores (`E402`, `B018`, `BLE001`, `INP001`, `PLR0913`, `S101`
  for `*.ipynb`) stay scoped to notebooks; package code gets the full rule set.
- mypy runs on `src/` directly; nbqa stays for notebooks.
- The migration adds no shell scripts (D12). Existing scripts: `yahoo-commodities-update.sh`
  is retired in the final step (section 7). The four
  `notebooks/*-all.sh` lint scripts were deleted on 2026-10-02; lint and type checks
  are plain `uv run ruff ...` / `uv run mypy ...` (and `nbqa` for notebooks). The
  rest (`uv-upgrade.sh`, `test-*.sh`) are untouched by this work.
- Dependencies `pymc`, `arviz`, `jax`, `numpyro`, `graphviz` are removed from
  `pyproject.toml` (D11), with `notebooks/pymc_helper.py`. Nothing outside `OLD/`
  imports them. Separate step, so the lock-file change is reviewed on its own.
- No test suite for now (D16): build first; chart production is the test. Runner
  behaviour that chart images cannot show is checked by hand at its first real use
  (step 5): partial runs leave other charts in place, `u` does not select
  `underemployment`, unknown names are refused, the readabs cache in use is
  the root `.readabs_cache` (no new cache appears under `notebooks/` or elsewhere). pytest can be
  added later if something proves fragile.

## 9. Migration plan

Each step is independently reviewable and leaves everything runnable. No step
before the last edits, moves or deletes anything in the old world (D17).

| Step | Change | Touches | Verification |
|---|---|---|---|
| 1 | Package skeleton: `pyproject` build-system, `src/au_econ/__init__.py`, `paths.py`; `.gitignore` gains root `CHARTS/**`, `KEYS/`, `CACHE/`; keys copied into `KEYS/` | 4 files + 2 key copies | `uv sync`; import from root and from `notebooks/`; paths resolve the same from both; `git check-ignore` covers keys and caches |
| 3 | `runner.py` + `run.py` (no real modules yet) | 2 files | ruff, mypy; `--list` and `--variables` run (empty); first real use is step 5 |
| 3a | Drop PyMC stack: remove `pymc`, `arviz`, `jax`, `numpyro`, `graphviz` and `pymc_helper.py` | `pyproject.toml`, `uv.lock`, 1 file | `uv sync`; ruff/mypy clean; no import errors in remaining notebooks |
| 4 | Recreate the helpers' logic in `sources/series/analysis/charting`, one at a time, as the modules being converted need it; no notebook edits | new package files only | ruff, mypy on `src/` |
| 5 | Pilot conversion: recreate the small `6302` notebook (Average Weekly Earnings, 2 charts, needs only `sources/abs.py`) as `releases/abs/average_weekly_earnings_6302.py`; the notebook stays | 1 module + `sources/abs.py` | Image comparison (section 10); hand checks of runner behaviour (section 8) |
| 6+ | Recreate further notebooks, one per step, user's choice of order; merge duplicate functions as each is rebuilt | per step | Image comparison |
| last | Delete the old world: `notebooks/`, the shell scripts it uses, notebook-only `pyproject.toml` settings (nbqa, `*.ipynb` ignores, `src = "notebooks"`); switch launchd to `run.py`; rewrite CLAUDE.md for the new layout | old world, config | `run.py --all` succeeds after the deletion |

## 10. Verifying a conversion

A converted module passes only if it reproduces its notebook's charts:
- Run the notebook and the module the same day (data is fetched live). The notebook
  writes to `notebooks/CHARTS/`, the module to `CHARTS/`, so neither run clears the
  other's output.
- Same set of file names in both chart folders.
- Each pair of PNGs identical pixel-for-pixel (compare decoded pixels, not file
  bytes: PNG metadata differs between runs).
- Both sides drawn with the same backend: run the notebook through Jupyter
  (inline, Agg-based) and the module through `run.py` (Agg). A module drawn any
  other way can differ by a few pixels everywhere for reasons unrelated to the code.
- Any differing chart is investigated, not accepted.
- A deliberate improvement (e.g. `rfooter=source` replacing a literal footer) is a
  second stage: first prove an exact match with the notebook's behaviour, then
  make the change and confirm the differing pixels are confined to where it shows.
- The checks are in `tools/` (checked in, unlike the throwaway `scratch/`, which holds
  only their snapshots): `compare_charts.py` compares two chart folders pixel by pixel
  and gives the bounds of each difference; `footer_gaps.py` measures the gap between
  the left and right footers and flags collisions; `pass.sh` runs one stage-two pass
  (lint, snapshot to `scratch/prev`, rerun, compare); `old_palette.py` redraws a module
  with mgplot's pre-2026-10-02 palette, for comparing against notebook charts drawn before
  mgplot 0.3.3 changed its default colours.

## 11. CLAUDE.md changes (applied at the end, step "last")

- Carry over to modules: data handling, charting conventions, no magic numbers,
  no duplicate code, named window constants, fetch validation, no hardcoded IDs.
- Footer rule, stated 2026-10-02: every chart of Australian data (ABS data is
  essentially all Australian) whose title does not contain "Australia" starts its
  lfooter with "Australia. ". Notebook footers that break it are fixed in a
  conversion's second stage, after the exact match (section 10).
- Series-type rule, stated 2026-10-02: where possible, and unless the legend
  already makes it clear, the lfooter says whether the series is Original,
  Seasonally Adjusted or Trend, and, where it applies, Chain Volume Measures or
  Current Prices. Wording: "Original series.", "Seasonally adjusted." or "Trend.",
  from `charting.footers.SERIES_TYPE_NOTES`. A seasonally adjusted against trend
  chart needs no note.
- Source rule, stated 2026-10-02: the rfooter is the source only, without table
  names. Catalogues from one source are comma-separated after one prefix, different
  sources are separated by a semicolon, and there is no closing punctuation (no
  full stop): `ABS: 6345.0, 6401.0; RBA: F1`.
- ID rule, stated 2026-10-03: CLAUDE.md's "Constants hold descriptions, never series
  IDs" is rewritten as the label rule in section 4 (Coding practice): ABS by
  description; other providers through a label-to-ID table.
- Recent window, stated 2026-10-02: for quarterly data, five years
  (`charting.windows.quarterly_plot_times`, `0, -21`: twenty quarters of growth
  plus the quarter it grows from). Modules import it rather than define their own.
  For monthly annotated bar-and-line charts only, a year and a half
  (`monthly_plot_times`, `0, -19`), so readers can easily look back a year; 25
  labelled bars (two years) was tried on 2026-10-02 and proved too cramped. Monthly
  line charts keep their own windows (clarified 2026-10-03).
- Line widths are left to mgplot (2.0 up to 151 points, 1.0 beyond). `width=` is
  used only to give the lines of a multi-line chart different widths, to highlight
  one.
- Drop for modules (they exist only because of cells): imports-at-top-of-cell,
  no cross-cell variables, one responsibility per cell, watermark cell,
  Restart and Run All, `SHOW`.
- New: layer import rules (section 3), module contract (section 4), paths only via
  `paths.py`, verification by image comparison.
- Notebook rules go with the old world.

## 12. Risks

- **Refetching the readabs cache** if `READABS_CACHE_DIR` (or `SDMXABS_CACHE_DIR`)
  is not set before the package is imported. Mitigated by the runner setting both
  first; checked by hand in step 5.
- **Silent wrong module** from overlapping tags. Mitigated by printing the selection
  before running.
- **Clearing charts a run will not replace.** Prevented by construction: a folder is
  only filled by the command that names it, and a full run of that command redraws
  everything in it (section 6).
- **Two copies of a chart** (`CHARTS/6302 - .../` and `CHARTS/wages/6302 - .../`) from runs on
  different days. Accepted: each folder is the output of its own command.
- **Import side effects**: a module that fetches at import would make `--list` slow
  and fragile. The contract forbids it.

## 13. After the transition: issues to consider

- **Retrying failed fetches and charts** (raised 2026-10-05). A failing chart is run
  once: the runner prints the traceback, records the failure and moves on, with no
  pause, refetch or cache clearing. Rerunning only the chart would not help, as each
  module fetches once and every chart shares that data; the CME and Yahoo fetches are
  not cached. Only DBnomics retries (timeouts and server errors, with backoff), and
  sources read through `http_cache` fall back to their last saved copy. Two places a
  retry could go: in the sources (CME, Yahoo, oilprice, OPEC retry on timeouts and
  server errors, as DBnomics does), or in the runner (after a pause, refetch the
  module's data and rerun its failed charts once, which repeats every other fetch in
  the module). A retry suits network failures, such as the oilprice.com read timeouts
  in the launchd error log. It would probably not have saved `energy`'s
  `gas_forward_curves` on Sunday 2026-10-04: CME answered with a TTF curve none of
  whose months matched Henry Hub's, the same bad answer a retry would likely get (CME's
  answer for the latest trade date changed over hours, not seconds). That one needs the
  CME curve's trade date and months logged, then a fix chosen from the evidence:
  reject a partial trade date and fall back to the previous one, as
  `cme.get_settlement_curve` already does for empty dates, or fail with a message
  naming the curve.
- **The period of a flow on the y-axis, from the ABS metadata** (raised 2026-10-05). A
  dollar flow needs its period ("$ Billions/Quarter"); a stock, index, percentage or
  ratio does not. Today the "/Quarter" is typed by hand (8755, 5625). The ABS metadata
  can supply it: `mc.dtype` (Data Type) marks each series FLOW, STOCK, STOCK_CLOSE,
  INDEX, PERCENT, RATIO, AVERAGE or DERIVED, and `mc.freq` gives Quarter, Month or
  Annual (5625: FLOW 990, RATIO 84; 5232: STOCK_CLOSE 4783, FLOW 4731; 6202: STOCK
  2868, PERCENT 1848). The idea: add the period where data are prepared for plotting,
  beside `ra.recalibrate`, so the units string that comes out ("$ Billions/Quarter")
  is the ylabel as is, and chart functions never add a suffix. Gaps to handle: DERIVED
  (all of 5206's key aggregates, GDP included, though GDP is a flow), transformed data
  (a rolling four-quarter sum is still marked FLOW / Quarter but covers a year; a share
  of GDP is a ratio), and non-ABS sources, which have no Data Type. Each of these needs
  an explicit override at the preparation step.
