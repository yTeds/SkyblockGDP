import requests
import csv
import time
import os
import threading
from flask import Flask, render_template_string

# Files
BURNER_FILE = "burner.csv"
STATS_FILE = "stats.csv"
SKYBLOCK_API = "https://api.hypixel.net/v2/skyblock/auctions_ended"

app = Flask(__name__)

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
                data_rows = reader[2:]  # skip grand total + header
            else:
                data_rows = reader
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
        return session_count, session_total, cumulative_total

    # Format numbers with commas
    session_total_fmt = f"{session_total:,}"
    cumulative_total_fmt = f"{cumulative_total:,}"

    # Append new row
    new_row = [session_count, session_total_fmt, cumulative_total_fmt]
    data_rows.append(new_row)

    # Write everything back to stats.csv
    with open(STATS_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        # Grand total row
        writer.writerow(["Grand Total", session_total_fmt, cumulative_total_fmt])
        # Header
        writer.writerow(["count", "current", "total"])
        # Data rows
        writer.writerows(data_rows)

    print(f"✅ Session {session_count}: {session_total_fmt} added (cumulative: {cumulative_total_fmt})")
    return session_count, session_total, cumulative_total

def stats_loop():
    """Background loop to update stats every 60 seconds"""
    while True:
        try:
            print("\n🔄 Fetching new auctions...")
            auction_tracker()
            session_count, session_total, cumulative_total = actual_stats_tracker()
            print(f"Session {session_count} complete. Waiting 60 seconds...")
            time.sleep(60)
        except Exception as e:
            print(f"⚠️ Error occurred: {e}")
            time.sleep(60)

# Start background loop in a daemon thread
threading.Thread(target=stats_loop, daemon=True).start()

# --- Flask Web Routes ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Skyblock Stats</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; }
        table { border-collapse: collapse; width: 50%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: center; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <h1>Skyblock Stats</h1>
    {% if stats %}
    <table>
        <tr><th>Count</th><th>Current</th><th>Total</th></tr>
        {% for row in stats %}
        <tr>
            <td>{{ row[0] }}</td>
            <td>{{ row[1] }}</td>
            <td>{{ row[2] }}</td>
        </tr>
        {% endfor %}
    </table>
    {% else %}
    <p>No stats yet.</p>
    {% endif %}
</body>
</html>
"""

@app.route("/")
def index():
    stats = []
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r", newline="", encoding="utf-8") as f:
            reader = list(csv.reader(f))
            stats = reader[2:]  # skip grand total + header
    return render_template_string(HTML_TEMPLATE, stats=stats)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
