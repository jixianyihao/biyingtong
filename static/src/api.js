// BYT API Client — connects frontend to Flask backend
(function() {
  var BASE = '';

  async function get(url) {
    try {
      var res = await fetch(BASE + url);
      if (!res.ok) {
        var err = await res.json().catch(function() { return {}; });
        throw new Error(err.error || 'HTTP ' + res.status);
      }
      return await res.json();
    } catch (e) {
      console.error('API GET error:', url, e);
      throw e;
    }
  }

  async function post(url, body) {
    try {
      var res = await fetch(BASE + url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        var err = await res.json().catch(function() { return {}; });
        throw new Error(err.error || 'HTTP ' + res.status);
      }
      return await res.json();
    } catch (e) {
      console.error('API POST error:', url, e);
      throw e;
    }
  }

  function fmtVol(vol) {
    if (!vol) return '—';
    if (vol >= 100000000) return (vol / 100000000).toFixed(2) + '亿';
    if (vol >= 10000) return (vol / 10000).toFixed(1) + '万';
    return String(Math.round(vol));
  }

  function fmtAmount(amount) {
    if (!amount) return '—';
    if (amount >= 10000) return (amount / 10000).toFixed(2) + '亿';
    return amount.toFixed(2) + '万';
  }

  // WebSocket singleton
  var ws = null;
  var wsListeners = [];

  function connectWS() {
    if (ws && ws.connected) return ws;
    if (typeof io === 'undefined') return null;
    ws = io({ transports: ['websocket'] });
    ws.on('quotes', function(data) {
      wsListeners.forEach(function(fn) { fn(data); });
    });
    ws.on('connect_error', function(err) {
      console.warn('WebSocket error:', err);
    });
    return ws;
  }

  function onQuotes(fn) {
    wsListeners.push(fn);
    return function() { wsListeners = wsListeners.filter(function(f) { return f !== fn; }); };
  }

  function subscribeWS(codes) {
    if (ws && ws.connected) ws.emit('subscribe', { codes: codes });
  }

  function unsubscribeWS(codes) {
    if (ws && ws.connected) ws.emit('unsubscribe', { codes: codes });
  }

  window.BYT = {
    getStatus: function() { return get('/api/status'); },
    connect: function() { return get('/api/connect'); },
    getIndices: function() { return get('/api/market/indices'); },
    getKline: function(code, period, count) { return get('/api/market/kline?code=' + encodeURIComponent(code) + '&period=' + period + '&count=' + count); },
    getSnapshot: function(code) { return get('/api/market/snapshot?code=' + encodeURIComponent(code)); },
    getSnapshots: function(codes) { return post('/api/market/snapshots', { codes: codes }); },
    getStockList: function(market) { return get('/api/stocks/list?market=' + market); },
    getStockInfo: function(code) { return get('/api/stocks/info?code=' + encodeURIComponent(code)); },
    getAccountStatus: function() { return get('/api/account/status'); },
    getAsset: function() { return get('/api/account/asset'); },
    getPositions: function() { return get('/api/account/positions'); },
    getOrders: function(code) { return get('/api/account/orders' + (code ? '?code=' + encodeURIComponent(code) : '')); },
    placeOrder: function(data) { return post('/api/trade/order', data); },
    cancelOrder: function(data) { return post('/api/trade/cancel', data); },
    connectWS: connectWS,
    onQuotes: onQuotes,
    subscribeWS: subscribeWS,
    unsubscribeWS: unsubscribeWS,
    fmtVol: fmtVol,
    fmtAmount: fmtAmount,
  };
})();
