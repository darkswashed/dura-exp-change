import os
import csv
import time
import requests
import subprocess
from datetime import datetime, timedelta
import pytz
from bs4 import BeautifulSoup

BASE_URL_FIRST = "https://classic.dura-online.com/?highscores/experience"
BASE_URL_PAGED = "https://classic.dura-o    # Calculate statistics
    common_players = set(today_data.keys()) & set(yesterday_data.keys())
    changes_count = sum(1 for name in common_players if today_data[name] != yesterday_data[name])
    
    # Load historical data for additional stats
    seven_days_ago = (get_eastern_date() - timedelta(days=7)).strftime("%Y-%m-%d")
    thirty_days_ago = (get_eastern_date() - timedelta(days=30)).strftime("%Y-%m-%d")
    seven_day_data = load_historical_data(seven_days_ago)
    thirty_day_data = load_historical_data(thirty_days_ago)
    
    print(f"Players present in both snapshots: {len(common_players)}")
    print(f"Players with 1-day changes: {changes_count}")
    print(f"Historical data available:")
    print(f"  - 7-day ({seven_days_ago}): {len(seven_day_data):,} players")
    print(f"  - 30-day ({thirty_days_ago}): {len(thirty_day_data):,} players")
    
    # Commit and push to git
    commit_message = f"Update index.html {today_date}"
    git_success = git_commit_push(report_file, commit_message)
    
    # Print completion status
    if git_success:
        print(f"✅ Successfully processed multi-period comparison for {today_date}")
        print(f"📊 Players analyzed: {len(common_players):,}")
        print(f"📈 1-day changes: {changes_count:,}")
        print(f"📅 7-day data: {'Available' if seven_day_data else 'Not available'}")
        print(f"📅 30-day data: {'Available' if thirty_day_data else 'Not available'}")
    else:
        print(f"⚠️ Comparison completed but git operations may have failed")res/experience/{}"
SAVE_DIR = "snapshots"

def get_eastern_date():
    """Get current date in Eastern Time (EST/EDT)"""
    eastern = pytz.timezone('US/Eastern')
    return datetime.now(eastern)

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
            name_td = cols[1]
            name_tag = name_td.find(["a", "span"])
            if name_tag:
                name = name_tag.get_text(strip=True)
            else:
                name = name_td.get_text(strip=True).split("\n")[0]
            exp = cols[3].get_text(strip=True).replace(",", "")
            if exp.isdigit():
                rows.append([name, int(exp)])
    return rows

def build_snapshot(pages=200, delay=0.05):
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
        date = get_eastern_date().strftime("%Y-%m-%d")
    filename = os.path.join(SAVE_DIR, f"highscores_{date}.csv")
    with open(filename, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "Experience"])
        writer.writerows(data)
    return filename

def load_csv(filepath):
    """Load CSV data into a dictionary with name as key and experience as value"""
    data = {}
    if not os.path.exists(filepath):
        print(f"Warning: {filepath} not found")
        return data
    
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            data[row["Name"]] = int(row["Experience"].replace(",", ""))
    return data

def load_historical_data(target_date):
    """Load historical data for a specific date"""
    filepath = os.path.join(SAVE_DIR, f"highscores_{target_date}.csv")
    if os.path.exists(filepath):
        return load_csv(filepath)
    return {}

def compare_and_generate_html(today_data, yesterday_data, output_file):
    """Compare datasets and generate comprehensive HTML report with 1-day, 7-day, and 30-day changes"""
    today_date = get_eastern_date()
    
    # Calculate dates for 7-day and 30-day comparisons
    seven_days_ago = (today_date - timedelta(days=7)).strftime("%Y-%m-%d")
    thirty_days_ago = (today_date - timedelta(days=30)).strftime("%Y-%m-%d")
    
    # Load historical data
    seven_day_data = load_historical_data(seven_days_ago)
    thirty_day_data = load_historical_data(thirty_days_ago)
    
    # Prepare comprehensive changes data
    all_players = set(today_data.keys())
    changes_data = []
    
    for name in all_players:
        today_exp = today_data.get(name, 0)
        yesterday_exp = yesterday_data.get(name, None)
        seven_day_exp = seven_day_data.get(name, None)
        thirty_day_exp = thirty_day_data.get(name, None)
        
        # Calculate changes
        day_change = today_exp - yesterday_exp if yesterday_exp is not None else None
        seven_day_change = today_exp - seven_day_exp if seven_day_exp is not None else None
        thirty_day_change = today_exp - thirty_day_exp if thirty_day_exp is not None else None
        
        # Only include players with at least one valid comparison
        if day_change is not None or seven_day_change is not None or thirty_day_change is not None:
            changes_data.append({
                'name': name,
                'today': today_exp,
                'yesterday': yesterday_exp,
                'seven_days_ago': seven_day_exp,
                'thirty_days_ago': thirty_day_exp,
                'day_change': day_change,
                'seven_day_change': seven_day_change,
                'thirty_day_change': thirty_day_change
            })
    
    # Sort by 1-day change (descending), then by 7-day change
    changes_data.sort(key=lambda x: (x['day_change'] or 0, x['seven_day_change'] or 0), reverse=True)
    
    # Generate HTML
    html_content = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>Dura Highscores Experience Changes</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background: #f9f9f9; }}
            .header {{ text-align: center; margin-bottom: 30px; }}
            .summary {{ background: #fff; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
            table {{ border-collapse: collapse; width: 100%; margin-top: 20px; background: #fff; }}
            th, td {{ border: 1px solid #ddd; padding: 10px; text-align: right; }}
            th {{ background: #2c3e50; color: #fff; text-align: center; }}
            .name {{ text-align: left !important; font-weight: bold; }}
            tr:nth-child(even) {{ background: #f8f9fa; }}
            .gain {{ color: #27ae60; font-weight: bold; }}
            .loss {{ color: #e74c3c; font-weight: bold; }}
            .neutral {{ color: #7f8c8d; }}
            .na {{ color: #bdc3c7; font-style: italic; }}
            .period-header {{ background: #34495e !important; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🎮 Dura Online Highscores Tracker</h1>
            <h2>Experience Changes - {today_date.strftime("%Y-%m-%d")}</h2>
        </div>
        
        <div class="summary">
            <h3>📊 Summary</h3>
            <p><strong>Total Players Tracked:</strong> {len(changes_data):,}</p>
            <p><strong>Historical Data Available:</strong></p>
            <ul>
                <li>7-day comparison ({seven_days_ago}): {'✅' if seven_day_data else '❌'} ({len(seven_day_data):,} players)</li>
                <li>30-day comparison ({thirty_days_ago}): {'✅' if thirty_day_data else '❌'} ({len(thirty_day_data):,} players)</li>
            </ul>
        </div>
        
        <table>
            <tr>
                <th rowspan="2" class="name">Player Name</th>
                <th rowspan="2">Current Experience</th>
                <th colspan="3" class="period-header">Experience Changes</th>
            </tr>
            <tr>
                <th>1 Day</th>
                <th>7 Days</th>
                <th>30 Days</th>
            </tr>
    """
    
    for player in changes_data:
        name = player['name']
        today = player['today']
        
        # Format changes with appropriate styling
        def format_change(change):
            if change is None:
                return '<span class="na">N/A</span>'
            elif change > 0:
                return f'<span class="gain">+{change:,}</span>'
            elif change < 0:
                return f'<span class="loss">{change:,}</span>'
            else:
                return '<span class="neutral">0</span>'
        
        day_change_html = format_change(player['day_change'])
        seven_day_change_html = format_change(player['seven_day_change'])
        thirty_day_change_html = format_change(player['thirty_day_change'])
        
        html_content += f"""
            <tr>
                <td class="name">{name}</td>
                <td>{today:,}</td>
                <td>{day_change_html}</td>
                <td>{seven_day_change_html}</td>
                <td>{thirty_day_change_html}</td>
            </tr>
        """
    
    html_content += """
        </table>
        
        <div style="margin-top: 30px; text-align: center; color: #7f8c8d; font-size: 12px;">
            <p>🤖 Generated automatically by GitHub Actions | 📅 Updates daily at 10 AM EST</p>
            <p>🔗 <a href="https://github.com/darkswashed/dura-exp-change">View Source Code</a></p>
        </div>
    </body>
    </html>
    """

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    return output_file

def git_commit_push(filepath, commit_message="Update index.html"):
    """Commit and push the HTML file to git repository"""
    # In GitHub Actions, authentication is handled automatically
    print(f"📝 Note: Git operations will be handled by GitHub Actions workflow")
    print(f"✅ {filepath} ready for commit with message: {commit_message}")
    return True  # Always return True as GitHub Actions will handle the actual git operations



def compare_only(today_date=None, yesterday_date=None):
    """
    Compare existing snapshots and generate HTML report without scraping
    
    Args:
        today_date: Date string in YYYY-MM-DD format for today's snapshot
        yesterday_date: Date string in YYYY-MM-DD format for yesterday's snapshot
    """
    # Default to current date and previous day if not specified
    if today_date is None:
        today_date = get_eastern_date().strftime("%Y-%m-%d")
    
    if yesterday_date is None:
        yesterday_date = (get_eastern_date() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Construct file paths
    today_file = os.path.join(SAVE_DIR, f"highscores_{today_date}.csv")
    yesterday_file = os.path.join(SAVE_DIR, f"highscores_{yesterday_date}.csv")
    
    print(f"Loading today's data from: {today_file}")
    print(f"Loading yesterday's data from: {yesterday_file}")
    
    # Load data from CSV files
    today_data = load_csv(today_file)
    yesterday_data = load_csv(yesterday_file)
    
    if not today_data:
        print(f"Error: No data found in {today_file}")
        return
    
    if not yesterday_data:
        print(f"Warning: No data found in {yesterday_file}. Only today's data will be shown.")
    
    # Generate HTML report
    report_file = "index.html"
    compare_and_generate_html(today_data, yesterday_data, report_file)
    
    print(f"HTML report generated: {report_file}")
    print(f"Found {len(today_data)} players in today's data")
    print(f"Found {len(yesterday_data)} players in yesterday's data")
    
    # Calculate statistics
    common_players = set(today_data.keys()) & set(yesterday_data.keys())
    changes_count = sum(1 for name in common_players if today_data[name] != yesterday_data[name])
    
    print(f"Players present in both snapshots: {len(common_players)}")
    print(f"Players with experience changes: {changes_count}")
    
    # Commit and push to git
    commit_message = f"Update index.html {today_date}"
    git_success = git_commit_push(report_file, commit_message)
    
    # Print completion status
    if git_success:
        print(f"✅ Successfully processed comparison for {today_date}")
        print(f"� Players analyzed: {len(common_players):,}")
        print(f"📈 Changes detected: {changes_count:,}")
    else:
        print(f"⚠️ Comparison completed but git operations may have failed")

if __name__ == "__main__":
    import sys
    
    # Check for command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--compare-only":
            # Compare-only mode
            if len(sys.argv) == 4:
                today_date = sys.argv[2]
                yesterday_date = sys.argv[3]
                compare_only(today_date, yesterday_date)
            elif len(sys.argv) == 3:
                today_date = sys.argv[2]
                compare_only(today_date)
            else:
                compare_only()
        elif sys.argv[1] == "--help":
            print("Usage:")
            print("  python highscore.py                              # Full scrape + compare")
            print("  python highscore.py --compare-only               # Compare existing snapshots (today vs yesterday)")
            print("  python highscore.py --compare-only 2025-10-03    # Compare with specific today date")
            print("  python highscore.py --compare-only 2025-10-03 2025-10-02  # Compare specific dates")
            print("  python highscore.py --help                       # Show this help")
        else:
            print(f"Unknown argument: {sys.argv[1]}")
            print("Use --help for usage information")
    else:
        # Default mode: scrape and compare
        print("Starting full scrape and compare process...")
        rows = build_snapshot(pages=200, delay=0.25)

        today_str = get_eastern_date().strftime("%Y-%m-%d")
        today_file = save_csv(rows, today_str)

        yesterday_str = (get_eastern_date() - timedelta(days=1)).strftime("%Y-%m-%d")
        yesterday_file = os.path.join(SAVE_DIR, f"highscores_{yesterday_str}.csv")

        today_dict = {name: exp for name, exp in rows}
        yesterday_dict = load_csv(yesterday_file)

        report_file = "index.html"
        compare_and_generate_html(today_dict, yesterday_dict, report_file)

        print("CSV snapshot saved:", today_file)
        print("HTML report saved:", report_file)

        git_success = git_commit_push(report_file, commit_message=f"Update index.html {get_eastern_date().strftime('%Y-%m-%d')}")
        
        # Print completion status for full scrape with enhanced statistics
        common_players = set(today_dict.keys()) & set(yesterday_dict.keys())
        changes_count = sum(1 for name in common_players if today_dict[name] != yesterday_dict[name])
        
        # Load historical data for additional stats
        seven_days_ago = (get_eastern_date() - timedelta(days=7)).strftime("%Y-%m-%d")
        thirty_days_ago = (get_eastern_date() - timedelta(days=30)).strftime("%Y-%m-%d")
        seven_day_data = load_historical_data(seven_days_ago)
        thirty_day_data = load_historical_data(thirty_days_ago)
        
        print(f"🎆 Dura Highscores Full Scrape Complete!")
        print(f"📅 Date: {today_str}")
        print(f"🔍 Scraped: {len(rows):,} players")
        print(f"👥 1-day comparison: {len(common_players):,} players")
        print(f"📈 1-day changes: {changes_count:,}")
        print(f"📅 Historical data:")
        print(f"    7-day ({seven_days_ago}): {len(seven_day_data):,} players")
        print(f"    30-day ({thirty_days_ago}): {len(thirty_day_data):,} players")
        print(f"💾 CSV saved: {today_file}")
        print(f"📝 Enhanced HTML report saved: {report_file}")
        
        if git_success:
            print("✅ All operations completed successfully!")
        else:
            print("⚠️ Operations completed but git push may have failed")
