from flask import Flask, render_template_string
import requests
import threading
import time
import json
import os
import math

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

                # Save all history (don’t overwrite, just append)
                stats["history"].append({
                    "count": stats["count"],
                    "current": total_price,
                    "total": stats["total"]
                })

                save_stats()

            time.sleep(60)
        except Exception as e:
            print("Error fetching stats:", e)
            time.sleep(60)


# Start background thread
threading.Thread(target=fetch_stats, daemon=True).start()


@app.route("/")
def index():
    # Break history into groups of 30
    groups = []
    history = stats.get("history", [])
    if history:
        num_groups = math.ceil(len(history) / 30)
        for i in range(num_groups):
            start = i * 30
            end = start + 30
            groups.append(history[start:end])

    return render_template_string("""
        <html>
        <head>
            <title>Skyblock GDP</title>
            <style>
                body {
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background: linear-gradient(135deg, #f0f4ff, #d9e4ff);
                    color: #333;
                    margin: 0;
                    padding: 20px;
                }
                h1 {
                    text-align: center;
                    color: #2c3e50;
                }
                .stats {
                    text-align: center;
                    margin: 20px 0;
                }
                .stat-box {
                    display: inline-block;
                    background: #fff;
                    padding: 15px 25px;
                    margin: 10px;
                    border-radius: 12px;
                    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                    font-size: 18px;
                }
                h2 {
                    margin-top: 40px;
                    text-align: center;
                    color: #34495e;
                }
                table {
                    border-collapse: collapse;
                    width: 90%;
                    margin: 20px auto;
                    background: #fff;
                    border-radius: 10px;
                    overflow: hidden;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                }
                th, td {
                    padding: 12px 15px;
                    text-align: center;
                }
                th {
                    background-color: #4a69bd;
                    color: #fff;
                }
                tr:nth-child(even) {
                    background-color: #f8f9fa;
                }
                tr:hover {
                    background-color: #e9f0ff;
                }
                h3 {
                    text-align: center;
                    color: #2c3e50;
                    margin-top: 30px;
                }
            </style>
        </head>
        <body>
            <h1>🌍 Skyblock GDP Stats</h1>
            <div class="stats">
                <div class="stat-box"><b>Count:</b> {{ stats.count }}</div>
                <div class="stat-box"><b>Current:</b> {{ "{:,}".format(stats.current) }}</div>
                <div class="stat-box"><b>Total:</b> {{ "{:,}".format(stats.total) }}</div>
            </div>

            <h2>📜 History</h2>
            {% if groups %}
                {% for g in groups %}
                    <h3>Batch {{ loop.index }}</h3>
                    <table>
                        <tr><th>Count</th><th>Current</th><th>Total</th></tr>
                        {% for h in g %}
                        <tr>
                            <td>{{ h.count }}</td>
                            <td>{{ "{:,}".format(h.current) }}</td>
                            <td>{{ "{:,}".format(h.total) }}</td>
                        </tr>
                        {% endfor %}
                    </table>
                {% endfor %}
            {% else %}
                <p style="text-align:center;">No history yet.</p>
            {% endif %}
        </body>
        </html>
    """, stats=stats, groups=groups)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
