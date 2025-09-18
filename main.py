from flask import Flask, render_template_string
import csv
import threading
import time
import requests
import os

app = Flask(__name__)

BURNER_FILE = "burner.csv"
STATS_FILE = "stats.csv"
SKYBLOCK_API = "https://api.hypixel.net/v2/skyblock/auctions_ended"

# --- Your auction/stat functions (keep as you have them) ---
def auction_tracker(filename=BURNER_FILE, fields=("price", "timestamp")):
    r = requests.get(SKYBLOCK_API).json()
    auctions = r["auctions"]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for auction in auctions:
            row = {field: auction[field] for field in fields}
            writer.writerow(row)

def stats_tracker():
    prices = []
    if os.path.exists(BURNER_FILE):
        with open(BURNER_FILE, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                prices.append(int(row["price"]))
    return prices

def actual_stats_tracker():
    prices = stats_tracker()
    session_total = sum(prices)

    # Read existing data
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r", newline="", encoding="utf-8") as f:
            reader = list(csv.reader(f))
            if reader and reader[0][0] == "Grand Total":
                data_rows = reader[2:]  # skip grand total and header
            else:
                data_rows = reader
    else:
        data_rows = []

    if data_rows:
        last_row = data_rows[-1]
        session_count = int(last_row[0]) + 1
        cumulative_total = int(last_row[2].replace(',', '')) + session_total
        last_total = int(last_row[1].replace(',', ''))
    else:
        session_count = 1
        cumulative_total = session_total
        last_total = None

    if session_total == last_total:
        return

    session_total_fmt = f"{session_total:,}"
    cumulative_total_fmt = f"{cumulative_total:,}"
    new_row = [session_count, session_total_fmt, cumulative_total_fmt]
    data_rows.append(new_row)

    with open(STATS_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Grand Total", session_total_fmt, cumulative_total_fmt])
        writer.writerow(["count", "current", "total"])
        writer.writerows(data_rows)

# --- Background loop ---
def stats_loop():
    while True:
        try:
            auction_tracker()
            actual_stats_tracker()
        except Exception as e:
            print(f"Error in loop: {e}")
        time.sleep(60)

threading.Thread(target=stats_loop, daemon=True).start()

# --- Flask routes ---
@app.route("/")
def index():
    grand_total = session_total = session_count = 0
    data_rows = []

    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r", newline="", encoding="utf-8") as f:
            reader = list(csv.reader(f))
            if reader:
                if reader[0][0] == "Grand Total":
                    grand_total = reader[0][2]
                    session_total = reader[0][1]
                if len(reader) > 2:
                    data_rows = reader[2:]  # skip grand total + header

    html = """
    <html>
    <head>
        <title>SkyblockGDP Stats</title>
        <meta http-equiv="refresh" content="30">
        <style>
            body { font-family: Arial; text-align:center; }
            table { margin:auto; border-collapse: collapse; }
            td, th { border: 1px solid #999; padding: 6px 12px; }
        </style>
    </head>
    <body>
        <h1>SkyblockGDP Stats</h1>
        <h2>Grand Total: {{grand_total}}</h2>
        <h3>Last Session Total: {{session_total}}</h3>
        <table>
            <tr><th>Count</th><th>Current</th><th>Cumulative</th></tr>
            {% for row in data_rows %}
            <tr>
                <td>{{row[0]}}</td>
                <td>{{row[1]}}</td>
                <td>{{row[2]}}</td>
            </tr>
            {% endfor %}
        </table>
        <p>Page auto-refreshes every 30 seconds.</p>
    </body>
    </html>
    """
    return render_template_string(html, grand_total=grand_total, session_total=session_total, data_rows=data_rows)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
