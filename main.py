from flask import Flask, render_template_string
import requests
import threading
import time
import json
import os

app = Flask(__name__)

DATA_FILE = "stats.json"

# Load saved stats if file exists
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        saved = json.load(f)
else:
    saved = {"count": 0, "current": 0, "total": 0, "history": []}

stats = saved

SKYBLOCK_API = "https://api.hypixel.net/v2/skyblock/auctions_ended"


def save_stats():
    """Save stats to file so they survive restarts"""
    with open(DATA_FILE, "w") as f:
        json.dump(stats, f)


def fetch_stats():
    while True:
        try:
            r = requests.get(SKYBLOCK_API).json()
            auctions = r.get("auctions", [])
            total_price = sum(a["price"] for a in auctions)

            # Only add if total changed
            if total_price != stats["current"]:
                stats["count"] += 1
                stats["current"] = total_price
                stats["total"] += total_price

                # Save to history (keep only last 30 for now)
                stats["history"].append({
                    "count": stats["count"],
                    "current": total_price,
                    "total": stats["total"]
                })
                if len(stats["history"]) > 30:
                    stats["history"].pop(0)

                save_stats()

            time.sleep(60)
        except Exception as e:
            print("Error fetching stats:", e)
            time.sleep(60)


# Start background thread
threading.Thread(target=fetch_stats, daemon=True).start()


# Homepage with live stats
@app.route("/")
def index():
    return render_template_string("""
        <h1>🌍 Skyblock GDP Stats</h1>
        <p><b>Count:</b> {{ stats.count }}</p>
        <p><b>Current:</b> {{ "{:,}".format(stats.current) }}</p>
        <p><b>Total:</b> {{ "{:,}".format(stats.total) }}</p>
        <p><a href="/history">📜 View History</a></p>
    """, stats=stats)


# History page
@app.route("/history")
def history():
    return render_template_string("""
        <h1>📜 History (Last {{ stats.history|length }} sessions)</h1>
        <table border="1" cellpadding="5">
            <tr><th>Count</th><th>Current</th><th>Total</th></tr>
            {% for h in stats.history %}
            <tr>
                <td>{{ h.count }}</td>
                <td>{{ "{:,}".format(h.current) }}</td>
                <td>{{ "{:,}".format(h.total) }}</td>
            </tr>
            {% endfor %}
        </table>
        <p><a href="/">⬅ Back to Stats</a></p>
    """, stats=stats)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
