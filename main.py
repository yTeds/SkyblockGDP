# main.py
import os
import redis
from flask import Flask, render_template_string, jsonify

REDIS_URL = os.environ.get("REDIS_URL")
r = redis.from_url(REDIS_URL, decode_responses=True)

app = Flask(__name__)

TEMPLATE = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Skyblock GDP</title>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <style>
    :root{--bg:#0f1724;--card:#0b1220;--accent:#38bdf8;--muted:#94a3b8}
    body{font-family:Inter,system-ui,Segoe UI,Roboto,Arial;background:linear-gradient(180deg,#071027 0%, #0b1220 100%);color:#e6eef8;margin:0}
    .wrap{max-width:900px;margin:28px auto;padding:20px}
    header{display:flex;align-items:center;justify-content:space-between}
    h1{color:var(--accent);margin:0}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin-top:18px}
    .card{background:var(--card);border-radius:12px;padding:16px;box-shadow:0 6px 18px rgba(2,6,23,.6)}
    .big{font-size:1.8rem;margin:8px 0}
    .muted{color:var(--muted);font-size:.9rem}
    table{width:100%;border-collapse:collapse;margin-top:12px}
    th,td{padding:8px;border-bottom:1px solid rgba(255,255,255,0.04);text-align:center}
    th{color:#000;background:var(--accent);border-radius:6px}
    .nav{margin-top:10px}
    a{color:var(--accent);text-decoration:none}
    footer{margin-top:18px;color:var(--muted);font-size:.85rem;text-align:center}
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1>Skyblock GDP</h1>
      <div class="muted">Auto-updates every 60s</div>
    </header>

    <div class="grid">
      <div class="card">
        <div class="muted">Session Count</div>
        <div class="big">{{count}}</div>
      </div>
      <div class="card">
        <div class="muted">Latest Session (current)</div>
        <div class="big">{{latest_current}}</div>
      </div>
      <div class="card">
        <div class="muted">Grand Total</div>
        <div class="big">{{grand_total}}</div>
      </div>
    </div>

    <div class="card" style="margin-top:16px">
      <div class="muted">History (latest 30 sessions)</div>
      <table>
        <tr><th>#</th><th>Price</th></tr>
        {% for i, p in enumerate(history) %}
          <tr><td>{{ i+1 }}</td><td>{{ "{:,}".format(p) }}</td></tr>
        {% endfor %}
      </table>
    </div>

    <footer>Note: the fetcher runs separately and writes stats to Redis.</footer>
  </div>

  <script>
    // refresh every 60s
    setTimeout(()=>window.location.reload(), 60000);
  </script>
</body>
</html>
"""

@app.route("/")
def index():
    count = int(r.get("count") or 0)
    latest_current = int(r.get("latest_total") or 0)
    grand = int(r.get("grand_total") or 0)
    raw_history = r.lrange("history", 0, -1) or []
    history = [int(x) for x in raw_history]
    return render_template_string(TEMPLATE, count=count, latest_current=f"{latest_current:,}", grand_total=f"{grand:,}", history=history)

@app.route("/api/stats")
def api_stats():
    return jsonify({
        "count": int(r.get("count") or 0),
        "latest_current": int(r.get("latest_total") or 0),
        "grand_total": int(r.get("grand_total") or 0),
        "history": [int(x) for x in (r.lrange("history", 0, -1) or [])]
    })

if __name__ == "__main__":
    # use gunicorn in production; for local testing:
    app.run(host="0.0.0.0", port=10000)
