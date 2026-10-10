"""Every filesystem location, anchored to the project root rather than the working directory."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CHARTS_DIR = PROJECT_ROOT / "CHARTS"
CHECK_DIR = PROJECT_ROOT / "scratch" / "check"  # run.py --check draws here, never into CHARTS (gitignored)
LOGS_DIR = PROJECT_ROOT / "LOGS"
KEYS_DIR = PROJECT_ROOT / "KEYS"  # fred.api, EIA-API-KEY.txt, webstat.api (gitignored)
CACHE_DIR = PROJECT_ROOT / "CACHE"  # http_cache downloads (gitignored)
READABS_CACHE = PROJECT_ROOT / ".readabs_cache"
SDMXABS_CACHE = PROJECT_ROOT / ".sdmxabs_cache"
