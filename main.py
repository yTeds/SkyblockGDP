from flask import Flask, render_template_string
import requests, threading, time, json, base64, os

app = Flask(__name__)

# GitHub settings (set these as environment variables in Render)
GITHUB_REPO = os.getenv("GITHUB_REPO", "username/reponame")
GITHUB_FILE = "stats.json"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
STATS_URL = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"

# In-memory stats
stats = {
    "count": 0,
    "current": 0,
    "total": 0,
    "history": [],
    "buyers": {}
}

SKYBLOCK_API = "https://api.hypixel.net/v2/skyblock/auctions_ended"

# === GitHub Helpers ===
def load_stats():
    """Pull latest stats.json from GitHub"""
    global stats
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    r = requests.get(STATS_URL, headers=headers)
    if r.status_code == 200:
        content = base64.b64decode(r.json()["content"]).decode()
        stats.update(json.loads(content))
        print("Loaded stats from GitHub")
    else:
        print("No stats.json found, starting fresh")

def save_stats():
    """Push stats.json to GitHub"""
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    content = base64.b64encode(json.dumps(stats, indent=2).encode()).decode()
    
    # Need file SHA to update
    r = requests.get(STATS_URL, headers=headers).json()
    sha = r.get("sha", None)

    data = {
        "message": "Update stats.json",
        "content": content,
        "sha": sha
    }
    requests.put(STATS_URL, headers=headers, json=data)
    print("Saved stats to GitHub")

# === Background Stats Fetch ===
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

                # Track history in chunks of 30
                if len(stats["history"]) == 0 or len(stats["history"][-1]) >= 30:
                    stats["history"].append([])
                stats["history"][-1].append(total_price)

                # Track buyers
                for auction in auctions:
                    buyer = auction.get("buyer", "Unknown")
                    price = auction["price"]
                    stats["buyers"][buyer] = stats["buyers"].get(buyer, 0) + price

                save_stats()  # Save to GitHub

            time.sleep(60)
        except Exception as e:
            print("Error fetching stats:", e)
            time.sleep(60)

# === Web Routes ===
@app.route("/")
def index():
    # Calculate average per minute
    avg = stats["total"] / stats["count"] if stats["count"] > 0 else 0
    # Sort buyers by total spent
    sorted_buyers = sorted(stats["buyers"].items(), key=lambda x: x[1], reverse=True)

    return render_template_string("""
    <html>
    <head>
        <title>Skyblock GDP Stats</title>
        <meta http-equiv="refresh" content="60">
        <style>
            body {
                background: linear-gradient(to right, #1f1c2c, #928dab);
                color: white;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                padding: 20px;
            }
            h1, h2 {
                text-align: center;
            }
            .stats, .history, .leaderboard {
                display: flex;
                flex-wrap: wrap;
                justify-content: center;
                gap: 15px;
                margin-top: 20px;
            }
            .card {
                background: rgba(255,255,255,0.15);
                padding: 15px;
                border-radius: 10px;
                min-width: 150px;
                text-align: center;
                box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            }
            .history-card {
                min-width: 250px;
            }
        </style>
    </head>
    <body>
        <h1>Skyblock GDP Stats</h1>
        <div class="stats">
            <div class="card">Count: {{ stats.count }}</div>
            <div class="card">Current: {{ "{:,}".format(stats.current) }}</div>
            <div class="card">Total: {{ "{:,}".format(stats.total) }}</div>
            <div class="card">Average per min: {{ "{:,}".format(avg|int) }}</div>
        </div>

        <h2>History</h2>
        <div class="history">
            {% for batch in stats.history %}
                <div class="card history-card">
                    <strong>Batch {{ loop.index }}:</strong><br>
                    {% for price in batch %}
                        {{ "{:,}".format(price) }}<br>
                    {% endfor %}
                </div>
            {% endfor %}
        </div>

        <h2>Top Buyers</h2>
        <div class="leaderboard">
            {% for buyer, spent in sorted_buyers %}
                <div class="card">
                    <strong>{{ buyer }}</strong><br>
                    {{ "{:,}".format(spent) }}
                </div>
            {% endfor %}
        </div>
    </body>
    </html>
    """, stats=stats, avg=avg, sorted_buyers=sorted_buyers)

if __name__ == "__main__":
    load_stats()
    threading.Thread(target=fetch_stats, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)
