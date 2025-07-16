from flask import Flask, request, render_template

app = Flask(__name__)

# 🧠 Injury risk calculator
def calculate_risk(pitches, days_rest, age):
    max_pitches = 95 if age > 14 else 75
    fatigue_score = (pitches / max_pitches) * (1 if days_rest < 2 else 0.7)

    if fatigue_score > 0.9:
        return "High"
    elif fatigue_score > 0.6:
        return "Medium"
    else:
        return "Low"

# 🏠 Home route
@app.route('/', methods=['GET', 'POST'])
def home():
    risk_level = None
    if request.method == 'POST':
        try:
            player = request.form['player']
            age = int(request.form['age'])
            pitches = int(request.form['pitches'])
            days_rest = int(request.form['days_rest'])

            # Calculate injury risk
            risk_level = calculate_risk(pitches, days_rest, age)

        except ValueError:
            risk_level = "Invalid input. Please enter numbers only."

    return render_template('index.html', risk=risk_level)

# 🚀 Run app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=81)