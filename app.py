from flask import Flask
from routes.auth import auth
from routes.resident import resident
from routes.admin import admin
from routes.technician import technician
from database.db import init_db

app = Flask(__name__)
app.secret_key = 'resifix_secret_key'

app.register_blueprint(auth)
app.register_blueprint(resident)
app.register_blueprint(admin)
app.register_blueprint(technician)

with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(debug=True)
