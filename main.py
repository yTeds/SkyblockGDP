from flask import Flask, render_template_string
import requests
import threading
import time

app = Flask(__name__)

# In-memory stats
stats = {
    "count": 0,
    "current": 0,
    "total": 0
}

SKYBLOCK_API = "https://api.hypixel.net/v2/skyblock/auctions_ended"

def fetch_stats():
    while True:
        try:
            r = requests.get(SKYBLOCK_API).json()
            auctions = r["auctions"]
            total_price = sum(a["price"] for a in auctions)

            # Only add if total changed
            if total_price != stats["current"]:
                stats["count"] += 1
                stats["current"] = total_price
                stats["total"] += total_price

            time.sleep(60)
        except Exception as e:
            print("Error fetching stats:", e)
            time.sleep(60)

# Start background thread
threading.Thread(target=fetch_stats, daemon=True).start()

# Simple webpage showing stats
@app.route("/")
def index():
    return render_template_string("""
        <h1>Skyblock GDP Stats</h1>
        <p>Count: {{ stats.count }}</p>
        <p>Current: {{ "{:,}".format(stats.current) }}</p>
        <p>Total: {{ "{:,}".format(stats.total) }}</p>
    """, stats=stats)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
