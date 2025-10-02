import os
import csv
import time
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

BASE_URL_FIRST = "https://classic.dura-online.com/?highscores/experience"
BASE_URL_PAGED = "https://classic.dura-online.com/?highscores/experience/{}"
SAVE_DIR = "snapshots"

def fetch_page(page):
    if page == 1:
        url = BASE_URL_FIRST
    else:
        url = BASE_URL_PAGED.format(page - 1)
    r = requests.get(url)
    r.raise_for_status()
    return r.text

def parse_highscores(html):
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for tr in soup.find_all("tr"):
        cols = tr.find_all("td")
        if len(cols) == 4:  # Rank, Name, Level, Points
            # Extract only the character name, omitting <small> tag
            name_td = cols[1]
            # Find the <a> or <span> containing the name
            name_tag = name_td.find(["a", "span"])
            if name_tag:
                name = name_tag.get_text(strip=True)
            else:
                # Fallback: get text before <br> if no <a> or <span>
                name = name_td.get_text(strip=True).split("\n")[0]
            exp = cols[3].get_text(strip=True).replace(",", "")
            if exp.isdigit():
                rows.append([name, int(exp)])
    return rows


def build_snapshot(pages=200, delay=0.25):
    all_rows = []
    for i in range(1, pages + 1):
        print(f"Fetching page {i}/{pages}")
        html = fetch_page(i)
        rows = parse_highscores(html)
        all_rows.extend(rows)
        time.sleep(delay)
    return all_rows

def save_csv(data, date=None):
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    filename = os.path.join(SAVE_DIR, f"highscores_{date}.csv")
    with open(filename, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "Experience"])
        writer.writerows(data)
    return filename

def load_csv(filepath):
    data = {}
    if not os.path.exists(filepath):
        return data
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            data[row["Name"]] = int(row["Experience"].replace(",", ""))
    return data

def compare_and_generate_html(today_data, yesterday_data, output_file):
    changes = []
    for name, exp in today_data.items():
        old_exp = yesterday_data.get(name, None)
        if old_exp is not None:
            diff = exp - old_exp
            if diff != 0:
                changes.append((name, old_exp, exp, diff))

    changes.sort(key=lambda x: x[3], reverse=True)

    html_content = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>Experience Changes</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background: #f9f9f9; }}
            table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
            th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
            th {{ background: #444; color: #fff; }}
            tr:nth-child(even) {{ background: #eee; }}
            .gain {{ color: green; font-weight: bold; }}
            .loss {{ color: red; font-weight: bold; }}
        </style>
    </head>
    <body>
        <h2>Experience Changes ({datetime.now().strftime("%Y-%m-%d")})</h2>
        <table>
            <tr><th>Name</th><th>Yesterday</th><th>Today</th><th>Change</th></tr>
    """

    for name, old, new, diff in changes:
        cls = "gain" if diff > 0 else "loss"
        html_content += f"<tr><td>{name}</td><td>{old:,}</td><td>{new:,}</td><td class='{cls}'>{diff:+,}</td></tr>"

    html_content += """
        </table>
    </body>
    </html>
    """

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    return output_file

if __name__ == "__main__":
    # Fetch 200 pages live
    rows = build_snapshot(pages=10, delay=0.25)

    # Save today's CSV
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_file = save_csv(rows, today_str)

    # Load yesterday's CSV
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    yesterday_file = os.path.join(SAVE_DIR, f"highscores_{yesterday_str}.csv")


    today_dict = {name: exp for name, exp in rows}
    yesterday_dict = load_csv(yesterday_file)

    # Generate HTML report
    report_file = os.path.join(SAVE_DIR, f"changes_{today_str}.html")
    compare_and_generate_html(today_dict, yesterday_dict, report_file)

    print("CSV snapshot saved:", today_file)
    print("HTML report saved:", report_file)
