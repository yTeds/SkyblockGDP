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
    "history": []
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

            if total_price != stats["current"]:
                stats["count"] += 1
                stats["current"] = total_price
                stats["total"] += total_price

                # Track history in chunks of 30
                if len(stats["history"]) == 0 or len(stats["history"][-1]) >= 30:
                    stats["history"].append([])
                stats["history"][-1].append(total_price)

                save_stats()  # Save to GitHub

            time.sleep(60)
        except Exception as e:
            print("Error fetching stats:", e)
            time.sleep(60)

# === Web Routes ===
@app.route("/")
def index():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Skyblock GDP Stats</title>
        <meta http-equiv="refresh" content="60">
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(to right, #1e3c72, #2a5298);
                color: #f0f0f0;
                margin: 0;
                padding: 0;
            }
            .container {
                max-width: 900px;
                margin: 0 auto;
                padding: 20px;
            }
            h1, h2 {
                text-align: center;
            }
            .stats {
                display: flex;
                justify-content: space-around;
                margin-bottom: 30px;
            }
            .card {
                background: rgba(255, 255, 255, 0.1);
                padding: 20px;
                border-radius: 10px;
                text-align: center;
                flex: 1;
                margin: 0 10px;
                box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            }
            .card h3 {
                margin: 10px 0;
                font-size: 1.2rem;
                color: #ffd700;
            }
            .history {
                display: flex;
                flex-direction: column;
                gap: 10px;
            }
            .batch {
                background: rgba(255, 255, 255, 0.1);
                padding: 10px;
                border-radius: 8px;
                display: flex;
                flex-wrap: wrap;
                gap: 5px;
            }
            .batch span {
                background: rgba(0,255,204,0.2);
                padding: 3px 6px;
                border-radius: 4px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Skyblock GDP Stats</h1>
            <div class="stats">
                <div class="card">
                    <h3>Count</h3>
                    <p>{{ stats.count }}</p>
                </div>
                <div class="card">
                    <h3>Current</h3>
                    <p>{{ "{:,}".format(stats.current) }}</p>
                </div>
                <div class="card">
                    <h3>Total</h3>
                    <p>{{ "{:,}".format(stats.total) }}</p>
                </div>
                <div class="card">
                    <h3>Average / min</h3>
                    <p>{{ "{:,}".format(stats.total // stats.count if stats.count else 0) }}</p>
                </div>
            </div>

            <h2>History</h2>
            <div class="history">
                {% for group in stats.history %}
                    <div class="batch">
                        {% for price in group %}
                            <span>{{ "{:,}".format(price) }}</span>
                        {% endfor %}
                    </div>
                {% endfor %}
            </div>
        </div>
    </body>
    </html>
    """, stats=stats)



if __name__ == "__main__":
    load_stats()
    threading.Thread(target=fetch_stats, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)
