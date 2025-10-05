import os
import csv
from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)  # Enable CORS for GitHub Pages

SAVE_DIR = "snapshots"

def get_all_available_snapshots():
    """Get all available snapshot dates sorted from oldest to newest"""
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
    
    # Sort from oldest to newest
    snapshot_files.sort()
    return snapshot_files

def load_csv(filepath):
    """Load CSV data into a dictionary with name as key and experience as value"""
    data = {}
    if not os.path.exists(filepath):
        return data
    
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            data[row["Name"]] = int(row["Experience"].replace(",", ""))
    return data

@app.route('/player_history', methods=['GET'])
def player_history():
    """Get historical experience data for a specific player"""
    player_name = request.args.get('name', '').strip()
    
    if not player_name:
        return jsonify({'error': 'Player name is required'}), 400
    
    # Get all available snapshots
    snapshots = get_all_available_snapshots()
    
    if not snapshots:
        return jsonify({'error': 'No snapshot data available'}), 404
    
    # Collect player data across all snapshots
    history_data = []
    
    for snapshot_date in snapshots:
        filepath = os.path.join(SAVE_DIR, f"highscores_{snapshot_date}.csv")
        data = load_csv(filepath)
        
        if player_name in data:
            history_data.append({
                'date': snapshot_date,
                'experience': data[player_name]
            })
    
    if not history_data:
        return jsonify({'error': f'Player "{player_name}" not found in any snapshots'}), 404
    
    return jsonify({
        'player': player_name,
        'history': history_data
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
