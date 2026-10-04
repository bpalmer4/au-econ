"""Shared broad words (topics) that gather related chart modules into one run set.

A module joins topics through its TOPICS tuple; `run.py <topic>` runs every module that
joined. Each topic must be listed here with its meaning, so the same idea is not filed
under different words (jobs / labour / employment). A topic is added here the first time
a module uses it. A module's own names (release number, short release name) go in its
RELEASE tuple instead, and are not listed here.
"""

TOPICS: dict[str, str] = {
    "activity": "Output, demand and income: GDP and its components",
    "commodities": "Commodity prices",
    "environment": "Emissions and the environment",
    "equities": "Share markets and stock indices",
    "families": "Families, households and relationships",
    "insolvency": "Corporate and personal insolvencies",
    "international": "International comparisons",
    "jobs": "Employment, unemployment, hours and job vacancies",
    "migration": "Migration and population",
    "prices": "Prices and inflation",
    "productivity": "Labour, capital and multifactor productivity",
    "rba": "Reserve Bank of Australia tables and forecasts",
    "wages": "Wages, earnings and labour costs",
}
