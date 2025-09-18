import requests
import csv
import time
import os
from flask import Flask, render_template_string

# Files
BURNER_FILE = "burner.csv"
STATS_FILE = "stats.csv"
SKYBLOCK_API = "https://api.hypixel.net/v2/skyblock/auctions_ended"

app = Flask(__name__)

# --- Initialize stats.csv if missing ---
if not os.path.exists(STATS_FILE) or os.path.getsize(STATS_FILE) == 0:
    with open(STATS_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Grand Total", "0", "0"])
        writer.writerow(["count", "current", "total"])

def auction_tracker(filename=BURNER_FILE, fields=("price", "timestamp")):
    """Fetch auctions from API and save to burner.csv"""
    try:
        r = requests.get(SKYBLOCK_API).json()
        auctions = r.get("auctions", [])

        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for auction in auctions:
                row = {field: auction.get(field, 0) for field in fields}
                writer.writerow(row)
    except Exception as e:
        print(f"⚠️ Error fetching auctions: {e}")

def stats_tracker():
    """Read prices from burner.csv and return them as a list of ints"""
    prices = []
    if not os.path.exists(BURNER_FILE):
        return prices

    with open(BURNER_FILE, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                prices.append(int(row["price"]))
            except ValueError:
                continue
    return prices

def actual_stats_tracker():
    """Update stats.csv with session total, cumulative total, session count, and grand totals"""
    prices = stats_tracker()
    session_total = sum(prices)

    # Read existing data
    with open(STATS_FILE, "r", newline="", encoding="utf-8") as f:
        reader = list(csv.reader(f))
        if reader and reader[0][0] == "Grand Total":
            data_rows = reader[2:]  # Skip grand total + header
        else:
            data_rows = []

    # Determine last session info
    if data_rows and len(data_rows) > 0:
        last_row = data_rows[-1]
        session_count = int(last_row[0]) + 1
        cumulative_total = int(last_row[2].replace(',', '')) + session_total
        last_total = int(last_row[1].replace(',', ''))
    else:
        session_count = 1
        cumulative_total = session_total
        last_total = None

    # Skip if total hasn't changed
    if session_total == last_total:
        print("⚠️ Total price same as last session. Skipping update.")
        return

    # Format numbers with commas
    session_total_fmt = f"{session_total:,}"
    cumulative_total_fmt = f"{cumulative_total:,}"

    # Append new row
    new_row = [session_count, session_total_fmt, cumulative_total_fmt]
    data_rows.append(new_row)

    # Update grand totals
    grand_current = session_total_fmt
    grand_total = cumulative_total_fmt

    # Write everything back to stats.csv
    with open(STATS_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Grand Total", grand_current, grand_total])
        writer.writerow(["count", "current", "total"])
        writer.writerows(data_rows)

    print(f"✅ Session {session_count}: {session_total_fmt} added (cumulative: {cumulative_total_fmt})")

# --- Flask Route ---
@app.route("/")
def index():
    if not os.path.exists(STATS_FILE):
        return "No stats yet."
    
    with open(STATS_FILE, "r", newline="", encoding="utf-8") as f:
        reader = list(csv.reader(f))
        if len(reader) < 2:
            return "No stats yet."

        grand_total = reader[0]
        headers = reader[1]
        data_rows = reader[2:]

    html = f"""
    <h1>Skyblock GDP Stats</h1>
    <h2>{grand_total[0]}: Current: {grand_total[1]}, Total: {grand_total[2]}</h2>
    <table border="1" cellpadding="5">
        <tr>{" ".join(f"<th>{h}</th>" for h in headers)}</tr>
        {" ".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in data_rows)}
    </table>
    """
    return render_template_string(html)

# --- Background loop ---
def background_loop():
    while True:
        try:
            print("\n🔄 Fetching new auctions...")
            auction_tracker()
            actual_stats_tracker()
            print("⏳ Waiting 60 seconds for next update...")
            time.sleep(60)
        except Exception as e:
            print(f"⚠️ Error occurred: {e}")
            time.sleep(60)

import threading
threading.Thread(target=background_loop, daemon=True).start()

# --- Run Flask ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
