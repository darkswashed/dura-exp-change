import os
import csv
import time
import requests
import subprocess
from datetime import datetime, timedelta
import pytz
from bs4 import BeautifulSoup
from urllib.parse import quote

BASE_URL_FIRST = "https://classic.dura-online.com/?highscores/experience"

def calculate_level_from_exp(experience):
    """
    Calculate the player's level based on their experience using the reverse of the experience formula.
    The formula for experience to reach a level is: 50(lvl-1)³ - 150(lvl-1)² + 400(lvl-1) / 3
    We need to solve for level given experience.
    
    Uses an improved iterative approach that works for very high levels.
    """
    if experience <= 0:
        return 1.0
    
    def exp_to_reach_level(level):
        """Calculate total experience needed to reach a certain level"""
        if level <= 1:
            return 0
        lvl_minus_1 = level - 1
        numerator = (50 * (lvl_minus_1 ** 3)) - (150 * (lvl_minus_1 ** 2)) + (400 * lvl_minus_1)
        return numerator / 3
    
    # Start with a reasonable estimate based on cubic root approximation
    # For very high exp, the dominant term is 50(lvl-1)³/3, so lvl ≈ (3*exp/50)^(1/3) + 1
    rough_estimate = ((3 * experience / 50) ** (1/3)) + 1
    
    # Use Newton-Raphson method for better convergence at high levels
    level = max(1.0, rough_estimate)
    
    for iteration in range(50):  # More iterations for high precision
        current_exp = exp_to_reach_level(level)
        
        # Check if we're close enough
        if abs(current_exp - experience) < 0.1:
            return level
        
        # Calculate derivative for Newton-Raphson
        # d/dx[50(x-1)³ - 150(x-1)² + 400(x-1)]/3 = [150(x-1)² - 300(x-1) + 400]/3
        lvl_minus_1 = level - 1
        derivative = (150 * (lvl_minus_1 ** 2) - 300 * lvl_minus_1 + 400) / 3
        
        if derivative == 0:
            # Fallback to binary search if derivative is zero
            break
        
        # Newton-Raphson step
        new_level = level - (current_exp - experience) / derivative
        
        # Ensure we don't go below 1 or make wild jumps
        if new_level < 1:
            new_level = 1.0
        elif abs(new_level - level) > 10:  # Limit step size for stability
            if new_level > level:
                new_level = level + 10
            else:
                new_level = level - 10
        
        level = new_level
    
    # Fallback binary search if Newton-Raphson didn't converge
    low = 1.0
    high = max(1000.0, level * 2)  # Use a much higher upper bound
    
    for _ in range(100):
        mid = (low + high) / 2
        exp_for_mid = exp_to_reach_level(mid)
        
        if abs(exp_for_mid - experience) < 0.1:
            return mid
        elif exp_for_mid < experience:
            low = mid
        else:
            high = mid
    
    return (low + high) / 2
BASE_URL_PAGED = "https://classic.dura-online.com/?highscores/experience/{}"
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
            # Extract name
            name_td = cols[1]
            name_tag = name_td.find(["a", "span"])
            if name_tag:
                name = name_tag.get_text(strip=True)
            else:
                name = name_td.get_text(strip=True).split("\n")[0]
            
            # Extract experience points
            exp = cols[3].get_text(strip=True).replace(",", "")
            
            # Validate that experience is valid
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
        date = datetime.now().strftime("%Y-%m-%d")
    filename = os.path.join(SAVE_DIR, f"highscores_{date}.csv")
    with open(filename, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "Experience"])
        writer.writerows(data)
    return filename

def load_csv(filepath):
    """Load CSV data into a dictionary with name as key and all player data as value"""
    data = {}
    if not os.path.exists(filepath):
        print(f"Warning: {filepath} not found")
        return data
    
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            player_data = {
                'experience': int(row["Experience"].replace(",", "")),
            }
            
            # Handle new format with rank and level (backward compatibility)
            if "Rank" in row and row["Rank"]:
                player_data['rank'] = int(row["Rank"].replace(",", ""))
            else:
                player_data['rank'] = None
                
            if "Level" in row and row["Level"]:
                player_data['level'] = int(row["Level"].replace(",", ""))
            else:
                player_data['level'] = None
            
            data[row["Name"]] = player_data
    return data

def find_best_historical_data(target_days_back, max_days_back, reference_date=None):
    """
    Find the best available historical data within a range of days
    
    Args:
        target_days_back: Preferred number of days back (e.g., 7 for weekly)
        max_days_back: Maximum days to look back (e.g., 10 for weekly range)
        reference_date: Date to use as reference point (if None, uses current Eastern date)
    
    Returns:
        tuple: (data_dict, actual_date_found, days_back_found)
    """
    if reference_date is None:
        today_date = get_eastern_date()
    else:
        # Parse the reference date string if provided
        if isinstance(reference_date, str):
            today_date = datetime.strptime(reference_date, "%Y-%m-%d")
        else:
            today_date = reference_date
    
    # Start from target days back and work backwards to find available data
    for days_back in range(target_days_back, max_days_back + 1):
        check_date = (today_date - timedelta(days=days_back)).strftime("%Y-%m-%d")
        filepath = os.path.join(SAVE_DIR, f"highscores_{check_date}.csv")
        
        if os.path.exists(filepath):
            data = load_csv(filepath)
            if data:  # Make sure data was actually loaded
                print(f"Found historical data: {check_date} ({days_back} days back)")
                return data, check_date, days_back
    
    # If no data found in the range, return empty
    print(f"No historical data found in {target_days_back}-{max_days_back} day range")
    return {}, None, None

def find_oldest_available_data():
    """
    Find the oldest available historical data for fallback comparisons
    
    Returns:
        tuple: (data_dict, actual_date_found, days_back_found)
    """
    all_snapshots = get_all_available_snapshots()
    if not all_snapshots:
        return {}, None, None
    
    # Get the oldest snapshot (last in the sorted list)
    oldest_date = all_snapshots[-1]
    oldest_filepath = os.path.join(SAVE_DIR, f"highscores_{oldest_date}.csv")
    
    data = load_csv(oldest_filepath)
    if data:
        today_date = get_eastern_date()
        oldest_datetime = datetime.strptime(oldest_date, "%Y-%m-%d")
        days_back = (today_date.date() - oldest_datetime.date()).days
        print(f"Using oldest available data: {oldest_date} ({days_back} days back)")
        return data, oldest_date, days_back
    
    return {}, None, None

def get_all_available_snapshots():
    """Get all available snapshot dates sorted from newest to oldest"""
    if not os.path.exists(SAVE_DIR):
        return []
    
    snapshot_files = []
    for filename in os.listdir(SAVE_DIR):
        if filename.startswith("highscores_") and filename.endswith(".csv"):
            # Extract date from filename
            date_part = filename.replace("highscores_", "").replace(".csv", "")
            try:
                # Validate date format
                datetime.strptime(date_part, "%Y-%m-%d")
                snapshot_files.append(date_part)
            except ValueError:
                continue
    
    # Sort from newest to oldest
    snapshot_files.sort(reverse=True)
    return snapshot_files

def compare_and_generate_html(today_data, yesterday_data, output_file, reference_date=None):
    """Compare datasets and generate comprehensive HTML report with intelligent multi-period changes"""
    if reference_date is None:
        today_date = get_eastern_date()
        reference_date_str = today_date.strftime("%Y-%m-%d")
    else:
        # If reference_date is provided, use it for both display and historical data lookup
        if isinstance(reference_date, str):
            today_date = datetime.strptime(reference_date, "%Y-%m-%d")
            reference_date_str = reference_date
        else:
            today_date = reference_date
            reference_date_str = reference_date.strftime("%Y-%m-%d")
    
    # Find best available historical data using intelligent fallback
    # For 7-day: look 3-10 days back (more flexible for weekly data)
    seven_day_data, seven_day_date, seven_days_back = find_best_historical_data(3, 10, reference_date_str)
    # For 30-day: look 15-35 days back (more flexible for monthly data)
    thirty_day_data, thirty_day_date, thirty_days_back = find_best_historical_data(15, 35, reference_date_str)
    
    # If no specific period data found, use oldest available as fallback
    oldest_data, oldest_date, oldest_days_back = find_oldest_available_data()
    
    # Use oldest data as fallback for missing periods
    if not seven_day_data and oldest_data:
        seven_day_data, seven_day_date, seven_days_back = oldest_data, oldest_date, oldest_days_back
        print(f"Using oldest data for 7-day fallback: {oldest_date} ({oldest_days_back} days)")
    
    if not thirty_day_data and oldest_data:
        thirty_day_data, thirty_day_date, thirty_days_back = oldest_data, oldest_date, oldest_days_back
        print(f"Using oldest data for 30-day fallback: {oldest_date} ({oldest_days_back} days)")
    
    # Get list of all available snapshots for summary
    all_snapshots = get_all_available_snapshots()
    
    # Calculate ranks for today and yesterday based on experience
    def calculate_ranks(player_data):
        """Calculate rank positions based on experience (highest exp = rank 1)"""
        if not player_data:
            return {}
        
        # Convert to list of (name, experience) and sort by experience (highest first)
        player_list = []
        for name, data in player_data.items():
            if isinstance(data, dict):
                experience = data.get('experience', 0)
            else:
                # Handle old format where data was just experience value
                experience = data
            player_list.append((name, experience))
        
        # Sort by experience (highest first)
        player_list.sort(key=lambda x: x[1], reverse=True)
        
        # Create rank mapping
        rank_mapping = {}
        for rank, (name, _) in enumerate(player_list, 1):
            rank_mapping[name] = rank
            
        return rank_mapping
    
    # Get rank mappings
    today_ranks = calculate_ranks(today_data)
    yesterday_ranks = calculate_ranks(yesterday_data)
    
    # Prepare comprehensive changes data
    all_players = set(today_data.keys())
    changes_data = []
    
    for name in all_players:
        # Get today's data
        today_player = today_data.get(name, {})
        if isinstance(today_player, dict):
            today_exp = today_player.get('experience', 0)
        else:
            # Handle old format where data was just experience value
            today_exp = today_player
        
        # Use calculated ranks
        today_rank = today_ranks.get(name, None)
        
        # Get yesterday's data
        yesterday_player = yesterday_data.get(name, {})
        if isinstance(yesterday_player, dict):
            yesterday_exp = yesterday_player.get('experience', None)
        else:
            # Handle old format where data was just experience value
            yesterday_exp = yesterday_player if yesterday_player else None
        
        # Use calculated ranks
        yesterday_rank = yesterday_ranks.get(name, None)
        
        # Get 7-day data
        seven_day_player = seven_day_data.get(name, {})
        seven_day_exp = seven_day_player.get('experience', None) if seven_day_player else None
        
        # Get 30-day data
        thirty_day_player = thirty_day_data.get(name, {})
        thirty_day_exp = thirty_day_player.get('experience', None) if thirty_day_player else None
        
        # Calculate changes
        exp_day_change = today_exp - yesterday_exp if yesterday_exp is not None else None
        exp_seven_day_change = today_exp - seven_day_exp if seven_day_exp is not None else None
        exp_thirty_day_change = today_exp - thirty_day_exp if thirty_day_exp is not None else None
        
        rank_day_change = yesterday_rank - today_rank if (today_rank is not None and yesterday_rank is not None) else None
        
        # Only include players who have actual experience changes (not zero or None)
        has_experience_changes = (
            (exp_day_change is not None and exp_day_change != 0) or
            (exp_seven_day_change is not None and exp_seven_day_change != 0) or
            (exp_thirty_day_change is not None and exp_thirty_day_change != 0)
        )
        
        if has_experience_changes:
            changes_data.append({
                'name': name,
                'today_exp': today_exp,
                'today_rank': today_rank,
                'exp_day_change': exp_day_change,
                'exp_seven_day_change': exp_seven_day_change,
                'exp_thirty_day_change': exp_thirty_day_change,
                'rank_day_change': rank_day_change,
                'yesterday_exp': yesterday_exp,
                'seven_day_exp': seven_day_exp,
                'thirty_day_exp': thirty_day_exp
            })
    
    # Sort by current rank (if available), then by name
    changes_data.sort(key=lambda x: (x['today_rank'] or 999999, x['name'].lower()))
    
    # Generate HTML
    html_content = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>Dura Highscores Experience Changes</title>
        <style>
            :root {{
                --bg-color: #f5f6fa;
                --text-color: #2c3e50;
                --table-bg: #fff;
                --table-border: #e1e8ed;
                --header-bg: #2c3e50;
                --header-text: #fff;
                --row-even: #f8f9fa;
                --row-odd: #ffffff;
                --row-hover: #e8f4fd;
                --link-color: #2980b9;
                --link-hover-bg: #3498db;
                --gain-color: #27ae60;
                --loss-color: #e74c3c;
                --neutral-color: #7f8c8d;
                --na-color: #bdc3c7;
                --button-bg: #3498db;
                --button-text: #fff;
                --button-hover: #2980b9;
            }}

            [data-theme="dark"] {{
                --bg-color: #1a1a1a;
                --text-color: #e8e8e8;
                --table-bg: #2d2d2d;
                --table-border: #404040;
                --header-bg: #1e3a5f;
                --header-text: #e8e8e8;
                --row-even: #333333;
                --row-odd: #2d2d2d;
                --row-hover: #404040;
                --link-color: #5dade2;
                --link-hover-bg: #2980b9;
                --gain-color: #2ecc71;
                --loss-color: #e67e22;
                --neutral-color: #95a5a6;
                --na-color: #7f8c8d;
                --button-bg: #34495e;
                --button-text: #ecf0f1;
                --button-hover: #2c3e50;
            }}

            body {{ 
                font-family: Arial, sans-serif; 
                margin: 20px; 
                background: var(--bg-color); 
                color: var(--text-color);
                transition: background-color 0.3s ease, color 0.3s ease;
            }}
            
            .banner {{
                display: flex;
                justify-content: center;
                align-items: center;
                margin-bottom: 20px;
                width: 100%;
            }}
            
            .banner img {{
                max-width: 100%;
                height: auto;
                object-fit: contain;
            }}
            
            .controls {{
                display: flex;
                justify-content: center;
                align-items: center;
                gap: 20px;
                margin-bottom: 20px;
                flex-wrap: wrap;
            }}
            
            .theme-toggle {{
                padding: 10px 20px;
                background: var(--button-bg);
                color: var(--button-text);
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 14px;
                transition: all 0.3s ease;
                display: flex;
                align-items: center;
                gap: 8px;
            }}
            
            .theme-toggle:hover {{
                background: var(--button-hover);
                transform: translateY(-1px);
            }}
            
            .header {{ text-align: center; margin-bottom: 30px; }}
            .header h1, .header h2 {{ color: var(--text-color); }}
            
            table {{ 
                border-collapse: collapse; 
                width: 100%; 
                margin-top: 20px; 
                background: var(--table-bg); 
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }}
            
            th, td {{ 
                border: 1px solid var(--table-border); 
                padding: 12px; 
                text-align: center; 
                transition: background-color 0.2s ease;
            }}
            
            th {{ 
                background: var(--header-bg); 
                color: var(--header-text); 
                text-align: center; 
                position: sticky; 
                top: 0; 
                z-index: 10;
                box-shadow: 0 2px 4px rgba(0,0,0,0.15);
                font-weight: 600;
                cursor: pointer;
                user-select: none;
                position: relative;
            }}
            
            th:hover {{
                background: color-mix(in srgb, var(--header-bg) 80%, #fff 20%);
            }}
            
            th.sortable::after {{
                content: ' ↕';
                opacity: 0.5;
                font-size: 12px;
            }}
            
            th.sort-asc::after {{
                content: ' ↑';
                opacity: 1;
                color: var(--gain-color);
            }}
            
            th.sort-desc::after {{
                content: ' ↓';
                opacity: 1;
                color: var(--loss-color);
            }}
            
            .name {{ text-align: left !important; font-weight: bold; }}
            .name a {{ 
                color: var(--link-color); 
                text-decoration: underline; 
                text-decoration-color: rgba(41, 128, 185, 0.3);
                text-underline-offset: 2px;
                transition: all 0.2s ease;
                padding: 2px 4px;
                border-radius: 3px;
            }}
            .name a:hover {{ 
                color: var(--header-text); 
                background: var(--link-hover-bg); 
                text-decoration: none;
                transform: translateY(-1px);
                box-shadow: 0 2px 4px rgba(52, 152, 219, 0.3);
            }}
            
            tr:nth-child(even) {{ background: var(--row-even); }}
            tr:nth-child(odd) {{ background: var(--row-odd); }}
            tr:hover {{ background: var(--row-hover); }}
            
            .gain {{ color: var(--gain-color); font-weight: bold; }}
            .loss {{ color: var(--loss-color); font-weight: bold; }}
            .neutral {{ color: var(--neutral-color); }}
            .na {{ color: var(--na-color); font-style: italic; }}
            .period-header {{ background: #34495e !important; position: sticky; top: 0; z-index: 10; font-weight: 600; }}
            
            .footer {{
                margin-top: 30px; 
                text-align: center; 
                color: var(--neutral-color); 
                font-size: 12px;
            }}
            
            .footer a {{
                color: var(--link-color);
                text-decoration: none;
            }}
            
            .footer a:hover {{
                text-decoration: underline;
            }}
        </style>
    </head>
    <body data-theme="light">
        <div class="banner">
            <img src="banner.gif" alt="Banner" />
        </div>
        
        <div class="header">
            <h1>🎮 Dura Online Highscores Tracker</h1>
            <h2>Experience Changes - {today_date.strftime("%Y-%m-%d")}</h2>
        </div>
        
        <div class="controls">
            <button class="theme-toggle" onclick="toggleTheme()">
                <span class="theme-icon">🌙</span>
                <span class="theme-text">Dark Mode</span>
            </button>
        </div>
        
        <table id="highscoresTable">
            <tr>
                <th rowspan="2" class="name sortable" data-column="name">Player Name</th>
                <th rowspan="2" class="sortable" data-column="rank">Rank</th>
                <th rowspan="2" class="sortable" data-column="level">Level</th>
                <th rowspan="2" class="sortable" data-column="experience">Experience</th>
                <th colspan="3" class="period-header">Experience Changes</th>
            </tr>
            <tr>
                <th class="sortable" data-column="exp-day">1 Day</th>
                <th class="sortable" data-column="exp-week">7 Days</th>
                <th class="sortable" data-column="exp-month">30 Days</th>
            </tr>
    """
    
    for player in changes_data:
        name = player['name']
        
        # Current values
        today_exp = player['today_exp']
        today_rank = player['today_rank']
        
        # Format changes with appropriate styling
        def format_exp_change(change, previous_exp):
            if change is None:
                return '<span class="na">N/A</span>'
            elif change == 0:
                return '<span class="neutral">0</span>'
            else:
                if change > 0:
                    return f'<span class="gain">+{change:,}</span>'
                else:
                    return f'<span class="loss">{change:,}</span>'
        
        def format_rank_change(change):
            if change is None:
                return '<span class="na">N/A</span>'
            elif change > 0:  # Rank improvement (lower number is better)
                return f'<span class="gain">+{change:,}</span>'
            elif change < 0:  # Rank decline (higher number is worse)
                return f'<span class="loss">{change:,}</span>'
            else:
                return '<span class="neutral">0</span>'
        
        def format_level_change(change):
            if change is None:
                return '<span class="na">N/A</span>'
            elif change > 0:
                return f'<span class="gain">+{change:,}</span>'
            elif change < 0:
                return f'<span class="loss">{change:,}</span>'
            else:
                return '<span class="neutral">0</span>'
        

        
        # Format current values with changes
        def format_rank_with_change(rank, change):
            if rank is None:
                return "N/A"
            base = f"#{rank:,}"
            if change is None:
                return base
            elif change > 0:  # Rank improvement (lower number is better)
                return f"{base} <span class='gain'>+{change}</span>"
            elif change < 0:  # Rank decline (higher number is worse)
                return f"{base} <span class='loss'>{change}</span>"
            else:
                return base
        
        rank_display = format_rank_with_change(today_rank, player['rank_day_change'])
        
        # Calculate player level
        player_level = calculate_level_from_exp(today_exp)
        
        # Format experience changes with percentages
        exp_day_change_html = format_exp_change(player['exp_day_change'], player['yesterday_exp'])
        exp_seven_day_change_html = format_exp_change(player['exp_seven_day_change'], player['seven_day_exp'])
        exp_thirty_day_change_html = format_exp_change(player['exp_thirty_day_change'], player['thirty_day_exp'])
        
        # Get raw values for sorting
        rank_raw = today_rank if today_rank is not None else 999999
        exp_day_change_raw = player['exp_day_change'] if player['exp_day_change'] is not None else 0
        exp_seven_day_change_raw = player['exp_seven_day_change'] if player['exp_seven_day_change'] is not None else 0
        exp_thirty_day_change_raw = player['exp_thirty_day_change'] if player['exp_thirty_day_change'] is not None else 0
        
        html_content += f"""
            <tr data-name="{name.lower()}" 
                data-rank="{rank_raw}" 
                data-level="{player_level:.2f}"
                data-experience="{today_exp}" 
                data-exp-day="{exp_day_change_raw}" 
                data-exp-week="{exp_seven_day_change_raw}" 
                data-exp-month="{exp_thirty_day_change_raw}">
                <td class="name"><a href="player_history.html?player={quote(name)}">{name}</a></td>
                <td>{rank_display}</td>
                <td>Lv. {int(player_level)}</td>
                <td>{today_exp:,}</td>
                <td>{exp_day_change_html}</td>
                <td>{exp_seven_day_change_html}</td>
                <td>{exp_thirty_day_change_html}</td>
            </tr>
        """
    
    html_content += """
        </table>
        
        <div class="footer">
            <p>🤖 Generated automatically by GitHub Actions | 📅 Updates daily at 10 AM EST</p>
            <p>📈 Intelligent historical data lookup - uses best available data within range</p>
            <p>🔗 <a href="https://github.com/darkswashed/dura-exp-change">View Source Code</a></p>
        </div>
        
        <script>
            let currentSort = { column: null, direction: 'asc' };
            
            // Theme management
            function toggleTheme() {
                const body = document.body;
                const themeIcon = document.querySelector('.theme-icon');
                const themeText = document.querySelector('.theme-text');
                const currentTheme = body.getAttribute('data-theme');
                
                if (currentTheme === 'light') {
                    body.setAttribute('data-theme', 'dark');
                    themeIcon.textContent = '☀️';
                    themeText.textContent = 'Light Mode';
                    localStorage.setItem('theme', 'dark');
                } else {
                    body.setAttribute('data-theme', 'light');
                    themeIcon.textContent = '🌙';
                    themeText.textContent = 'Dark Mode';
                    localStorage.setItem('theme', 'light');
                }
            }
            
            // Load saved theme
            function loadTheme() {
                const savedTheme = localStorage.getItem('theme') || 'light';
                const body = document.body;
                const themeIcon = document.querySelector('.theme-icon');
                const themeText = document.querySelector('.theme-text');
                
                body.setAttribute('data-theme', savedTheme);
                if (savedTheme === 'dark') {
                    themeIcon.textContent = '☀️';
                    themeText.textContent = 'Light Mode';
                } else {
                    themeIcon.textContent = '🌙';
                    themeText.textContent = 'Dark Mode';
                }
            }
            
            // Sorting functionality
            function sortTable(column) {
                const table = document.getElementById('highscoresTable');
                const tbody = table.querySelector('tbody') || table;
                const rows = Array.from(tbody.querySelectorAll('tr')).slice(2); // Skip header rows
                
                // Determine sort direction
                if (currentSort.column === column) {
                    currentSort.direction = currentSort.direction === 'asc' ? 'desc' : 'asc';
                } else {
                    currentSort.column = column;
                    currentSort.direction = 'asc';
                }
                
                // Update header indicators
                document.querySelectorAll('th.sortable').forEach(th => {
                    th.classList.remove('sort-asc', 'sort-desc');
                });
                const activeHeader = document.querySelector(`th[data-column="${column}"]`);
                activeHeader.classList.add(currentSort.direction === 'asc' ? 'sort-asc' : 'sort-desc');
                
                // Sort rows
                rows.sort((a, b) => {
                    let valueA, valueB;
                    
                    if (column === 'name') {
                        valueA = a.getAttribute('data-name');
                        valueB = b.getAttribute('data-name');
                        const result = valueA.localeCompare(valueB);
                        return currentSort.direction === 'asc' ? result : -result;
                    } else {
                        valueA = parseFloat(a.getAttribute(`data-${column}`)) || 0;
                        valueB = parseFloat(b.getAttribute(`data-${column}`)) || 0;
                        const result = valueA - valueB;
                        return currentSort.direction === 'asc' ? result : -result;
                    }
                });
                
                // Re-append sorted rows
                rows.forEach(row => tbody.appendChild(row));
                
                // Update row striping
                updateRowStriping();
            }
            
            function updateRowStriping() {
                const table = document.getElementById('highscoresTable');
                const rows = table.querySelectorAll('tr');
                
                // Start from index 2 to skip header rows
                for (let i = 2; i < rows.length; i++) {
                    const row = rows[i];
                    // Remove existing striping classes
                    row.style.background = '';
                    // Add new striping based on position
                    if ((i - 2) % 2 === 0) {
                        row.style.background = 'var(--row-even)';
                    } else {
                        row.style.background = 'var(--row-odd)';
                    }
                }
            }
            
            // Initialize
            document.addEventListener('DOMContentLoaded', function() {
                loadTheme();
                
                // Add click handlers to sortable headers
                document.querySelectorAll('th.sortable').forEach(header => {
                    header.addEventListener('click', function() {
                        const column = this.getAttribute('data-column');
                        sortTable(column);
                    });
                });
                
                // Initial sort by name
                sortTable('name');
            });
        </script>
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
        today_date = datetime.now().strftime("%Y-%m-%d")
    
    if yesterday_date is None:
        yesterday_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
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
    compare_and_generate_html(today_data, yesterday_data, report_file, today_date)
    
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

        today_str = datetime.now().strftime("%Y-%m-%d")
        today_file = save_csv(rows, today_str)

        yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        yesterday_file = os.path.join(SAVE_DIR, f"highscores_{yesterday_str}.csv")

        # Convert rows to dictionary format: {name: {experience}}
        today_dict = {}
        for row in rows:
            name, experience = row
            today_dict[name] = {
                'experience': experience
            }
        
        yesterday_dict = load_csv(yesterday_file)

        report_file = "index.html"
        compare_and_generate_html(today_dict, yesterday_dict, report_file, today_str)

        print("CSV snapshot saved:", today_file)
        print("HTML report saved:", report_file)

        git_success = git_commit_push(report_file, commit_message=f"Update index.html {datetime.now().strftime('%Y-%m-%d')}")
        
        # Print completion status for full scrape
        common_players = set(today_dict.keys()) & set(yesterday_dict.keys())
        changes_count = sum(1 for name in common_players if today_dict[name] != yesterday_dict[name])
        
        print(f"🎆 Dura Highscores Full Scrape Complete!")
        print(f"📅 Date: {today_str}")
        print(f"🔍 Scraped: {len(rows):,} players")
        print(f"👥 Compared: {len(common_players):,} players")
        print(f"📈 Changes detected: {changes_count:,}")
        print(f"💾 CSV saved: {today_file}")
        print(f"📝 HTML report saved: {report_file}")
        
        if git_success:
            print("✅ All operations completed successfully!")
        else:
            print("⚠️ Operations completed but git push may have failed")

