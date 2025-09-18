from flask import Flask, render_template_string, jsonify
import requests
import threading
import time
import json
import os

app = Flask(__name__)

STATS_FILE = "stats.json"
SKYBLOCK_API = "https://api.hypixel.net/v2/skyblock/auctions_ended"

# --- Load stats from JSON if it exists ---
if os.path.exists(STATS_FILE):
    with open(STATS_FILE, "r") as f:
        stats = json.load(f)
else:
    stats = {
        "count": 0,
        "current": 0,
        "total": 0,
        "history": []  # store each session total
    }

# --- Background updater ---
def fetch_stats():
    while True:
        try:
            r = requests.get(SKYBLOCK_API).json()
            auctions = r["auctions"]
            total_price = sum(a["price"] for a in auctions)

            # Only update if price changed
            if total_price != stats["current"]:
                stats["count"] += 1
                stats["current"] = total_price
                stats["total"] += total_price

                # Add to history
                stats["history"].append(total_price)
                # Keep only last 30 in a page
                if len(stats["history"]) > 30:
                    stats["history"] = stats["history"][-30:]

                # Save to JSON for persistence
                with open(STATS_FILE, "w") as f:
                    json.dump(stats, f)

            time.sleep(60)  # 60 seconds
        except Exception as e:
            print("Error fetching stats:", e)
            time.sleep(60)

threading.Thread(target=fetch_stats, daemon=True).start()

# --- Routes ---
@app.route("/")
def index():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Skyblock GDP Stats</title>
        <style>
            body { font-family: 'Segoe UI', sans-serif; background: #1e1e2f; color: #fff; text-align: center; }
            h1 { margin-top: 30px; color: #00d4ff; }
            .card { background: #2e2e3e; padding: 20px; border-radius: 10px; margin: 20px auto; width: 250px; box-shadow: 0 4px 10px rgba(0,0,0,0.3); }
            a { color: #00d4ff; text-decoration: none; }
        </style>
    </head>
    <body>
        <h1>Skyblock GDP Stats</h1>
        <div class="card">
            <h2>Session Count</h2>
            <p id="count">{{ stats.count }}</p>
        </div>
        <div class="card">
            <h2>Current Price</h2>
            <p id="current">{{ "{:,}".format(stats.current) }}</p>
        </div>
        <div class="card">
            <h2>Total Accumulated</h2>
            <p id="total">{{ "{:,}".format(stats.total) }}</p>
        </div>
        <a href="/history">View History</a>

        <script>
            async function updateStats() {
                const res = await fetch("/api/stats");
                const data = await res.json();
                document.getElementById("count").innerText = data.count;
                document.getElementById("current").innerText = data.current.toLocaleString();
                document.getElementById("total").innerText = data.total.toLocaleString();
            }
            setInterval(updateStats, 60000); // refresh every 60 seconds
        </script>
    </body>
    </html>
    """, stats=stats)

@app.route("/history")
def history():
    pages = [stats["history"][i:i+30] for i in range(0, len(stats["history"]), 30)]
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Skyblock GDP History</title>
        <style>
            body { font-family: 'Segoe UI', sans-serif; background: #1e1e2f; color: #fff; text-align: center; }
            table { margin: 20px auto; border-collapse: collapse; width: 80%; }
            th, td { padding: 10px; border: 1px solid #444; }
            th { background: #00d4ff; color: #000; }
            td { background: #2e2e3e; }
            h1 { color: #00d4ff; }
        </style>
    </head>
    <body>
        <h1>History (last 30 sessions per page)</h1>
        {% for page_num, page in enumerate(pages) %}
            <h2>Page {{ page_num + 1 }}</h2>
            <table>
                <tr><th>Session #</th><th>Price</th></tr>
                {% for idx, price in enumerate(page) %}
                    <tr><td>{{ idx + 1 + page_num*30 }}</td><td>{{ "{:,}".format(price) }}</td></tr>
                {% endfor %}
            </table>
        {% endfor %}
        <a href="/">Back to Stats</a>
    </body>
    </html>
    """, pages=pages)

@app.route("/api/stats")
def api_stats():
    return jsonify(stats)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
