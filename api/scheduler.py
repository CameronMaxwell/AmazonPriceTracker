# scheduler.py

from flask import current_app
from apscheduler.schedulers.background import BackgroundScheduler
from api.models import db, Product, PriceHistory
from api.scraper import scrape_amazon_info
from datetime import datetime
import pytz  # Import pytz for timezone support

# Define the EST timezone
est = pytz.timezone('America/New_York')

def check_prices(app):
    with app.app_context():
        # Fetch all products from the database
        products = Product.query.all()
        for product in products:
            # Scrape the latest price
            product_name, product_price = scrape_amazon_info(product.url)
            if product_price:
                try:
                    # Remove currency symbols and commas
                    price_cleaned = ''.join(c for c in product_price if c.isdigit() or c == '.')
                    product_price_float = float(price_cleaned)
                except ValueError:
                    continue  # Skip if price cannot be parsed
                
                # Update the product's price
                product.price = product_price_float

                # Add a new entry to PriceHistory with EST timestamp
                price_history = PriceHistory(
                    product_id=product.id,
                    price=product_price_float,
                    timestamp=datetime.now(est)  
                )
                db.session.add(price_history)
        db.session.commit()

# Check price of item every week
def start_price_check_scheduler(app):
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=check_prices, args=[app], trigger="interval", hours=168)
    scheduler.start()