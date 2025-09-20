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
    "buyers": {}  # UUID: {name: str, spent: int}
}

# Cache for UUID -> username
uuid_cache = {}

# Queue of UUIDs to convert with retry counts
uuid_queue = {}  # uuid: retry_count
MAX_RETRIES = 5

SKYBLOCK_API = "https://api.hypixel.net/v2/skyblock/auctions_ended"

# === GitHub Helpers ===
def load_stats():
    global stats
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    r = requests.get(STATS_URL, headers=headers)
    if r.status_code == 200:
        content = base64.b64decode(r.json()["content"]).decode()
        loaded = json.loads(content)

        # Migrate old buyers format (uuid -> int) into new format
        if "buyers" in loaded:
            migrated_buyers = {}
            for uuid, data in loaded["buyers"].items():
                if isinstance(data, int):  # old format
                    migrated_buyers[uuid] = {"name": uuid[:8], "spent": data}
                elif isinstance(data, dict):  # already new format
                    migrated_buyers[uuid] = data
            loaded["buyers"] = migrated_buyers

        stats.update(loaded)
        print("Loaded stats from GitHub (with migration check)")
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
async def fetch_uuid(session, uuid):
    try:
        async with session.get(f"https://api.mojang.com/user/profile/{uuid}", timeout=10) as r:
            if r.status == 200:
                data = await r.json()
                name = data.get("name", uuid[:8])
                uuid_cache[uuid] = name
                # also update stats buyers if exists
                if uuid in stats["buyers"]:
                    stats["buyers"][uuid]["name"] = name
                return True
    except Exception as e:
        print(f"Error converting UUID {uuid}: {e}")
    return False

async def process_uuid_queue():
    global uuid_queue
    async with aiohttp.ClientSession() as session:
        tasks = []
        for uuid in list(uuid_queue.keys()):
            tasks.append(convert_uuid(session, uuid))
        await asyncio.gather(*tasks)

async def convert_uuid(session, uuid):
    success = await fetch_uuid(session, uuid)
    if success:
        uuid_queue.pop(uuid, None)
    else:
        uuid_queue[uuid] += 1
        if uuid_queue[uuid] > MAX_RETRIES:
            print(f"Failed to convert UUID {uuid} after {MAX_RETRIES} retries")
            uuid_queue.pop(uuid, None)

def uuid_to_name(uuid):
    if uuid in uuid_cache:
        return uuid_cache[uuid]
    if uuid in stats["buyers"] and "name" in stats["buyers"][uuid]:
        return stats["buyers"][uuid]["name"]
    if uuid not in uuid_queue:
        uuid_queue[uuid] = 0
    return uuid[:8]  # fallback

# === Background Stats Fetch ===
def fetch_stats():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
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

                # Track buyers
                for auction in auctions:
                    buyer_uuid = auction.get("buyer")
                    price = auction["price"]
                    if buyer_uuid:
                        buyer_data = stats["buyers"].get(
                            buyer_uuid, {"name": uuid_to_name(buyer_uuid), "spent": 0}
                        )
                        buyer_data["spent"] += price
                        buyer_data["name"] = uuid_to_name(buyer_uuid)
                        stats["buyers"][buyer_uuid] = buyer_data

                        if buyer_uuid not in uuid_cache and buyer_uuid not in uuid_queue:
                            uuid_queue[buyer_uuid] = 0

                save_stats()

            # Process UUID queue asynchronously
            loop.run_until_complete(process_uuid_queue())

            time.sleep(60)
        except Exception as e:
            print("Error fetching stats:", e)
            time.sleep(60)

# === Web Routes ===
@app.route("/", methods=["GET"])
def index():
    avg = stats["total"] / stats["count"] if stats["count"] > 0 else 0

    # Build buyer list with UUID, name, spent
    buyer_list = [(uuid, data["name"], data["spent"]) for uuid, data in stats["buyers"].items()]
    buyer_list.sort(key=lambda x: x[2], reverse=True)

    # Top 10 with ranks
    top_buyers = [(i+1, name, spent) for i, (_, name, spent) in enumerate(buyer_list[:10])]

    # Search feature
    search_name = request.args.get("search", "").strip()
    search_result = None
    if search_name:
        for i, (_, name, spent) in enumerate(buyer_list):
            if name.lower() == search_name.lower():
                search_result = (name, spent, i+1)  # include rank
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
            {% for rank, name, spent in top_buyers %}
                <div class="card">
                    <strong>{{ rank }}. {{ name }}</strong><br>{{ "{:,}".format(spent) }}
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
        </form>
    </body>
    </html>
    """, stats=stats, avg=avg, top_buyers=top_buyers, search_result=search_result, request=request, search_name=search_name)


if __name__ == "__main__":
    load_stats()
    threading.Thread(target=fetch_stats, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)
