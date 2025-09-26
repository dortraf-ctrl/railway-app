import os
import time
import threading
import queue
from flask import Flask, Response, request, render_template_string

app = Flask(__name__)
msg_queue = queue.Queue()

def notify(text: str):
    ts = time.strftime("%H:%M:%S")
    msg_queue.put(f"[{ts}] {text}")

def event_stream():
    # İlk bağlantıda bir karşılama mesajı
    yield "data: Bağlandı. Mesajlar burada akacak.\n\n"
    while True:
        msg = msg_queue.get()  # yeni mesaj gelene kadar bloklar
        yield f"data: {msg}\n\n"

INDEX_HTML = """
<!doctype html>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Railway Mesaj Akışı</title>
<style>
  body { font-family: -apple-system, system-ui, sans-serif; margin:0; background:#0b0b0b; color:#eee; }
  header { position:sticky; top:0; background:#111; padding:12px 16px; border-bottom:1px solid #222; }
  .badge { display:inline-block; padding:4px 8px; border-radius:6px; background:#222; font-size:12px; }
  #log { padding:12px 16px; }
  .line { padding:10px 12px; margin:8px 0; background:#141414; border:1px solid #222; border-radius:8px; word-break:break-word; }
  .controls { padding:12px 16px; display:flex; gap:8px; border-top:1px solid #222; background:#0f0f0f; position:sticky; bottom:0; }
  input, button { font-size:16px; padding:10px 12px; border-radius:8px; border:1px solid #333; background:#1a1a1a; color:#eee; }
  button { cursor:pointer; }
</style>
<header>
  <div class="badge">Railway • Ekran Mesaj Akışı</div>
</header>
<div id="log"></div>
<div class="controls">
  <input id="msg" placeholder="Test mesajı yaz..." style="flex:1" />
  <button onclick="send()">Gönder</button>
</div>
<script>
  const log = document.getElementById('log');
  const es = new EventSource('/events');
  es.onmessage = (e) => {
    const div = document.createElement('div');
    div.className = 'line';
    div.textContent = e.data;
    log.prepend(div);
  };
  async function send() {
    const v = document.getElementById('msg').value;
    if (!v) return;
    document.getElementById('msg').value = '';
    try { await fetch('/push?msg=' + encodeURIComponent(v)); } catch (e) {}
  }
</script>
"""

@app.route("/")
def index():
    return render_template_string(INDEX_HTML)

@app.route("/events")
def sse():
    return Response(event_stream(), mimetype="text/event-stream")

@app.route("/push")
def push():
    text = request.args.get("msg", "").strip()
    if text:
        notify(text)
        return "OK", 200
    return "Empty", 400

# Arka planda sürekli çalışan iş parçacığı (örnek heartbeat)
def worker():
    notify("Arka plan işçisi başladı 🚀")
    count = 0
    while True:
        count += 1
        notify(f"Heartbeat #{count} — sistem çalışıyor")
        time.sleep(30)

# Gunicorn ile çalıştırılacağı için __main__ bloğunda sadece thread’i başlatıyoruz
t = threading.Thread(target=worker, daemon=True)
t.start()
