# worker.py
import os
import requests
import redis
from urllib.parse import urlparse

REDIS_URL = os.environ.get("REDIS_URL")  # set in Render
SKYBLOCK_API = os.environ.get("SKYBLOCK_API", "https://api.hypixel.net/v2/skyblock/auctions_ended")

r = redis.from_url(REDIS_URL, decode_responses=True)

def run_once():
    try:
        resp = requests.get(SKYBLOCK_API, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        auctions = data.get("auctions", [])
        session_total = sum(int(a.get("price", 0)) for a in auctions)

        last_total = r.get("latest_total")
        last_total_int = int(last_total) if last_total is not None else None

        if last_total_int == session_total:
            print("No change in total; skipping")
            return

        # increment counters atomically
        r.incr("count")
        r.set("latest_total", session_total)
        # store grand_total as integer
        r.incrby("grand_total", session_total)
        # push history list (left push) and trim to 30
        r.lpush("history", session_total)
        r.ltrim("history", 0, 29)  # keep latest 30 items

        print(f"Updated: session_total={session_total:,}")
    except Exception as e:
        print("Worker error:", e)

if __name__ == "__main__":
    run_once()
