from flask import Flask, render_template_string, request
import csv

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Online Character Analyzer</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        input[type=text] { padding: 5px; width: 200px; }
        input[type=submit] { padding: 5px 10px; }
        ul { margin-top: 20px; }
    </style>
</head>
<body>
    <h2>Online Character Analyzer</h2>
    <form method="post">
        <label for="charname">Enter character name:</label>
        <input type="text" id="charname" name="charname" required>
        <input type="submit" value="Analyze">
    </form>
    {% if result %}
        <h3>Characters who have never been online at the same time as <b>{{ charname }}</b>:</h3>
        <ul>
        {% for name in result %}
            <li>{{ name }}</li>
        {% endfor %}
        </ul>
    {% endif %}
</body>
</html>
"""

def load_online_log(filename="online_log.csv"):
    sessions = []
    try:
        with open(filename, newline='') as f:
            reader = csv.reader(f)
            for row in reader:
                timestamp = row[0]
                players = row[1:]
                sessions.append((timestamp, players))
    except FileNotFoundError:
        pass
    return sessions

def get_never_online_with(target_name, filename="online_log.csv"):
    sessions = load_online_log(filename)
    all_players = set()
    online_with_target = set()
    for timestamp, players in sessions:
        all_players.update(players)
        if target_name in players:
            online_with_target.update(players)
    never_online_with = all_players - online_with_target
    never_online_with.discard(target_name)
    return sorted(never_online_with)

@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    charname = ""
    if request.method == "POST":
        charname = request.form.get("charname", "").strip()
        if charname:
            result = get_never_online_with(charname)
    return render_template_string(HTML, result=result, charname=charname)

if __name__ == "__main__":
    app.run(debug=True)
