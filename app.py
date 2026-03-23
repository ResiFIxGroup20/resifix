import os
from flask import Flask, redirect, url_for
from dotenv import load_dotenv
from routes.auth import auth
from routes.resident import resident
from routes.admin import admin
from routes.technician import technician
from database.db import init_db

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'resifix-dev-secret-change-in-production')

app.register_blueprint(auth)
app.register_blueprint(resident)
app.register_blueprint(admin)
app.register_blueprint(technician)

with app.app_context():
    init_db()

@app.route('/')
def index():
    return redirect(url_for('auth.login'))

@app.route('/seed-db-once')
def seed_db():
    from database.db import seed_data
    try:
        seed_data()
        return "Seed data inserted successfully! DELETE THIS ROUTE NOW.", 200
    except Exception as e:
        return f"Error: {e}", 500

if __name__ == '__main__':
    app.run(debug=True)