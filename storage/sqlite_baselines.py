"""SQLiteBaselineResultStore."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

from data_schema.baseline_state import (
    SCHEMA_BASELINE_RESULTS,
    ensure_baseline_observability_column,
)

from .base import BaselineResultStore


_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[1]


def _row_to_result(row):
    from backtest.base import BacktestStats
    from backtest.baselines.base import BaselineResult
    stats = BacktestStats(**json.loads(row[7]))
    daily_records = json.loads(row[8]) if len(row) > 8 and row[8] else []
    return BaselineResult(
        id=row[0], session_id=row[1], name=row[2],
        start_date=row[3], end_date=row[4],
        initial_capital=row[5], final_equity=row[6],
        stats=stats,
        daily_records=daily_records,
    )


class SQLiteBaselineResultStore(BaselineResultStore):
    def __init__(self, tmp_path: Path | None = None):
        base = tmp_path if tmp_path else (_DEFAULT_REPO_ROOT / 'data')
        if hasattr(base, 'mkdir'):
            base.mkdir(parents=True, exist_ok=True)
        self._db_path = Path(base) / 'agent_state.db'

    def init_schema(self) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.execute('PRAGMA journal_mode=WAL')
            con.executescript(SCHEMA_BASELINE_RESULTS)
            ensure_baseline_observability_column(con)
            con.commit()
        finally:
            con.close()

    def insert(self, result) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.executescript(SCHEMA_BASELINE_RESULTS)
            ensure_baseline_observability_column(con)
            # Idempotency by (session_id, name): remove any OTHER row with the
            # same session+name before inserting.  This makes run_all safe to
            # rerun — fresh uuids don't accumulate duplicates.
            con.execute(
                '''DELETE FROM baseline_results
                   WHERE session_id = ? AND name = ? AND id != ?''',
                (result.session_id, result.name, result.id),
            )
            daily_records = getattr(result, 'daily_records', None) or []
            con.execute(
                '''INSERT OR REPLACE INTO baseline_results
                   (id, session_id, name, start_date, end_date,
                    initial_capital, final_equity, stats_json,
                    daily_records_json)
                   VALUES (?,?,?,?,?,?,?,?,?)''',
                (result.id, result.session_id, result.name,
                 result.start_date, result.end_date,
                 result.initial_capital, result.final_equity,
                 json.dumps(asdict(result.stats), ensure_ascii=False),
                 json.dumps(daily_records, ensure_ascii=False, default=str)),
            )
            con.commit()
        finally:
            con.close()

    def _cols(self):
        return ('id, session_id, name, start_date, end_date, '
                'initial_capital, final_equity, stats_json, '
                'daily_records_json')

    def get(self, result_id: str):
        con = sqlite3.connect(self._db_path)
        try:
            row = con.execute(
                f'SELECT {self._cols()} FROM baseline_results WHERE id = ?',
                (result_id,),
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        finally:
            con.close()
        return _row_to_result(row) if row else None

    def list_for_session(self, session_id: str):
        con = sqlite3.connect(self._db_path)
        try:
            rows = con.execute(
                f'SELECT {self._cols()} '
                f'FROM baseline_results WHERE session_id = ? '
                f'ORDER BY name ASC',
                (session_id,),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            con.close()
        return [_row_to_result(r) for r in rows]
