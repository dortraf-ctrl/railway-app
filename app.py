import os
import time
import threading
import queue
from flask import Flask, Response, request, render_template_string

app = Flask(__name__)
msg_queue = queue.Queue()

def notify(text):
    ts = time.strftime("%H:%M:%S")
    msg_queue.put(f"[{ts}] {text}")

def event_stream():
    yield f"data: { 'Bağlandı. Mesajlar burada akacak.' }\n\n"
    while True:
        msg = msg_queue.get()
        yield f"data: {msg}\n\n"

INDEX_HTML = """
<!doctype html>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ekran Mesajları</title>
<style>
  body { font-family: sans-serif; background:#0b0b0b; color:#eee; margin:0; }
  header { padding:12px; background:#111; border-bottom:1px solid #222; }
  #log { padding:12px; }
  .line { padding:8px; margin:6px 0; background:#141414; border-radius:6px; }
</style>
<header>📡 Railway Mesaj Akışı</header>
<div id="log"></div>
<script>
  const log = document.getElementById('log');
  const es = new EventSource('/events');
  es.onmessage = (e) => {
    const div = document.createElement('div');
    div.className = 'line';
    div.textContent = e.data;
    log.prepend(div);
  };
</script>
"""

@app.route("/")
def index():
    return render_template_string(INDEX_HTML)

@app.route("/events")
def sse():
    return Response(event_stream(), mimetype="text/event-stream")

def worker():
    notify("Arka plan işçisi başladı 🚀")
    count = 0
    while True:
        count += 1
        notify(f"Heartbeat #{count} — sistem çalışıyor")
        time.sleep(30)

if __name__ == "__main__":
    t = threading.Thread(target=worker, daemon=True)
    t.start()
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port, threaded=True)
