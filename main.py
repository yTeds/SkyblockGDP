from flask import Flask, render_template_string, request, redirect, url_for
import requests, threading, time, json, base64, os, asyncio, aiohttp

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
    "buyers": {}  # UUID: total_spent
}

# Cache for UUID -> username
uuid_cache = {}

# Queue for UUIDs that need conversion
uuid_queue = set()

SKYBLOCK_API = "https://api.hypixel.net/v2/skyblock/auctions_ended"

# === GitHub Helpers ===
def load_stats():
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
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    content = base64.b64encode(json.dumps(stats, indent=2).encode()).decode()
    r = requests.get(STATS_URL, headers=headers).json()
    sha = r.get("sha", None)
    data = {"message": "Update stats.json", "content": content, "sha": sha}
    requests.put(STATS_URL, headers=headers, json=data)
    print("Saved stats to GitHub")

# === UUID -> Username Helper ===
def uuid_to_name_sync(uuid):
    """Try to convert UUID to name (blocking)."""
    if uuid in uuid_cache:
        return uuid_cache[uuid]
    try:
        r = requests.get(f"https://api.mojang.com/user/profile/{uuid}", timeout=5)
        if r.status_code == 200:
            name = r.json().get("name", uuid[:8])
            uuid_cache[uuid] = name
            return name
    except Exception as e:
        print(f"Error converting UUID {uuid}: {e}")
    return uuid[:8]

# Background async UUID converter
async def process_uuid_queue():
    while True:
        if uuid_queue:
            uuids = list(uuid_queue)
            for uuid in uuids:
                name = uuid_to_name_sync(uuid)
                uuid_queue.discard(uuid)
        await asyncio.sleep(1)  # avoid tight loop

# === Background Stats Fetch ===
def fetch_stats():
    while True:
        try:
            r = requests.get(SKYBLOCK_API, timeout=10).json()
            auctions = r.get("auctions", [])
            total_price = sum(a["price"] for a in auctions)

            if total_price != stats["current"]:
                stats["count"] += 1
                stats["current"] = total_price
                stats["total"] += total_price

                # Track history in chunks of 30
                if len(stats["history"]) == 0 or len(stats["history"][-1]) >= 30:
                    stats["history"].append([])
                stats["history"][-1].append(total_price)

                # Track buyers and add UUIDs to queue
                for auction in auctions:
                    buyer_uuid = auction.get("buyer")
                    price = auction["price"]
                    if buyer_uuid:
                        stats["buyers"][buyer_uuid] = stats["buyers"].get(buyer_uuid, 0) + price
                        uuid_queue.add(buyer_uuid)

                save_stats()

            time.sleep(60)
        except Exception as e:
            print("Error fetching stats:", e)
            time.sleep(60)

# === Web Routes ===
@app.route("/", methods=["GET"])
def index():
    avg = stats["total"] / stats["count"] if stats["count"] > 0 else 0

    # Convert buyers to usernames safely
    buyer_list = [(uuid_to_name_sync(uuid), stats["buyers"][uuid]) for uuid in stats["buyers"]]
    buyer_list.sort(key=lambda x: x[1], reverse=True)
    top_buyers = [(name, spent, idx+1) for idx, (name, spent) in enumerate(buyer_list[:10])]

    # Search feature
    search_name = request.args.get("search", "").strip()
    search_result = None
    if search_name:
        for idx, (name, spent) in enumerate(buyer_list):
            if name.lower() == search_name.lower():
                search_result = (name, spent, idx+1)
                break

    return render_template_string("""
    <html>
    <head>
        <title>Skyblock GDP Stats</title>
        <meta http-equiv="refresh" content="60">
        <style>
            body { background: linear-gradient(to right, #1f1c2c, #928dab); color: white; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 20px;}
            h1, h2 { text-align:center; }
            .stats, .history, .leaderboard { display:flex; flex-wrap:wrap; justify-content:center; gap:15px; margin-top:20px;}
            .card { background: rgba(255,255,255,0.15); padding:15px; border-radius:10px; min-width:150px; text-align:center; box-shadow:0 4px 8px rgba(0,0,0,0.2);}
            .history-card { min-width:250px; }
            form { text-align:center; margin-top:20px; }
            input[type=text], input[type=submit], button { padding:5px; border-radius:5px; border:none; cursor:pointer; }
            input[type=submit], button { background:#fff; color:#333; }
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

        <h2>Top 10 Buyers</h2>
        <div class="leaderboard">
            {% for name, spent, rank in top_buyers %}
                <div class="card">
                    <strong>{{ name }} (#{{ rank }})</strong><br>{{ "{:,}".format(spent) }}
                </div>
            {% endfor %}
        </div>

        <form method="get" action="/">
            <input type="text" name="search" placeholder="Search player name" value="{{ request.args.get('search','') }}">
            <input type="submit" value="Search">
        </form>

        {% if search_result %}
            <div class="card" style="margin:20px auto; max-width:300px;">
                <strong>{{ search_result[0] }} (#{{ search_result[2] }})</strong><br>
                Total spent: {{ "{:,}".format(search_result[1]) }}
            </div>
        {% elif search_name %}
            <div class="card" style="margin:20px auto; max-width:300px;">
                Player "{{ search_name }}" not found.
            </div>
        {% endif %}

        <form method="post" action="/reset">
            <button type="submit">Reset Stats</button>
        </form>
    </body>
    </html>
    """, stats=stats, avg=avg, top_buyers=top_buyers, search_result=search_result, request=request, search_name=search_name)

# === Reset Stats ===
@app.route("/reset", methods=["POST"])
def reset():
    global stats
    stats = {
        "count": 0,
        "current": 0,
        "total": 0,
        "history": [],
        "buyers": {}
    }
    uuid_cache.clear()
    uuid_queue.clear()
    save_stats()
    return redirect(url_for('index'))

if __name__ == "__main__":
    load_stats()
    # Start UUID processing loop
    loop = asyncio.get_event_loop()
    loop.create_task(process_uuid_queue())
    # Start stats fetching
    threading.Thread(target=fetch_stats, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)
