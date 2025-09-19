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
        <h1>Skyblock GDP Stats</h1>
        <p>Count: {{ stats.count }}</p>
        <p>Current: {{ "{:,}".format(stats.current) }}</p>
        <p>Total: {{ "{:,}".format(stats.total) }}</p>

        <h2>History</h2>
        {% for group in stats.history %}
          <p>Batch {{ loop.index }}: {{ group }}</p>
        {% endfor %}
    """, stats=stats)

if __name__ == "__main__":
    load_stats()
    threading.Thread(target=fetch_stats, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)
