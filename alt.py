import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time

URL = "https://classic.dura-online.com/?online"
TARGET_NAME = "Nickz"

def fetch_online_players():
    r = requests.get(URL)
    soup = BeautifulSoup(r.text, "html.parser")
    tables = soup.find_all("table")
    if len(tables) < 2:
        return []
    player_table = tables[1]
    players = []
    for row in player_table.find_all("tr")[1:]:
        cols = row.find_all("td")
        if len(cols) == 3:
            name = cols[0].get_text(strip=True)
            level = cols[1].get_text(strip=True)
            vocation = cols[2].get_text(strip=True)
            players.append(name)
    return players

def log_players(players):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("online_log.csv", "a") as f:
        f.write(f"{timestamp}," + ",".join(players) + "\n")

while True:
    players = fetch_online_players()
    log_players(players)
    print(players)
    time.sleep(60)  # wait for 60 seconds before next run
