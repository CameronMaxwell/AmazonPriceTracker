# scraper.py

from flask import current_app
import requests

def scrape_amazon_info(product_url):
    api_key = current_app.config['SCRAPERAPI_KEY']
    payload = {
        'api_key': api_key,
        'url': product_url,
        'autoparse': 'true',
        'output_format': 'json'
    }

    try:
        response = requests.get('https://api.scraperapi.com/', params=payload)
        response.raise_for_status()
        data = response.json()

        # Extract relevant information (name and price)
        product_name = data.get('name', 'Unknown Product')
        product_price = data.get('pricing', 'N/A')

        return product_name, product_price

    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch the data. Error: {str(e)}")
        return None, None