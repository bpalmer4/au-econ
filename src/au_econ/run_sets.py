"""Shared broad words (topics) that gather related chart modules into one run set.

A module joins topics through its TOPICS tuple; `run.py <topic>` runs every module that
joined. Each topic must be listed here with its meaning, so the same idea is not filed
under different words (jobs / labour / employment). A topic is added here the first time
a module uses it. A module's own names (release number, short release name) go in its
RELEASE tuple instead, and are not listed here.
"""

TOPICS: dict[str, str] = {
    "building": "Construction, building activity, capital expenditure and housing",
    "business": "Business conditions: profits, inventories and business wages",
    "commodities": "Commodity prices",
    "economy": "The whole economy: national accounts, output, income and productivity",
    "energy": "Energy prices and markets: crude oil, refined fuels and gas",
    "environment": "Emissions and the environment",
    "equities": "Share markets and stock indices",
    "families": "Families, households and relationships",
    "government": "Government finances: revenue, spending, balances, debt and taxation",
    "insolvency": "Corporate and personal insolvencies",
    "international": "International comparisons",
    "jobs": "Employment, unemployment, hours and job vacancies",
    "migration": "Migration and population",
    "prices": "Prices and inflation",
    "rba": "Reserve Bank of Australia tables and forecasts",
    "trade": "International trade and the balance of payments",
    "wages": "Wages, earnings and labour costs",
}
