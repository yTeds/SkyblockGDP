from flask import Flask, render_template_string, request, redirect
import requests, threading, time, json, base64, os

app = Flask(__name__)

# GitHub settings
GITHUB_REPO = os.getenv("GITHUB_REPO", "yteds/SkyblockAssistance")
GITHUB_FILE = "stats.json"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
STATS_URL = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"

# In-memory stats
stats = {
    "count": 0,
    "current": 0,
    "total": 0,
    "history": [],
    "players": {}
}

SKYBLOCK_API = "https://api.hypixel.net/v2/skyblock/auctions_ended"

# --- GitHub Helpers ---
def save_stats():
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    content = base64.b64encode(json.dumps(stats, indent=2).encode()).decode()
    r = requests.get(STATS_URL, headers=headers).json()
    sha = r.get("sha", None)
    data = {"message": "Update stats.json", "content": content, "sha": sha}
    requests.put(STATS_URL, headers=headers, json=data)

def reset_stats():
    global stats
    stats = {
        "count": 0,
        "current": 0,
        "total": 0,
        "history": [],
        "players": {}
    }
    save_stats()  # Push reset to GitHub
    print("✅ Stats have been reset")

# --- Background Fetch ---
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
                if len(stats["history"]) == 0 or len(stats["history"][-1]) >= 30:
                    stats["history"].append([])
                stats["history"][-1].append(total_price)
                save_stats()
            time.sleep(60)
        except Exception as e:
            print("Error fetching stats:", e)
            time.sleep(60)

# --- Web Routes ---
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST" and request.form.get("reset") == "1":
        reset_stats()
        return redirect("/")  # Reload page after reset

    return render_template_string("""
    <html>
    <head>
        <title>Skyblock GDP Stats</title>
        <meta http-equiv="refresh" content="60"> <!-- auto refresh every 60s -->
        <style>
            body { font-family: Arial, sans-serif; background: #1e1e2f; color: #fff; padding: 20px; }
            h1, h2 { color: #ffcc00; }
            .stats { margin-bottom: 20px; }
            button { padding: 10px 20px; font-size: 16px; background: #ff4444; color: #fff; border: none; cursor: pointer; }
            button:hover { background: #ff2222; }
        </style>
    </head>
    <body>
        <h1>Skyblock GDP Stats</h1>
        <div class="stats">
            <p>Count: {{ stats.count }}</p>
            <p>Current: {{ "{:,}".format(stats.current) }}</p>
            <p>Total: {{ "{:,}".format(stats.total) }}</p>
        </div>

        <h2>History</h2>
        {% for group in stats.history %}
            <p>Batch {{ loop.index }}: {{ group | map('int') | map('format', ',') | join(', ') }}</p>
        {% endfor %}

        <form method="POST">
            <input type="hidden" name="reset" value="1">
            <button type="submit">Reset Stats</button>
        </form>
    </body>
    </html>
    """, stats=stats)

if __name__ == "__main__":
    threading.Thread(target=fetch_stats, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)
