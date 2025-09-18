import requests
import time
import threading
from flask import Flask, render_template_string

app = Flask(__name__)

# --- In-memory stats ---
stats = {
    "grand_total": 0,
    "latest_count": 0,
    "latest_current": 0,
}

SKYBLOCK_API = "https://api.hypixel.net/v2/skyblock/auctions_ended"

# --- Background auction tracker ---
def auction_tracker():
    previous_total = 0
    while True:
        try:
            r = requests.get(SKYBLOCK_API).json()
            auctions = r.get("auctions", [])

            prices = [int(a.get("price", 0)) for a in auctions]
            session_total = sum(prices)

            # Skip if no change
            if session_total != previous_total:
                stats["latest_count"] += 1
                stats["latest_current"] = session_total
                stats["grand_total"] += session_total
                previous_total = session_total
                print(f"✅ Session {stats['latest_count']}: {session_total:,} added (grand total: {stats['grand_total']:,})")
        except Exception as e:
            print(f"⚠️ Error fetching auctions: {e}")

        time.sleep(60)

# --- Flask route ---
@app.route("/")
def index():
    return render_template_string(f"""
    <html>
    <head>
        <title>Skyblock GDP Stats</title>
    </head>
    <body>
        <h2>Grand Total: {stats['grand_total']:,}</h2>
        <h3>Latest Session</h3>
        <p>Session Count: {stats['latest_count']}</p>
        <p>Session Total: {stats['latest_current']:,}</p>

        <script>
            // Auto-refresh every 15 seconds
            setTimeout(() => window.location.reload(), 15000);
        </script>
    </body>
    </html>
    """)

# --- Start background thread ---
threading.Thread(target=auction_tracker, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
