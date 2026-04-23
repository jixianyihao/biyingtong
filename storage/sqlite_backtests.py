"""SQLiteBacktestResultStore — sessions + results."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

from data_schema.backtest_state import (
    SCHEMA_BACKTEST_SESSIONS, SCHEMA_BACKTEST_RESULTS,
)

from .base import BacktestResultStore


_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[1]


def _row_to_result(row):
    from backtest.base import BacktestResult, BacktestStats, ZoneStats
    stats_d = json.loads(row[9])
    stats = BacktestStats(**stats_d)
    zone_raw = json.loads(row[10])
    zones = [ZoneStats(**z) for z in zone_raw]
    return BacktestResult(
        id=row[0], session_id=row[1], agent_id=row[2],
        persona_id=row[3], model_id=row[4],
        start_date=row[5], end_date=row[6],
        initial_capital=row[7], final_equity=row[8],
        stats=stats, zone_stats=zones,
        quality_gate_label=row[11],
        quality_gate_criteria=json.loads(row[12]),
    )


class SQLiteBacktestResultStore(BacktestResultStore):
    def __init__(self, tmp_path: Path | None = None):
        base = tmp_path if tmp_path else (_DEFAULT_REPO_ROOT / 'data')
        if hasattr(base, 'mkdir'):
            base.mkdir(parents=True, exist_ok=True)
        self._db_path = Path(base) / 'agent_state.db'

    def init_schema(self) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.execute('PRAGMA journal_mode=WAL')
            con.executescript(SCHEMA_BACKTEST_SESSIONS)
            con.executescript(SCHEMA_BACKTEST_RESULTS)
            con.commit()
        finally:
            con.close()

    def create_session(self, session_id, start_date, end_date,
                       agent_ids, notes=None):
        con = sqlite3.connect(self._db_path)
        try:
            con.executescript(SCHEMA_BACKTEST_SESSIONS)
            con.execute(
                '''INSERT OR IGNORE INTO backtest_sessions
                   (id, start_date, end_date, agent_ids, notes)
                   VALUES (?,?,?,?,?)''',
                (session_id, start_date, end_date,
                 json.dumps(agent_ids, ensure_ascii=False), notes),
            )
            con.commit()
        finally:
            con.close()

    def insert(self, result) -> None:
        con = sqlite3.connect(self._db_path)
        try:
            con.executescript(SCHEMA_BACKTEST_RESULTS)
            zone_serial = json.dumps(
                [asdict(z) for z in result.zone_stats], ensure_ascii=False,
            )
            con.execute(
                '''INSERT OR REPLACE INTO backtest_results
                   (id, session_id, agent_id, persona_id, model_id,
                    start_date, end_date, initial_capital, final_equity,
                    stats_json, zone_stats_json,
                    quality_gate_label, quality_gate_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (result.id, result.session_id, result.agent_id,
                 result.persona_id, result.model_id,
                 result.start_date, result.end_date,
                 result.initial_capital, result.final_equity,
                 json.dumps(asdict(result.stats), ensure_ascii=False),
                 zone_serial,
                 result.quality_gate_label,
                 json.dumps(result.quality_gate_criteria, ensure_ascii=False)),
            )
            con.commit()
        finally:
            con.close()

    def _select_cols(self):
        return ('id, session_id, agent_id, persona_id, model_id, '
                'start_date, end_date, initial_capital, final_equity, '
                'stats_json, zone_stats_json, quality_gate_label, '
                'quality_gate_json')

    def get(self, result_id: str):
        con = sqlite3.connect(self._db_path)
        try:
            row = con.execute(
                f'SELECT {self._select_cols()} '
                f'FROM backtest_results WHERE id = ?',
                (result_id,),
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        finally:
            con.close()
        return _row_to_result(row) if row else None

    def list_for_agent(self, agent_id: str, limit: int = 50):
        con = sqlite3.connect(self._db_path)
        try:
            rows = con.execute(
                f'SELECT {self._select_cols()} '
                f'FROM backtest_results WHERE agent_id = ? '
                f'ORDER BY created_at DESC, rowid DESC LIMIT ?',
                (agent_id, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            con.close()
        return [_row_to_result(r) for r in rows]

    def list_for_session(self, session_id: str):
        con = sqlite3.connect(self._db_path)
        try:
            rows = con.execute(
                f'SELECT {self._select_cols()} '
                f'FROM backtest_results WHERE session_id = ? '
                f'ORDER BY agent_id ASC',
                (session_id,),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            con.close()
        return [_row_to_result(r) for r in rows]
