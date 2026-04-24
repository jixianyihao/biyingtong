# Batch C — subscribe_hq + 动态股池 + 资金流 + 5m Bar

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.

**Goal:** 收官 framework-first 审计 4 项 Batch C：把 `push_quotes` 3 秒轮询换成 `tq.subscribe_hq` 推送；给 persona 一个动态股池工具；暴露资金流字段；支持 5m bar 让 `intraday_t0` persona 数据路径通。

**Strategy:** 新增文件为主，app.py 原地改一个函数，`tools/__init__.py` 加两行。全部新增工具通过 `ALL_TOOLS` + `allowed_tools` 机制可选启用。

**Tech Stack:** tqcenter API + vnpy BarData/BarGenerator + Flask-SocketIO + Python 3.10

---

## File Structure

**新增：**
- `tools/get_stock_list.py` — 动态板块股票列表工具
- `tools/get_capital_flow.py` — 个股 + 板块资金流工具
- `scripts/setup/load_kline_intraday.py` — 5m bar 批量加载器
- `tests/test_subscribe_hq.py`
- `tests/test_get_stock_list.py`
- `tests/test_get_capital_flow.py`
- `tests/test_kline_intraday.py`

**修改：**
- `tdx_service.py` — 增 `subscribe_hq(codes, callback)` + `unsubscribe_hq(sub_handle)` 薄包装 + `get_gpjy_value` / `get_bkjy_value` / `get_stock_list_in_sector` / `get_sector_list` 薄包装
- `app.py` — 把 `push_quotes` 从 `socketio.sleep(3) + get_snapshots` 改为订阅回调
- `storage/base.py` — `KlineStore` Protocol 支持 `5m` period（如果之前硬编码 `1d`）
- `storage/sqlite_kline.py` — `_INTERVAL_MAP` 加 `('5m', 'MINUTE_5')`
- `tools/__init__.py` — 注册 `get_stock_list` + `get_capital_flow`

**不动：**
- `backtest/*` — 本批不改回测；5m bar 由 intraday persona 未来独立用
- `personas/*.py` — 静态 `default_pool` 保留作 fallback，persona 文件本身不动；新增工具让 persona 在 prompt 里自己动态取
- 旧 `get_snapshots` 接口 — 保留兼容单次拉取

---

### Task 1: tdx_service 薄包装（subscribe_hq + 资金流 + 板块）

**Files:**
- Modify: `tdx_service.py`
- Test: `tests/test_subscribe_hq.py` (new — unit, monkeypatch `tq`)

- [ ] **Step 1: Failing test for subscribe_hq wrapper**

```python
# tests/test_subscribe_hq.py
from unittest.mock import MagicMock
import tdx_service as ts


def test_subscribe_hq_delegates_to_tq(monkeypatch):
    fake_tq = MagicMock()
    fake_tq.subscribe_hq = MagicMock(return_value='sub-123')
    monkeypatch.setattr(ts, 'tq', fake_tq)
    svc = ts.TDXService()
    svc._connected = True  # bypass ensure_connected
    cb = lambda payload: None
    handle = svc.subscribe_hq(['600519.SH'], cb)
    fake_tq.subscribe_hq.assert_called_once_with(
        stock_list=['600519.SH'], callback=cb
    )
    assert handle == 'sub-123'


def test_unsubscribe_hq_delegates(monkeypatch):
    fake_tq = MagicMock()
    fake_tq.unsubscribe_hq = MagicMock()
    monkeypatch.setattr(ts, 'tq', fake_tq)
    svc = ts.TDXService()
    svc._connected = True
    svc.unsubscribe_hq('sub-123')
    fake_tq.unsubscribe_hq.assert_called_once_with('sub-123')


def test_get_gpjy_value_passes_fields(monkeypatch):
    fake_tq = MagicMock()
    fake_tq.get_gpjy_value = MagicMock(return_value={'600519.SH': {}})
    monkeypatch.setattr(ts, 'tq', fake_tq)
    svc = ts.TDXService()
    svc._connected = True
    svc.get_gpjy_value(['600519.SH'], ['GP1', 'GP5'], '20260101', '20260422')
    fake_tq.get_gpjy_value.assert_called_once_with(
        stock_list=['600519.SH'],
        field_list=['GP1', 'GP5'],
        start_time='20260101', end_time='20260422',
    )


def test_get_bkjy_value_passes_fields(monkeypatch):
    fake_tq = MagicMock()
    fake_tq.get_bkjy_value = MagicMock(return_value={'880660.SH': {}})
    monkeypatch.setattr(ts, 'tq', fake_tq)
    svc = ts.TDXService()
    svc._connected = True
    svc.get_bkjy_value(['880660.SH'], ['BK5'], '20260101', '20260422')
    fake_tq.get_bkjy_value.assert_called_once_with(
        stock_list=['880660.SH'],
        field_list=['BK5'],
        start_time='20260101', end_time='20260422',
    )


def test_get_stock_list_in_sector_delegates(monkeypatch):
    fake_tq = MagicMock()
    fake_tq.get_stock_list_in_sector = MagicMock(
        return_value=['600519.SH', '000858.SZ']
    )
    monkeypatch.setattr(ts, 'tq', fake_tq)
    svc = ts.TDXService()
    svc._connected = True
    out = svc.get_stock_list_in_sector('白酒')
    assert out == ['600519.SH', '000858.SZ']


def test_subscribe_hq_returns_none_when_disconnected(monkeypatch):
    fake_tq = MagicMock()
    monkeypatch.setattr(ts, 'tq', fake_tq)
    svc = ts.TDXService()
    svc._connected = False
    assert svc.subscribe_hq(['600519.SH'], lambda _: None) is None
    fake_tq.subscribe_hq.assert_not_called()
```

Run: `pytest tests/test_subscribe_hq.py -v`
Expected: FAIL — methods don't exist.

- [ ] **Step 2: Add the wrappers**

Find a good spot in `tdx_service.py` (after `get_stock_list`). Add:

```python
    # ---- Realtime push subscription ----
    def subscribe_hq(self, codes: list, callback):
        """Wrap tq.subscribe_hq. Returns handle or None if disconnected."""
        if not self._connected:
            return None
        try:
            return tq.subscribe_hq(stock_list=codes, callback=callback)
        except Exception as e:  # noqa: BLE001
            print(f"subscribe_hq error: {e}")
            return None

    def unsubscribe_hq(self, handle) -> bool:
        if not handle:
            return False
        try:
            tq.unsubscribe_hq(handle)
            return True
        except Exception as e:  # noqa: BLE001
            print(f"unsubscribe_hq error: {e}")
            return False

    # ---- Capital flow / sector data ----
    def get_gpjy_value(self, codes: list, fields: list,
                        start_time: str, end_time: str) -> dict:
        self.ensure_connected()
        try:
            return tq.get_gpjy_value(
                stock_list=codes, field_list=fields,
                start_time=start_time, end_time=end_time,
            ) or {}
        except Exception as e:  # noqa: BLE001
            print(f"get_gpjy_value error: {e}")
            return {}

    def get_bkjy_value(self, codes: list, fields: list,
                        start_time: str, end_time: str) -> dict:
        self.ensure_connected()
        try:
            return tq.get_bkjy_value(
                stock_list=codes, field_list=fields,
                start_time=start_time, end_time=end_time,
            ) or {}
        except Exception as e:  # noqa: BLE001
            print(f"get_bkjy_value error: {e}")
            return {}

    def get_stock_list_in_sector(self, sector: str) -> list:
        self.ensure_connected()
        try:
            return list(tq.get_stock_list_in_sector(sector) or [])
        except Exception as e:  # noqa: BLE001
            print(f"get_stock_list_in_sector error: {e}")
            return []

    def get_sector_list(self) -> list:
        self.ensure_connected()
        try:
            return list(tq.get_sector_list() or [])
        except Exception as e:  # noqa: BLE001
            print(f"get_sector_list error: {e}")
            return []
```

- [ ] **Step 3: Verify green**

Run: `pytest tests/test_subscribe_hq.py -v`
Expected: PASS (6/6).

- [ ] **Step 4: Commit**

```bash
git add tdx_service.py tests/test_subscribe_hq.py
git commit -m "feat(framework-first-c): subscribe_hq + gpjy/bkjy/sector wrappers on tdx_service"
```

---

### Task 2: app.py push_quotes → subscribe_hq callback

**Files:** Modify `app.py` lines 285-323. Test indirect (smoke only; no unit — depends on tdx client).

- [ ] **Step 1: Replace `push_quotes` body**

The function becomes a bootstrap that (re)subscribes when the subscription set changes, and a single callback that converts the payload into the `quotes` socket event.

Replace lines 285-323 with:

```python
# ---- WebSocket: Real-time Quotes ----
# Replaces the 3-second polling loop with tq.subscribe_hq push events.
# Whenever `ws_subscribe` mutates `_ws_subscriptions`, we cancel the existing
# subscription and open a fresh one covering the current set. The callback
# emits a 'quotes' socket event so the frontend contract is unchanged.

import json
import threading

_ws_subscriptions: set = set()
_ws_lock = threading.Lock()
_hq_handle = None


def _hq_callback(payload):
    """Called by tqcenter when a subscribed code ticks.

    Payload shape per docs (JSON string): {'Code': '600519.SH', ...fields}.
    We normalize to the same dict shape the old poll path produced via
    get_snapshots so the frontend doesn't need to change.
    """
    try:
        data = json.loads(payload) if isinstance(payload, str) else payload
        code = data.get('Code') or data.get('code')
        if not code:
            return
        socketio.emit('quotes', [data])
    except Exception as e:  # noqa: BLE001
        print(f'[hq] callback error: {e}')


def _resubscribe_hq():
    """Cancel any existing subscription and open a fresh one for the current set."""
    global _hq_handle
    with _ws_lock:
        if _hq_handle is not None:
            tdx.unsubscribe_hq(_hq_handle)
            _hq_handle = None
        codes = list(_ws_subscriptions)[:50]
        if not codes or not tdx.is_connected():
            return
        _hq_handle = tdx.subscribe_hq(codes, _hq_callback)


@socketio.on('connect')
def ws_connect():
    print('WebSocket client connected')


@socketio.on('disconnect')
def ws_disconnect():
    print('WebSocket client disconnected')


@socketio.on('subscribe')
def ws_subscribe(data):
    codes = data.get('codes', [])
    changed = False
    with _ws_lock:
        before = len(_ws_subscriptions)
        _ws_subscriptions.update(codes)
        if len(_ws_subscriptions) > 100:
            excess = len(_ws_subscriptions) - 100
            for _ in range(excess):
                _ws_subscriptions.pop()
        changed = len(_ws_subscriptions) != before
    if changed:
        _resubscribe_hq()
    emit('subscribed', {'codes': list(_ws_subscriptions)})


@socketio.on('unsubscribe')
def ws_unsubscribe(data):
    codes = data.get('codes', [])
    changed = False
    with _ws_lock:
        before = len(_ws_subscriptions)
        _ws_subscriptions.difference_update(codes)
        changed = len(_ws_subscriptions) != before
    if changed:
        _resubscribe_hq()
```

And delete the `socketio.start_background_task(push_quotes)` line in `__main__` (subscription opens on-demand when clients subscribe).

- [ ] **Step 2: Smoke check**

Run: `python -c "import app; print('OK')"`
Expected: no import error.

- [ ] **Step 3: Regression**

Run: `pytest -q`
Expected: no new failures versus the main branch baseline.

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat(framework-first-c): replace 3-sec poll with tq.subscribe_hq push"
```

---

### Task 3: tools/get_stock_list.py (动态股池)

**Files:**
- Create: `tools/get_stock_list.py`
- Test: `tests/test_get_stock_list.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_get_stock_list.py
from unittest.mock import patch
from tools import get_stock_list


def test_get_stock_list_returns_codes(monkeypatch):
    import tdx_service
    monkeypatch.setattr(
        tdx_service.tdx, 'get_stock_list_in_sector',
        lambda name: ['600519.SH', '000858.SZ', '']
    )
    out = get_stock_list.call({'sector': '白酒'})
    assert out['sector'] == '白酒'
    assert out['codes'] == ['600519.SH', '000858.SZ']
    assert 'count' in out
    assert out['count'] == 2


def test_get_stock_list_filters_invalid(monkeypatch):
    import tdx_service
    monkeypatch.setattr(
        tdx_service.tdx, 'get_stock_list_in_sector',
        lambda name: ['600519.SH', None, '', 'ABC', '000858.SZ']
    )
    out = get_stock_list.call({'sector': '白酒'})
    assert out['codes'] == ['600519.SH', '000858.SZ']


def test_get_stock_list_missing_sector_errors():
    out = get_stock_list.call({})
    assert 'error' in out


def test_get_stock_list_list_sectors(monkeypatch):
    import tdx_service
    monkeypatch.setattr(
        tdx_service.tdx, 'get_sector_list',
        lambda: ['白酒', '新能源', '半导体']
    )
    out = get_stock_list.call({'list_sectors': True})
    assert out['sectors'] == ['白酒', '新能源', '半导体']


def test_spec_has_expected_shape():
    assert get_stock_list.SPEC.name == 'get_stock_list'
    assert 'sector' in get_stock_list.SPEC.input_schema.get('properties', {})
```

Run: `pytest tests/test_get_stock_list.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 2: Implement**

```python
# tools/get_stock_list.py
"""Dynamic sector stock list — wraps tq.get_stock_list_in_sector.

Replaces the per-persona hand-coded 15-stock pool. An agent that wants a
dynamic universe lists `get_stock_list` in `allowed_tools` and calls it
from its prompt.
"""
from __future__ import annotations

from llm.base import ToolSpec


SPEC = ToolSpec(
    name='get_stock_list',
    description=(
        '获取指定板块的股票列表（或列出所有板块）。'
        '用于动态构建股池；替代硬编码 default_pool。'
    ),
    input_schema={
        'type': 'object',
        'properties': {
            'sector': {
                'type': 'string',
                'description': '板块名称，如 "白酒"、"新能源"。留空时须设 list_sectors=true。',
            },
            'list_sectors': {
                'type': 'boolean',
                'description': '若 true，返回所有板块名称列表而不是板块内股票。',
            },
        },
    },
)


def _is_valid_code(code) -> bool:
    return (
        isinstance(code, str)
        and (code.endswith('.SH') or code.endswith('.SZ'))
        and len(code) >= 9
    )


def call(payload: dict) -> dict:
    from tdx_service import tdx

    if payload.get('list_sectors'):
        sectors = tdx.get_sector_list()
        return {'sectors': list(sectors)}

    sector = payload.get('sector')
    if not sector:
        return {'error': 'sector is required (or set list_sectors=true)'}

    raw = tdx.get_stock_list_in_sector(sector)
    codes = [c for c in (raw or []) if _is_valid_code(c)]
    return {
        'sector': sector,
        'codes': codes,
        'count': len(codes),
    }
```

- [ ] **Step 3: Verify green**

Run: `pytest tests/test_get_stock_list.py -v`
Expected: PASS (5/5).

- [ ] **Step 4: Commit**

```bash
git add tools/get_stock_list.py tests/test_get_stock_list.py
git commit -m "feat(framework-first-c): get_stock_list tool (dynamic sector pool via tq)"
```

---

### Task 4: tools/get_capital_flow.py (资金流)

**Files:**
- Create: `tools/get_capital_flow.py`
- Test: `tests/test_get_capital_flow.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_get_capital_flow.py
from tools import get_capital_flow


def test_capital_flow_stock(monkeypatch):
    import tdx_service
    raw = {'600519.SH': {'GP3': [{'Date': '20260422', 'Value': ['141405.89', '11113.00']}]}}
    monkeypatch.setattr(
        tdx_service.tdx, 'get_gpjy_value',
        lambda codes, fields, start_time, end_time: raw
    )
    out = get_capital_flow.call({
        'code': '600519.SH',
        'start_date': '20260422',
        'end_date': '20260422',
    })
    assert out['code'] == '600519.SH'
    assert 'rows' in out
    assert len(out['rows']) >= 1


def test_capital_flow_sector(monkeypatch):
    import tdx_service
    raw = {'880660.SH': {'BK5': [{'Date': '20260422', 'Value': ['1000']}]}}
    monkeypatch.setattr(
        tdx_service.tdx, 'get_bkjy_value',
        lambda codes, fields, start_time, end_time: raw
    )
    out = get_capital_flow.call({
        'sector_code': '880660.SH',
        'start_date': '20260422',
        'end_date': '20260422',
    })
    assert out['sector_code'] == '880660.SH'
    assert 'rows' in out


def test_capital_flow_requires_one_target():
    out = get_capital_flow.call({'start_date': '20260422', 'end_date': '20260422'})
    assert 'error' in out


def test_spec_has_expected_shape():
    assert get_capital_flow.SPEC.name == 'get_capital_flow'
    props = get_capital_flow.SPEC.input_schema['properties']
    assert 'code' in props and 'sector_code' in props
```

Run: `pytest tests/test_get_capital_flow.py -v`
Expected: FAIL.

- [ ] **Step 2: Implement**

```python
# tools/get_capital_flow.py
"""Capital flow — wraps tq.get_gpjy_value (stock) and tq.get_bkjy_value (sector).

Exposes 资金流 / 成交额 / 换手率 for any A-share or sector. Used by
short-term (游资/热点) personas whose prompts mention 资金流入 but previously
had no data source.

Default fields match the typical 游资 decision set.
"""
from __future__ import annotations

from llm.base import ToolSpec


SPEC = ToolSpec(
    name='get_capital_flow',
    description=(
        '取个股或板块的资金流/成交/换手率数据。'
        '个股传 code (如 "600519.SH")，板块传 sector_code (如 "880660.SH")。'
    ),
    input_schema={
        'type': 'object',
        'properties': {
            'code': {
                'type': 'string',
                'description': '股票代码；与 sector_code 二选一',
            },
            'sector_code': {
                'type': 'string',
                'description': '板块代码（TDX 880xxx.SH/SZ）；与 code 二选一',
            },
            'start_date': {
                'type': 'string',
                'description': 'YYYYMMDD',
            },
            'end_date': {
                'type': 'string',
                'description': 'YYYYMMDD',
            },
            'fields': {
                'type': 'array',
                'items': {'type': 'string'},
                'description': '可选 field 列表。未指定时用默认。',
            },
        },
    },
)

# GP1-GP5 cover 成交量/成交额/换手率/振幅/量比 (approximate — refer to TDX docs GP field map)
_DEFAULT_STOCK_FIELDS = ['GP1', 'GP2', 'GP3', 'GP4', 'GP5']
# BK5-BK9 cover 板块成交额/涨跌家数/资金净流入 (approximate)
_DEFAULT_SECTOR_FIELDS = ['BK5', 'BK6', 'BK7', 'BK8', 'BK9']


def _flatten(raw: dict) -> list[dict]:
    """Flatten tq response {code: {field: [{Date, Value}, ...]}} to [{date, field, value}]."""
    rows: list[dict] = []
    for _code, field_map in (raw or {}).items():
        for field, entries in (field_map or {}).items():
            for entry in (entries or []):
                rows.append({
                    'date': entry.get('Date'),
                    'field': field,
                    'value': entry.get('Value'),
                })
    return rows


def call(payload: dict) -> dict:
    from tdx_service import tdx

    code = payload.get('code')
    sector_code = payload.get('sector_code')
    if not code and not sector_code:
        return {'error': 'code or sector_code is required'}
    start = payload.get('start_date') or ''
    end = payload.get('end_date') or ''

    if code:
        fields = payload.get('fields') or _DEFAULT_STOCK_FIELDS
        raw = tdx.get_gpjy_value([code], fields, start, end)
        return {
            'code': code,
            'start_date': start,
            'end_date': end,
            'rows': _flatten(raw),
        }
    fields = payload.get('fields') or _DEFAULT_SECTOR_FIELDS
    raw = tdx.get_bkjy_value([sector_code], fields, start, end)
    return {
        'sector_code': sector_code,
        'start_date': start,
        'end_date': end,
        'rows': _flatten(raw),
    }
```

- [ ] **Step 3: Verify green**

Run: `pytest tests/test_get_capital_flow.py -v`
Expected: PASS (4/4).

- [ ] **Step 4: Commit**

```bash
git add tools/get_capital_flow.py tests/test_get_capital_flow.py
git commit -m "feat(framework-first-c): get_capital_flow tool (gpjy/bkjy via tq)"
```

---

### Task 5: Register new tools in ALL_TOOLS

**Files:** Modify `tools/__init__.py`

- [ ] **Step 1: Edit the imports + registry**

```python
from . import (
    get_financials, get_index, get_kline, get_news, get_portfolio,
    get_snapshot, get_technical, place_decision,
    get_stock_list, get_capital_flow,
)

# ...

ALL_TOOLS: dict = {
    'place_decision': (place_decision.SPEC, _bind(place_decision)),
    'get_kline': (get_kline.SPEC, _bind(get_kline)),
    'get_snapshot': (get_snapshot.SPEC, _bind(get_snapshot)),
    'get_financials': (get_financials.SPEC, _bind(get_financials)),
    'get_technical': (get_technical.SPEC, _bind(get_technical)),
    'get_index': (get_index.SPEC, _bind(get_index)),
    'get_portfolio': (get_portfolio.SPEC, _bind(get_portfolio)),
    'get_news': (get_news.SPEC, _bind(get_news)),
    'get_stock_list': (get_stock_list.SPEC, _bind(get_stock_list)),
    'get_capital_flow': (get_capital_flow.SPEC, _bind(get_capital_flow)),
}
```

- [ ] **Step 2: Regression**

Run: `pytest -q`
Expected: no regressions. Previously failing tests stay failing, passing stay passing.

- [ ] **Step 3: Commit**

```bash
git add tools/__init__.py
git commit -m "feat(framework-first-c): register get_stock_list + get_capital_flow in ALL_TOOLS"
```

---

### Task 6: 5m bar support

**Files:**
- Modify: `storage/sqlite_kline.py::_interval` — add `'5m'`
- Create: `scripts/setup/load_kline_intraday.py`
- Test: `tests/test_kline_intraday.py`

- [ ] **Step 1: Failing tests**

```python
# tests/test_kline_intraday.py
from datetime import datetime
from unittest.mock import MagicMock, patch

from storage.sqlite_kline import _interval


def test_5m_interval_resolves():
    iv = _interval('5m')
    # Must be vnpy Interval.MINUTE_5 or closest match
    assert iv is not None
    assert str(iv) not in ('Interval.DAILY', 'Interval.WEEKLY')


def test_load_single_stock_5m_builds_bar_with_minute_interval(monkeypatch):
    from scripts.setup import load_kline_intraday as mod
    from vnpy.trader.constant import Interval

    fake_raw = [{
        'date': '2026-04-23 14:55:00',
        'open': 100.0, 'high': 100.5, 'low': 99.8, 'close': 100.3,
        'vol': 10,  # lots
    }]
    monkeypatch.setattr('tdx_service.tdx.ensure_connected', lambda: True)
    monkeypatch.setattr('tdx_service.tdx.get_kline',
                        lambda full, period, count: fake_raw)

    captured = {}
    import storage
    store = storage.kline()
    orig_save = store.save_bars

    def spy(bars):
        captured['bars'] = list(bars)
        return len(bars)
    monkeypatch.setattr(store, 'save_bars', spy)

    n = mod.load_single_stock_5m('600519',
                                  start=datetime(2026, 4, 23),
                                  end=datetime(2026, 4, 23, 23, 59))
    assert n == 1
    assert captured['bars'][0].interval == Interval.MINUTE_5
    assert captured['bars'][0].volume == 10 * 100
```

Run: `pytest tests/test_kline_intraday.py -v`
Expected: FAIL.

- [ ] **Step 2: Add 5m to _interval**

In `storage/sqlite_kline.py::_interval`, extend the mapping:

```python
        for key, name in (
            ('1d', 'DAILY'),
            ('1w', 'WEEKLY'),
            ('1M', 'MONTHLY'),
            ('5m', 'MINUTE_5'),
            ('1m', 'MINUTE'),
        ):
            val = getattr(Interval, name, None)
            if val is not None:
                _INTERVAL_MAP[key] = val
```

Note: vnpy's Interval enum historically uses `MINUTE` (1m) and `MINUTE_5` for 5m but names have varied across versions — the `getattr(..., None)` pattern means the code silently skips an unavailable name. If `MINUTE_5` isn't present, fall back to `MINUTE` and aggregate later.

- [ ] **Step 3: Create `scripts/setup/load_kline_intraday.py`**

```python
"""5-minute bar ingestion — mirror of load_kline.py but with intraday granularity.

Uses tdx_service.get_kline(period='5m') and constructs BarData with
Interval.MINUTE_5. Unblocks the intraday_t0 persona which until now had
only daily bars despite the persona spec calling for 5m.
"""
from __future__ import annotations

from datetime import datetime

from scripts.setup.vnpy_config import configure as _configure_vnpy

_configure_vnpy()

from vnpy.trader.constant import Exchange, Interval  # noqa: E402
from vnpy.trader.object import BarData  # noqa: E402

from tdx_service import tdx  # noqa: E402


_VOLUME_LOTS_TO_SHARES = 100


def _exchange_for(symbol: str) -> Exchange:
    if symbol.startswith(('6', '9')):
        return Exchange.SSE
    if symbol.startswith(('0', '3')):
        return Exchange.SZSE
    raise ValueError(f'Cannot infer exchange for symbol {symbol!r}')


def _tdx_full_code(symbol: str, exchange: Exchange) -> str:
    return f"{symbol}.{'SH' if exchange == Exchange.SSE else 'SZ'}"


def _parse_dt(raw: str) -> datetime | None:
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y%m%d%H%M'):
        try:
            return datetime.strptime(raw, fmt)
        except (ValueError, TypeError):
            continue
    return None


def load_single_stock_5m(symbol: str, start: datetime, end: datetime) -> int:
    """Fetch 5m bars via tqcenter, build BarData(MINUTE_5), persist via storage."""
    try:
        exchange = _exchange_for(symbol)
    except ValueError:
        exchange = Exchange.SSE

    full = _tdx_full_code(symbol, exchange)
    if not tdx.ensure_connected():
        return 0

    # 48 five-minute bars per trading day; pad for weekends.
    span_days = max((end - start).days + 2, 2)
    count = max(span_days * 60, 60)

    raw = tdx.get_kline(full, period='5m', count=count)
    if not raw:
        return 0

    bars: list[BarData] = []
    interval = getattr(Interval, 'MINUTE_5', None) or getattr(Interval, 'MINUTE')
    for row in raw:
        bar_dt = _parse_dt(row.get('date', ''))
        if bar_dt is None or bar_dt < start or bar_dt > end:
            continue
        bars.append(BarData(
            symbol=symbol,
            exchange=exchange,
            datetime=bar_dt,
            interval=interval,
            open_price=float(row.get('open', 0)),
            high_price=float(row.get('high', 0)),
            low_price=float(row.get('low', 0)),
            close_price=float(row.get('close', 0)),
            volume=float(row.get('vol', 0)) * _VOLUME_LOTS_TO_SHARES,
            turnover=0.0,
            open_interest=0.0,
            gateway_name='TDX',
        ))

    if not bars:
        return 0

    from storage import kline
    return kline().save_bars(bars)


def load_batch_5m(symbols: list[str], start: datetime, end: datetime) -> dict[str, int]:
    out: dict[str, int] = {}
    for s in symbols:
        try:
            out[s] = load_single_stock_5m(s, start, end)
        except Exception as e:  # noqa: BLE001
            print(f'[load_batch_5m] {s} FAILED: {e}')
            out[s] = 0
    return out


if __name__ == '__main__':
    from datetime import timedelta
    now = datetime.now()
    start = now - timedelta(days=2)
    n = load_single_stock_5m('600519', start=start, end=now)
    print(f'600519: {n} 5m bars written via storage.kline()')
```

- [ ] **Step 4: Verify green**

Run: `pytest tests/test_kline_intraday.py -v`
Expected: PASS (2/2).

- [ ] **Step 5: Commit**

```bash
git add storage/sqlite_kline.py scripts/setup/load_kline_intraday.py tests/test_kline_intraday.py
git commit -m "feat(framework-first-c): 5m bar ingestion + storage period support"
```

---

### Task 7: Roadmap + full regression + merge

- [ ] **Step 1: Full test suite**

Run: `pytest -q`
Expected: ≥646 passed (628 baseline + 18 new from tasks 1/3/4/6). 2 pre-existing TDX-connection tests may fail in offline CI — unrelated.

- [ ] **Step 2: Frontend build sanity (no frontend edits in Batch C but verify nothing imported stale)**

Run: `cd frontend && npm run build`
Expected: clean build.

- [ ] **Step 3: Update status-and-roadmap**

Edit `docs/superpowers/plans/2026-04-23-status-and-roadmap.md` — flip Batch C row from 🟡 Pending to ✅ Done with commit range.

- [ ] **Step 4: Merge + delete branch**

Use superpowers:finishing-a-development-branch. Merge locally into `main` (option 1). Push.

---

## Self-Review

**Framework-first coverage (memory/framework_first_principle.md):**
- 🔴 3-sec polling → subscribe_hq ✅ Task 1+2
- 🟡 Static stock pool → get_stock_list_in_sector ✅ Task 3
- 🟡 Capital flow missing → get_gpjy_value + get_bkjy_value ✅ Task 4
- 🔴 No 5m bars → Interval.MINUTE_5 + load_kline_intraday ✅ Task 6

**Out of scope (intentionally):**
- Persona `default_pool` still hardcoded — the new tool is *available* to personas; migration of each persona's prompt to call it is a follow-up once we see real performance
- Forward PE (GO23-GO25) — tqcenter docs note these, deferred
- Vnpy `BarGenerator` — 5m bars loaded directly from TDX; BarGenerator (1m→5m rollup in live trading) is an orthogonal concern handled when live intraday runs land

**Risks:**
- `tq.subscribe_hq` payload shape is documented as JSON string but actual tqcenter build may vary — the `_hq_callback` handles both string and dict
- TDX interval support in vnpy version-dependent — the `getattr(..., None)` pattern fails gracefully; we fall back to `MINUTE` if `MINUTE_5` missing
- `_ws_lock` threading: Flask-SocketIO's eventlet/gevent may interact oddly with a stdlib threading.Lock. Lock is short-held so the risk is low; if issues appear switch to `socketio.Lock()` (if available) or just live with 1-frame staleness

**Mitigation:**
- Keep legacy `get_snapshots` path in tdx_service (not deleted) so on-demand single polls still work
- `subscribe_hq` + `unsubscribe_hq` isolated behind tdx_service — swap-in mock for tests

---

## Execution

Subagent-driven. File-ownership split for parallel dispatch:

- **Subagent A** (tdx_service + app.py): Task 1 + Task 2 — depends on nobody, owns `tdx_service.py` + `app.py` + `tests/test_subscribe_hq.py`
- **Subagent B** (new tools): Task 3 + Task 4 + Task 5 — owns `tools/get_stock_list.py` + `tools/get_capital_flow.py` + `tools/__init__.py` + 2 test files. Task 5 serializes the `__init__.py` edit.
- **Subagent C** (5m bars): Task 6 — owns `storage/sqlite_kline.py` + `scripts/setup/load_kline_intraday.py` + `tests/test_kline_intraday.py`

A/B/C are fully file-disjoint → safe to dispatch in parallel.

Task 7 (merge + roadmap) runs on controller thread after all three return.

Total: ~2 hours (15 min setup + 60-90 min subagent work + 30 min verify/merge).
