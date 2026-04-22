"""Repo-root pytest config: add project root to sys.path.

This lets `tests/*.py` import `tdx_service`, `trading_calendar`, `scripts.*`
without needing to install the project as a package.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
