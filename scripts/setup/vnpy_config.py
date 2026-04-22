"""Configure vnpy to store its SQLite database in ./data/vnpy_data.db.

vnpy reads DB config from vnpy.trader.setting.SETTINGS. By default it uses
~/.vntrader/database.db, which is unreachable from a repo-local workflow.
Import `configure()` before using any vnpy Database or BacktestingEngine.
"""
from pathlib import Path

from vnpy.trader.setting import SETTINGS

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / 'data'
DB_PATH = DATA_DIR / 'vnpy_data.db'


def configure() -> Path:
    """Point vnpy at data/vnpy_data.db. Idempotent. Returns the DB path."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS['database.name'] = 'sqlite'
    SETTINGS['database.database'] = str(DB_PATH)
    return DB_PATH
