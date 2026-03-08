from flask import Blueprint

technician = Blueprint('technician', __name__)

@technician.route('/technician')
def technician_dashboard():
    return 'Technician dashboard - coming soon'
