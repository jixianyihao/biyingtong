import json
from flask import Flask, send_from_directory, request, jsonify
from flask_socketio import SocketIO, emit
from tdx_service import tdx

app = Flask(__name__, static_folder='static', static_url_path='')
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

# P2e REST API blueprint: /api/personas, /api/models, /api/agents,
# /api/backtests, /api/baselines, /api/redlines, /api/audit
from api import api_bp  # noqa: E402
app.register_blueprint(api_bp)


# ---- Startup crash recovery for deployed agents ----

def _pid_alive(pid: int) -> bool:
    """Return True if a process with the given PID is running. Cross-platform.

    On Unix: os.kill(pid, 0) raises ProcessLookupError if dead.
    On Windows: requires looking at the tasklist — use psutil if available,
    otherwise fall back to a best-effort check via os.kill(pid, 0) which
    works slightly differently on Windows but still raises for dead PIDs.
    """
    import os
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # On Unix, PermissionError means the PID exists but we can't signal.
        # Treat as alive.
        return True
    except OSError:
        return False
    return True


def _recover_deployed_agents() -> int:
    """On startup, mark any deployed agent whose subprocess is dead as 'crashed'.
    Returns the number of agents reclassified."""
    import storage
    crashed = 0
    try:
        running = storage.deployed_agents().list_running()
    except Exception:  # noqa: BLE001
        # Fresh install — table doesn't exist yet. Init it and move on.
        storage.deployed_agents().init_schema()
        return 0
    for d in running:
        if not _pid_alive(d.pid):
            storage.deployed_agents().mark_crashed(d.agent_id)
            crashed += 1
    return crashed


# ---- Serve Frontend ----

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('static', path)


# ---- API: Connection Status ----

@app.route('/api/status')
def api_status():
    connected = tdx.is_connected()
    return jsonify({'connected': connected})


@app.route('/api/connect')
def api_connect():
    ok = tdx.initialize()
    return jsonify({'success': ok, 'connected': tdx.is_connected()})


# ---- API: Market Data ----

@app.route('/api/market/indices')
def api_indices():
    data = tdx.get_indices()
    return jsonify(data)


@app.route('/api/market/kline')
def api_kline():
    code = request.args.get('code', '600519.SH')
    period = request.args.get('period', '1d')
    count = int(request.args.get('count', '80'))
    div = request.args.get('dividend_type', 'front')
    data = tdx.get_kline(code, period, count, div)
    return jsonify(data)


@app.route('/api/market/snapshot')
def api_snapshot():
    code = request.args.get('code', '')
    if not code:
        return jsonify({'error': 'code parameter required'}), 400
    data = tdx.get_snapshot(code)
    return jsonify(data)


@app.route('/api/market/snapshots', methods=['POST'])
def api_snapshots():
    body = request.get_json(force=True)
    codes = body.get('codes', [])
    data = tdx.get_snapshots(codes)
    return jsonify(data)


# ---- API: Stock Lists & Info ----

@app.route('/api/stocks/list')
def api_stock_list():
    market = request.args.get('market', '5')
    data = tdx.get_stock_list(market=market)
    return jsonify(data[:500])


@app.route('/api/stocks/info')
def api_stock_info():
    code = request.args.get('code', '')
    if not code:
        return jsonify({'error': 'code parameter required'}), 400
    data = tdx.get_stock_info(code)
    return jsonify(data)


# ---- API: Account & Trading ----

@app.route('/api/account/status')
def api_account_status():
    account_id = tdx.get_account_id()
    if account_id < 0:
        return jsonify({'logged_in': False, 'reason': 'trade_account_not_login'})
    return jsonify({'logged_in': True, 'account_id': account_id})


@app.route('/api/account/asset')
def api_asset():
    account_id = tdx.get_account_id()
    if account_id < 0:
        return jsonify({'error': '交易账户未登录，请在通达信客户端中按F12登录委托', 'code': 'TRADE_NOT_LOGGED_IN'}), 503
    data = tdx.get_asset()
    if data is None:
        return jsonify({'error': '查询资产失败', 'code': 'ASSET_QUERY_FAILED'}), 503
    return jsonify(data)


@app.route('/api/account/positions')
def api_positions():
    account_id = tdx.get_account_id()
    if account_id < 0:
        return jsonify({'error': '交易账户未登录', 'code': 'TRADE_NOT_LOGGED_IN'}), 503
    data = tdx.get_positions()
    return jsonify(data)


@app.route('/api/account/orders')
def api_orders():
    account_id = tdx.get_account_id()
    if account_id < 0:
        return jsonify({'error': '交易账户未登录', 'code': 'TRADE_NOT_LOGGED_IN'}), 503
    code = request.args.get('code', '')
    data = tdx.get_orders(stock_code=code)
    return jsonify(data)


@app.route('/api/trade/order', methods=['POST'])
def api_place_order():
    body = request.get_json(force=True)
    result = tdx.place_order(
        stock_code=body.get('stock_code', ''),
        side=body.get('side', 'buy'),
        qty=body.get('qty', 0),
        price=body.get('price', 0),
        price_type=body.get('price_type', 0),
    )
    return jsonify(result)


@app.route('/api/trade/cancel', methods=['POST'])
def api_cancel_order():
    body = request.get_json(force=True)
    result = tdx.cancel_order(
        stock_code=body.get('stock_code', ''),
        order_id=body.get('order_id', ''),
    )
    return jsonify(result)


# ---- WebSocket: Real-time Quotes ----

_ws_subscriptions = set()


@socketio.on('connect')
def ws_connect():
    print(f'WebSocket client connected')


@socketio.on('disconnect')
def ws_disconnect():
    print(f'WebSocket client disconnected')


@socketio.on('subscribe')
def ws_subscribe(data):
    codes = data.get('codes', [])
    _ws_subscriptions.update(codes)
    if len(_ws_subscriptions) > 100:
        excess = len(_ws_subscriptions) - 100
        for _ in range(excess):
            _ws_subscriptions.pop()
    emit('subscribed', {'codes': list(_ws_subscriptions)})


@socketio.on('unsubscribe')
def ws_unsubscribe(data):
    codes = data.get('codes', [])
    _ws_subscriptions.difference_update(codes)


def push_quotes():
    while True:
        socketio.sleep(3)
        if not _ws_subscriptions or not tdx.is_connected():
            continue
        codes = list(_ws_subscriptions)[:50]
        snapshots = tdx.get_snapshots(codes)
        if snapshots:
            socketio.emit('quotes', snapshots)


# ---- Crash recovery sweep at import time ----
# Runs after all blueprints/routes are registered. Any deployed agent whose
# subprocess is no longer alive gets flipped to 'crashed' so the UI reflects
# reality. Auto-restart is intentionally NOT done here — that's a Phase 2
# policy call; for Phase 1 we just surface the state.
try:
    _crashed_count = _recover_deployed_agents()
    if _crashed_count:
        print(f'[startup] marked {_crashed_count} deployed agent(s) as crashed')
except Exception as e:  # noqa: BLE001
    print(f'[startup] crash recovery skipped: {e}')


if __name__ == '__main__':
    print("Starting 必赢通量化交易终端 backend...")
    print("Connecting to TDX...")
    tdx.initialize()
    print(f"TDX connected: {tdx.is_connected()}")
    socketio.start_background_task(push_quotes)
    socketio.run(app, host='127.0.0.1', port=5000, debug=False)
