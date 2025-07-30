import csv
import gspread
from io import StringIO
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, request, render_template, session, redirect, url_for, flash, Response
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from datetime import datetime
import pytz

app = Flask(__name__)
app.secret_key = "super-secret-key"

# 🔐 Login Manager setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# Google Sheets Setup
SHEET_NAME = "PitchSmart Log"
USER_SHEET_TAB = "Users"

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
spreadsheet = client.open(SHEET_NAME)

# 🧾 Load users from the Google Sheet
def load_users():
    try:
        sheet = spreadsheet.worksheet(USER_SHEET_TAB)
        data = sheet.get_all_records()
        users = {}
        for row in data:
            users[row["username"].strip().lower()] = {
                "password": str(row["password"]),
                "sheet": row["sheet"]
            }
        return users
    except:
        return {}

# ✍️ Save new user to sheet
def save_user(username, password, sheet_tab_name):
    sheet = spreadsheet.worksheet(USER_SHEET_TAB)
    sheet.append_row([username, password, sheet_tab_name])

class User(UserMixin):
    def __init__(self, username):
        self.id = username

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"].strip().lower()
        password = request.form["password"].strip()
        users = load_users()

        if username in users:
            return render_template("user_exists.html", username=username)

        sheet_tab = f"{username}_Sheet"
        spreadsheet.add_worksheet(title=sheet_tab, rows="100", cols="20")
        header = ["Player", "Age", "Pitches", "Days Rest", "Risk", "BMI", "Timestamp"]
        spreadsheet.worksheet(sheet_tab).append_row(header)
        save_user(username, password, sheet_tab)
        return redirect(url_for("login"))

    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if "guest" in request.form:
            session["guest"] = True
            return redirect(url_for("home"))
        else:
            username = request.form["username"].strip().lower()
            password = request.form["password"].strip()
            users = load_users()
            if username in users and users[username]["password"] == password:
                login_user(User(username))
                session.pop("guest", None)
                return redirect(url_for("home"))
            return render_template("invalid.html")
    return render_template("login.html")

@app.route("/check-username")
def check_username():
    username = request.args.get("username", "").strip().lower()
    users = load_users()
    return {"exists": username in users}

@app.route("/logout")
def logout():
    logout_user()
    session.pop("guest", None)
    return redirect(url_for("login"))

# 🧠 Risk calculator with recommendation
def calculate_risk(pitches, days_rest, age, height_in, weight_lb):
    max_pitches = 95 if age > 14 else 75
    fatigue_score = (pitches / max_pitches) * (1 if days_rest < 2 else 0.7)
    bmi = (weight_lb / (height_in ** 2)) * 703

    if bmi < 18.5 or bmi > 25:
        fatigue_score *= 1.1

    if fatigue_score > 0.9:
        risk = "High"
        recommendation = (
            "🚨 High Risk: Rest 3–4 days. No throwing. Ice arm, stretch, and consult a sports therapist."
        )
    elif fatigue_score > 0.6:
        risk = "Medium"
        recommendation = (
            "⚠️ Medium Risk: Avoid intense throwing. Rest 2 days. Hydrate and use recovery bands."
        )
    else:
        risk = "Low"
        recommendation = (
            "✅ Low Risk: Keep regular warm-ups and monitor pitch count."
        )

    return risk, round(bmi, 1), recommendation

# 📤 Send to sheet
def send_to_sheet(sheet_name, data_row):
    ws = spreadsheet.worksheet(sheet_name)
    ws.append_row(data_row)

@app.route('/', methods=['GET', 'POST'])
def home():
    risk_level = None
    player_name = None
    bmi = None
    recommendation = None

    if request.method == 'POST':
        try:
            player_name = request.form['player_name']
            age = int(request.form['age'])
            pitches = int(request.form['num_pitches'])
            days_rest = int(request.form['days_rest'])
            height_in = float(request.form['height'])
            weight_lb = float(request.form['weight'])

            risk_level, bmi, recommendation = calculate_risk(pitches, days_rest, age, height_in, weight_lb)
            timestamp = datetime.now(pytz.timezone("America/Los_Angeles")).strftime("%b %d, %Y %I:%M %p")

            if current_user.is_authenticated:
                users = load_users()
                sheet_name = users[current_user.id]["sheet"]
                send_to_sheet(sheet_name, [player_name, age, pitches, days_rest, risk_level, bmi, timestamp])
        except ValueError:
            risk_level = "Invalid input. Please enter numbers only."

    return render_template('index.html', risk=risk_level, player=player_name, bmi=bmi, pitches=[], tip=recommendation)

@app.route('/history')
@login_required
def history():
    users = load_users()
    sheet_name = users[current_user.id]["sheet"]
    sheet = spreadsheet.worksheet(sheet_name)
    records = sheet.get_all_records()
    recent_20 = records[-20:] if len(records) >= 20 else records
    return render_template("history.html", records=recent_20)

@app.route('/export')
@login_required
def export_csv():
    users = load_users()
    sheet_name = users[current_user.id]["sheet"]
    sheet = spreadsheet.worksheet(sheet_name)
    records = sheet.get_all_records()
    recent_20 = records[-20:] if len(records) >= 20 else records

    # Create a CSV in memory
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=recent_20[0].keys())
    writer.writeheader()
    writer.writerows(recent_20)

    filename = f"{current_user.id}_pitchsmart_history.csv"

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=81)
