import sys
import json
import threading
from pathlib import Path

# Add TDX SDK to Python path
TDX_SDK_PATH = r'C:\new_tdx_mock\PYPlugins\sys'
if TDX_SDK_PATH not in sys.path:
    sys.path.insert(0, TDX_SDK_PATH)

import pandas as pd
from tqcenter import tq, tqconst


class TDXService:
    """Thread-safe singleton wrapping the TDX SDK."""
    _instance = None
    _lock = threading.Lock()
    _initialized = False
    _name_cache = {}

    INDICES = {
        '000001.SH': '上证指数',
        '399001.SZ': '深证成指',
        '399006.SZ': '创业板指',
        '000300.SH': '沪深300',
        '000688.SH': '科创50',
    }

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def initialize(self):
        if self._initialized:
            return True
        try:
            init_path = str(Path(TDX_SDK_PATH).parent.parent)
            tq.initialize(init_path)
            self._initialized = True
            return True
        except Exception as e:
            print(f"TDX initialization failed: {e}")
            return False

    def ensure_connected(self):
        if not self._initialized:
            return self.initialize()
        return True

    def is_connected(self):
        return self._initialized

    # ---- Market Data ----

    def _get_stock_name(self, stock_code):
        """Get stock name with caching."""
        if stock_code in self._name_cache:
            return self._name_cache[stock_code]
        try:
            info = tq.get_stock_info(stock_code=stock_code)
            if isinstance(info, list) and len(info) > 0:
                info = info[0]
            name = info.get('Name', '') if isinstance(info, dict) else ''
            if name:
                self._name_cache[stock_code] = name
            return name
        except Exception:
            return ''

    def get_indices(self):
        """Get real-time data for major market indices."""
        self.ensure_connected()
        codes = list(self.INDICES.keys())
        results = []
        for code in codes:
            try:
                snap = tq.get_market_snapshot(stock_code=code)
                if isinstance(snap, list) and len(snap) > 0:
                    snap = snap[0]
                if not snap:
                    continue
                price = float(snap.get('Now', 0) or 0)
                last_close = float(snap.get('LastClose', 0) or 0)
                if price == 0:
                    continue
                chg = round(price - last_close, 2) if last_close else 0
                pct = round(chg / last_close * 100, 2) if last_close else 0
                results.append({
                    'name': self.INDICES.get(code, code),
                    'code': code,
                    'price': price,
                    'chg': chg,
                    'pct': pct,
                })
            except Exception as e:
                print(f"Failed to get index {code}: {e}")
        return results

    def get_kline(self, stock_code, period='1d', count=80, dividend_type='front'):
        """Get K-line data as a list of OHLCV dicts."""
        self.ensure_connected()
        try:
            data = tq.get_market_data(
                field_list=['Open', 'High', 'Low', 'Close', 'Volume'],
                stock_list=[stock_code],
                period=period,
                count=count,
                dividend_type=dividend_type,
            )
            if not data or 'Close' not in data:
                return []
            df_close = data['Close']
            df_open = data.get('Open', df_close)
            df_high = data.get('High', df_close)
            df_low = data.get('Low', df_close)
            df_vol = data.get('Volume', pd.DataFrame())

            bars = []
            for i, dt in enumerate(df_close.index):
                try:
                    bar = {
                        'date': dt.strftime('%Y-%m-%d') if hasattr(dt, 'strftime') else str(dt),
                        'open': round(float(df_open.iloc[i][stock_code]) if stock_code in df_open.columns else 0, 2),
                        'high': round(float(df_high.iloc[i][stock_code]) if stock_code in df_high.columns else 0, 2),
                        'low': round(float(df_low.iloc[i][stock_code]) if stock_code in df_low.columns else 0, 2),
                        'close': round(float(df_close.iloc[i][stock_code]) if stock_code in df_close.columns else 0, 2),
                        'vol': int(float(df_vol.iloc[i][stock_code]) if stock_code in df_vol.columns and not df_vol.empty else 0),
                    }
                    bars.append(bar)
                except (ValueError, TypeError, KeyError):
                    continue
            return bars
        except Exception as e:
            print(f"K-line error for {stock_code}: {e}")
            return []

    def get_snapshot(self, stock_code):
        """Get real-time snapshot for a single stock."""
        self.ensure_connected()
        try:
            snap = tq.get_market_snapshot(stock_code=stock_code)
            if isinstance(snap, list) and len(snap) > 0:
                snap = snap[0]
            if not snap:
                return None
            price = float(snap.get('Now', 0) or 0)
            last_close = float(snap.get('LastClose', 0) or 0)
            open_price = float(snap.get('Open', 0) or 0)
            high = float(snap.get('Max', 0) or 0)
            low = float(snap.get('Min', 0) or 0)
            vol = float(snap.get('Volume', 0) or 0)
            amount = float(snap.get('Amount', 0) or 0)
            chg = round(price - last_close, 2) if last_close else 0
            pct = round(chg / last_close * 100, 2) if last_close else 0

            # Bid/Ask are arrays of 5 levels
            buyp = snap.get('Buyp', [])
            buyv = snap.get('Buyv', [])
            sellp = snap.get('Sellp', [])
            sellv = snap.get('Sellv', [])

            result = {
                'code': stock_code,
                'name': snap.get('Name', '') or self._get_stock_name(stock_code),
                'price': price,
                'chg': chg,
                'pct': pct,
                'vol': vol,
                'amount': amount,
                'open': open_price,
                'high': high,
                'low': low,
                'lastClose': last_close,
            }
            # Add 5-level depth if available
            for i in range(5):
                bp = buyp[i] if isinstance(buyp, list) and i < len(buyp) else 0
                bv = buyv[i] if isinstance(buyv, list) and i < len(buyv) else 0
                sp = sellp[i] if isinstance(sellp, list) and i < len(sellp) else 0
                sv = sellv[i] if isinstance(sellv, list) and i < len(sellv) else 0
                result[f'bid{i+1}'] = float(bp) if bp else 0
                result[f'bidVol{i+1}'] = float(bv) if bv else 0
                result[f'ask{i+1}'] = float(sp) if sp else 0
                result[f'askVol{i+1}'] = float(sv) if sv else 0
            return result
        except Exception as e:
            print(f"Snapshot error for {stock_code}: {e}")
            return None

    def get_snapshots(self, stock_codes):
        """Get real-time snapshots for multiple stocks."""
        results = []
        for code in stock_codes:
            snap = self.get_snapshot(code)
            if snap:
                results.append(snap)
        return results

    def get_stock_list(self, market='5'):
        """Get stock list by market code."""
        self.ensure_connected()
        try:
            return tq.get_stock_list(market=market)
        except Exception as e:
            print(f"Stock list error: {e}")
            return []

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

    def get_gp_one_data(self, codes: list, fields: list) -> dict:
        """Fetch per-stock one-shot GO fields (e.g. GO23/24/25 consensus forward PE).

        Wraps tq.get_gp_one_data. Returns {code: {field: value}} or {} on error.
        """
        self.ensure_connected()
        try:
            return tq.get_gp_one_data(
                stock_list=codes, field_list=fields,
            ) or {}
        except Exception as e:  # noqa: BLE001
            print(f"get_gp_one_data error: {e}")
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

    def get_stock_info(self, stock_code):
        """Get basic stock information."""
        self.ensure_connected()
        try:
            info = tq.get_stock_info(stock_code=stock_code)
            if isinstance(info, list) and len(info) > 0:
                info = info[0]
            return info
        except Exception as e:
            print(f"Stock info error for {stock_code}: {e}")
            return None

    # ---- Account & Trading ----

    def get_account_id(self):
        """Get the default stock account handle."""
        self.ensure_connected()
        try:
            return tq.stock_account(account='', account_type='stock')
        except Exception as e:
            print(f"Account error: {e}")
            return -1

    def get_asset(self):
        """Get account asset information."""
        account_id = self.get_account_id()
        if account_id < 0:
            return None
        try:
            return tq.query_stock_asset(account_id=account_id)
        except Exception as e:
            print(f"Asset query error: {e}")
            return None

    def get_positions(self):
        """Get current positions."""
        account_id = self.get_account_id()
        if account_id < 0:
            return []
        try:
            return tq.query_stock_positions(account_id=account_id)
        except Exception as e:
            print(f"Position query error: {e}")
            return []

    def get_orders(self, stock_code=''):
        """Get today's orders."""
        account_id = self.get_account_id()
        if account_id < 0:
            return []
        try:
            return tq.query_stock_orders(account_id=account_id, stock_code=stock_code, cancelable_only=False)
        except Exception as e:
            print(f"Order query error: {e}")
            return []

    def place_order(self, stock_code, side, qty, price, price_type=0):
        """Place an order. side: 'buy' or 'sell'."""
        account_id = self.get_account_id()
        if account_id < 0:
            return {'error': 'Account not available'}
        order_type = tqconst.STOCK_BUY if side == 'buy' else tqconst.STOCK_SELL
        try:
            result = tq.order_stock(
                account_id=account_id,
                stock_code=stock_code,
                order_type=order_type,
                order_volume=int(qty),
                price_type=price_type,
                price=float(price),
            )
            if result == -1:
                return {'error': 'Order failed'}
            return result
        except Exception as e:
            return {'error': str(e)}

    def cancel_order(self, stock_code, order_id):
        """Cancel an existing order."""
        account_id = self.get_account_id()
        if account_id < 0:
            return {'error': 'Account not available'}
        try:
            result = tq.cancel_order_stock(
                account_id=account_id,
                stock_code=stock_code,
                order_id=order_id,
            )
            if result == -1:
                return {'error': 'Cancel failed'}
            return result
        except Exception as e:
            return {'error': str(e)}


tdx = TDXService()
