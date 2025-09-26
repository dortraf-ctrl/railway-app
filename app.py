import os
import time
import threading
import queue
import json
from datetime import datetime
from typing import List, Dict, Any

from flask import Flask, Response, request, render_template_string
import yfinance as yf

app = Flask(__name__)

# Varsayılan semboller (istediğin kadar ekleyebilirsin)
DEFAULT_TICKERS = os.getenv("TICKERS", "ASELS.IS,THYAO.IS,BIMAS.IS,AKBNK.IS").split(",")

tickers_lock = threading.Lock()
tickers: List[str] = [t.strip() for t in DEFAULT_TICKERS if t.strip()]

# Son fiyatlar burada tutulacak
latest_quotes: Dict[str, Dict[str, Any]] = {}
msg_queue = queue.Queue()  # SSE kuyruğu

def fetch_prices(symbols: List[str]) -> Dict[str, Dict[str, Any]]:
    """Semboller için son fiyatları getirir."""
    data: Dict[str, Dict[str, Any]] = {}
    for sym in symbols:
        try:
            t = yf.Ticker(sym)
            # Hızlı yol: fast_info (yoksa history fallback)
            price = None
            try:
                fi = t.fast_info
                price = fi.get("last_price") or fi.get("lastPrice")
            except Exception:
                pass

            if price is None:
                hist = t.history(period="1d", interval="1m")
                if not hist.empty:
                    price = float(hist["Close"].dropna().iloc[-1])

            if price is not None:
                data[sym] = {
                    "symbol": sym,
                    "price": float(price),
                    "time": datetime.utcnow().strftime("%H:%M:%S"),
                }
        except Exception as e:
            data[sym] = {"symbol": sym, "error": str(e)}
    return data

def notify(payload: Dict[str, Any]):
    """SSE'ye JSON mesaj gönder."""
    msg_queue.put(json.dumps(payload, ensure_ascii=False))

def event_stream():
    # İlk mesaj: mevcut veriler varsa gönder
    if latest_quotes:
        yield f"data: {json.dumps({'type':'snapshot','quotes': latest_quotes}, ensure_ascii=False)}\n\n"
    else:
        yield "data: {\"type\":\"info\",\"message\":\"Bağlandı. İlk veri bekleniyor...\"}\n\n"
    while True:
        msg = msg_queue.get()
        yield f"data: {msg}\n\n"

# HTML (çok basit bir tablo + sembol düzenleme)
INDEX_HTML = """
<!doctype html>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Canlı Hisse Fiyatları</title>
<style>
  body { font-family: -apple-system, system-ui, sans-serif; margin:0; background:#0b0b0b; color:#eee; }
  header { padding:12px 16px; background:#111; border-bottom:1px solid #222; position:sticky; top:0; }
  h1 { margin:0; font-size:18px; }
  #wrap { padding:16px; }
  table { width:100%; border-collapse: collapse; }
  th, td { border-bottom:1px solid #222; padding:10px 8px; text-align:left; }
  .controls { display:flex; gap:8px; margin-bottom:12px; }
  input, button { font-size:16px; padding:10px 12px; border-radius:8px; border:1px solid #333; background:#1a1a1a; color:#eee; }
  .muted { color:#aaa; font-size:12px; }
  .ok { color:#7CFC00; }
</style>
<header><h1>📈 Canlı Hisse Fiyatları (60 sn)</h1></header>
<div id="wrap">
  <div class="controls">
    <input id="symbols" placeholder="Semboller (virgülle): ASELS.IS,THYAO.IS" style="flex:1">
    <button onclick="setSymbols()">Kaydet</button>
  </div>
  <div class="muted">Mevcut semboller: <span id="current"></span></div>
  <table>
    <thead>
      <tr><th>Sembol</th><th>Fiyat</th><th>Saat (UTC)</th><th>Durum</th></tr>
    </thead>
    <tbody id="rows"></tbody>
  </table>
  <p class="muted" id="status">Bağlanıyor...</p>
</div>
<script>
  const rows = document.getElementById('rows');
  const statusEl = document.getElementById('status');
  const current = document.getElementById('current');

  async function setSymbols() {
    const v = document.getElementById('symbols').value.trim();
    if (!v) return;
    localStorage.setItem('symbols', v);
    await fetch('/set?tickers=' + encodeURIComponent(v));
    statusEl.textContent = 'Semboller güncellendi: ' + v + ' (veri geldikçe tablo yenilenecek)';
  }

  function render(quotes) {
    rows.innerHTML = '';
    const syms = Object.keys(quotes).sort();
    current.textContent = syms.join(', ');
    syms.forEach(sym => {
      const q = quotes[sym] || {};
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${sym}</td>
        <td>${q.price !== undefined ? q.price : '-'}</td>
        <td>${q.time || '-'}</td>
        <td>${q.error ? q.error : '<span class="ok">OK</span>'}</td>
      `;
      rows.appendChild(tr);
    });
  }

  const es = new EventSource('/events');
  es.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      if (data.type === 'snapshot' || data.type === 'update') {
        render(data.quotes);
        statusEl.textContent = (data.type === 'update' ? 'Güncellendi' : 'Anlık durum') + ' • ' + new Date().toLocaleTimeString();
      }
    } catch (_) {}
  };

  // İlk açılışta localStorage'daki sembolleri sunucuya bildir
  (async () => {
    const saved = localStorage.getItem('symbols');
    if (saved) {
      document.getElementById('symbols').value = saved;
      await fetch('/set?tickers=' + encodeURIComponent(saved));
    } else {
      statusEl.textContent = 'Varsayılan semboller ile dinleniyor...';
    }
  })();
</script>
"""

@app.route("/")
def index():
    return render_template_string(INDEX_HTML)

@app.route("/events")
def sse():
    return Response(event_stream(), mimetype="text/event-stream")

@app.route("/set")
def set_symbols():
    global tickers
    raw = request.args.get("tickers", "")
    new_list = [s.strip() for s in raw.split(",") if s.strip()]
    if not new_list:
        return "No symbols", 400
    with tickers_lock:
        tickers = new_list
    return "OK", 200

def worker():
    """Her 60 sn’de bir fiyatları çekip SSE ile gönderir."""
    global latest_quotes
    # İlk anlık çekim (uygulama açılır açılmaz)
    with tickers_lock:
        syms = tickers[:]
    latest_quotes = fetch_prices(syms)
    notify({"type": "snapshot", "quotes": latest_quotes})

    while True:
        time.sleep(60)  # 60 sn
        with tickers_lock:
            syms = tickers[:]
        latest_quotes = fetch_prices(syms)
        notify({"type": "update", "quotes": latest_quotes})

# Gunicorn altında da çalışsın diye thread'i burada başlatıyoruz
threading.Thread(target=worker, daemon=True).start()
