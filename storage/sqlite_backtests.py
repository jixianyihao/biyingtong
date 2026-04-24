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
    # Columns 13/14/15 are daily_records_json/trades_json/thinking_json.
    # Schema default is '[]' and ensure_observability_columns runs at init,
    # so row[13:16] are always populated strings — but json.loads('') raises,
    # so we still guard against empty strings from buggy callers.
    daily_records = json.loads(row[13]) if row[13] else []
    trades = json.loads(row[14]) if row[14] else []
    thinking = json.loads(row[15]) if row[15] else []
    # P3-C: kind_str at index 16; default 'agent' for buggy callers returning empty
    kind = row[16] if len(row) > 16 and row[16] else 'agent'
    return BacktestResult(
        id=row[0], session_id=row[1], agent_id=row[2],
        persona_id=row[3], model_id=row[4],
        start_date=row[5], end_date=row[6],
        initial_capital=row[7], final_equity=row[8],
        stats=stats, zone_stats=zones,
        quality_gate_label=row[11],
        quality_gate_criteria=json.loads(row[12]),
        daily_records=daily_records,
        trades=trades,
        thinking=thinking,
        kind=kind,
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
            from data_schema.backtest_state import (
                ensure_observability_columns, ensure_kind_column,
            )
            ensure_observability_columns(con)
            ensure_kind_column(con)
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
            from data_schema.backtest_state import (
                ensure_observability_columns, ensure_kind_column,
            )
            ensure_observability_columns(con)
            ensure_kind_column(con)
            zone_serial = json.dumps(
                [asdict(z) for z in result.zone_stats], ensure_ascii=False,
            )
            daily_records = getattr(result, 'daily_records', None) or []
            trades = getattr(result, 'trades', None) or []
            thinking = getattr(result, 'thinking', None) or []
            kind = getattr(result, 'kind', 'agent') or 'agent'
            con.execute(
                '''INSERT OR REPLACE INTO backtest_results
                   (id, session_id, agent_id, persona_id, model_id,
                    start_date, end_date, initial_capital, final_equity,
                    stats_json, zone_stats_json,
                    quality_gate_label, quality_gate_json,
                    daily_records_json, trades_json, thinking_json, kind_str)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (result.id, result.session_id, result.agent_id,
                 result.persona_id, result.model_id,
                 result.start_date, result.end_date,
                 result.initial_capital, result.final_equity,
                 json.dumps(asdict(result.stats), ensure_ascii=False),
                 zone_serial,
                 result.quality_gate_label,
                 json.dumps(result.quality_gate_criteria, ensure_ascii=False),
                 json.dumps(daily_records, ensure_ascii=False, default=str),
                 json.dumps(trades, ensure_ascii=False, default=str),
                 json.dumps(thinking, ensure_ascii=False, default=str),
                 kind),
            )
            con.commit()
        finally:
            con.close()

    def _select_cols(self):
        return ('id, session_id, agent_id, persona_id, model_id, '
                'start_date, end_date, initial_capital, final_equity, '
                'stats_json, zone_stats_json, quality_gate_label, '
                'quality_gate_json, daily_records_json, '
                'trades_json, thinking_json, kind_str')

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

    def list_sessions(self, limit: int = 50) -> list:
        import json as _json
        con = sqlite3.connect(self._db_path)
        try:
            con.executescript(SCHEMA_BACKTEST_SESSIONS)
            con.executescript(SCHEMA_BACKTEST_RESULTS)
            # Also ensure baseline_results exists so the subquery doesn't crash
            # on first call. The baselines schema lives in a sibling module.
            try:
                from data_schema.baseline_state import SCHEMA_BASELINE_RESULTS
                con.executescript(SCHEMA_BASELINE_RESULTS)
            except Exception:  # noqa: BLE001
                pass
            rows = con.execute(
                '''SELECT s.id, s.start_date, s.end_date, s.agent_ids, s.notes,
                          s.created_at,
                          (SELECT COUNT(*) FROM backtest_results WHERE session_id=s.id) AS agent_ct,
                          (SELECT COUNT(*) FROM baseline_results WHERE session_id=s.id) AS baseline_ct
                   FROM backtest_sessions s
                   ORDER BY s.created_at DESC LIMIT ?''',
                (limit,),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            con.close()
        return [
            {
                'session_id': r[0],
                'start_date': r[1],
                'end_date': r[2],
                'agent_ids': _json.loads(r[3]) if r[3] else [],
                'notes': r[4],
                'created_at': r[5],
                'agent_count': r[6],
                'baseline_count': r[7],
            }
            for r in rows
        ]
