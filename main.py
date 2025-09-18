import requests
import csv
import time
import os

# Files
BURNER_FILE = "burner.csv"
STATS_FILE = "stats.csv"
SKYBLOCK_API = "https://api.hypixel.net/v2/skyblock/auctions_ended"

def auction_tracker(filename=BURNER_FILE, fields=("price", "timestamp")):
    """Fetch auctions from API and save to burner.csv"""
    r = requests.get(SKYBLOCK_API).json()
    auctions = r["auctions"]

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for auction in auctions:
            row = {field: auction[field] for field in fields}
            writer.writerow(row)

def stats_tracker():
    """Read prices from burner.csv and return them as a list of ints"""
    prices = []
    with open(BURNER_FILE, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            prices.append(int(row["price"]))
    return prices

def actual_stats_tracker():
    """Update stats.csv with session total, cumulative total, session count, and grand totals"""
    prices = stats_tracker()
    session_total = sum(prices)

    # Read existing data
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r", newline="", encoding="utf-8") as f:
            reader = list(csv.reader(f))
            # Skip grand total row if it exists
            if reader and reader[0][0] == "Grand Total":
                data_rows = reader[1:]  
            else:
                data_rows = reader
    else:
        data_rows = []

    # Determine last session info
    if data_rows and len(data_rows) > 1:  # header + data
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

    # Calculate grand totals
    grand_current = session_total_fmt
    grand_total = cumulative_total_fmt

    # Write everything back to stats.csv
    with open(STATS_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        # Grand total row
        writer.writerow(["Grand Total", grand_current, grand_total])
        # Header
        writer.writerow(["count", "current", "total"])
        # Data rows
        writer.writerows(data_rows)

    print(f"✅ Session {session_count}: {session_total_fmt} added (cumulative: {cumulative_total_fmt})")

# --- Continuous loop ---
while True:
    try:
        print("\n🔄 Fetching new auctions...")
        auction_tracker()
        prices = stats_tracker()
        print(f"Found {len(prices)} auctions, total price: {sum(prices):,}")
        actual_stats_tracker()
        print("⏳ Waiting 60 seconds for next update...")
        time.sleep(60)
    except Exception as e:
        print(f"⚠️ Error occurred: {e}")
        print("Retrying in 60 seconds...")
        time.sleep(60)
