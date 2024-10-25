import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.app import app  # Import the Flask app
from api.models import db, Product, PriceHistory  # Import db and models

print(f"Using database: {app.config['SQLALCHEMY_DATABASE_URI']}")

try:
    with app.app_context():
        print("Inside app context.")
        db.create_all()  # Create all the tables
        print("Database tables created.")
except Exception as e:
    print(f"Error creating tables: {e}")