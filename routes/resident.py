from flask import Blueprint

resident = Blueprint('resident', __name__)

@resident.route('/dashboard')
def dashboard():
    return 'Resident dashboard - coming soon'

@resident.route('/request/new')
def new_request():
    return 'New request form - coming soon'

@resident.route('/notifications')
def notifications():
    return 'Notifications - coming soon'
