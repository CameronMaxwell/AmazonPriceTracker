# api/app.py

from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
from werkzeug.security import generate_password_hash, check_password_hash
from api.scheduler import start_price_check_scheduler
from api.scraper import scrape_amazon_info
from api.models import db, User, Product, PriceHistory
from datetime import datetime
from dotenv import load_dotenv
import pytz  # Import pytz for timezone support
import os

load_dotenv()
# Initialize Flask application
app = Flask(__name__, instance_relative_config=True)
app.config.from_mapping(
    SECRET_KEY=os.getenv('SECRET_KEY', 'dev'),  # Replace with a secure key
    SQLALCHEMY_DATABASE_URI='sqlite:///../instance/database.db',  # Adjusted path
    SCRAPERAPI_KEY=os.getenv('SCRAPERAPI_KEY')  # Use environment variable
)

# Initialize extensions
db.init_app(app)
CORS(app)  # Enable CORS for all routes

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Redirect to 'login' for @login_required
login_manager.login_message_category = 'info'

# Define the EST timezone using pytz
est = pytz.timezone('America/New_York')

# User loader callback for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Flask-WTF Forms
class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=150)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=150)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')

    # Custom validators to ensure unique username and email
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already exists. Please choose a different one.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered. Please log in or use a different email.')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=150)])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Log In')

# Routes

@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('view_products'))
    form = LoginForm()
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('view_products'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = generate_password_hash(form.password.data)
        new_user = User(
            username=form.username.data,
            email=form.email.data,
            password=hashed_password
        )
        db.session.add(new_user)
        db.session.commit()
        flash('Your account has been created! You can now log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('view_products'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            flash('You have been logged in!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('view_products'))
        else:
            flash('Login Unsuccessful. Please check email and password.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

@app.route('/index')
@login_required
def index():
    return render_template('index.html')

@app.route('/delete_product/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    product = Product.query.filter_by(id=product_id, user_id=current_user.id).first()

    if product:
        # Delete related price history entries first
        PriceHistory.query.filter_by(product_id=product.id).delete()
        db.session.delete(product)
        db.session.commit()
        flash('Product deleted successfully.', 'success')
    else:
        flash('Product not found or you don’t have permission to delete it.', 'danger')

    return redirect(url_for('view_products'))

# Modify the scrape route to require login
@app.route('/scrape', methods=['GET', 'POST'])
@login_required
def scrape():
    print(f"Received {request.method} request at /scrape")  # Debug print
    print(f"Request headers: {request.headers}")  # Debug print
    if request.method == 'POST':
        data = request.get_json()
        print(f"Received data: {data}")  # Debug print
        if not data or 'url' not in data:
            print("No URL provided in POST data.")  # Debug print
            return jsonify({'success': False, 'message': 'No URL provided.'}), 400
        product_url = data.get('url')
        print(f"Received URL via POST: {product_url}")  # Debug print
    else:
        product_url = request.args.get('url')
        print(f"Received URL via GET: {product_url}")  # Debug print

    if product_url:
        try:
            product_name, product_price = scrape_amazon_info(product_url)
            print(f"Scraped Name: {product_name}, Price: {product_price}")  # Debug print
        except Exception as e:
            print(f"Error during scraping: {e}")  # Debug print
            if request.method == 'POST':
                return jsonify({'success': False, 'message': 'Failed to scrape product information.'}), 500
            else:
                flash('Failed to scrape product information.', 'danger')
                return render_template('products.html')

        if product_name and product_price:
            # Parse the price to a float
            try:
                # Remove currency symbols and commas
                price_cleaned = ''.join(c for c in product_price if c.isdigit() or c == '.')
                product_price_float = float(price_cleaned)
                print(f"Parsed Price: {product_price_float}")  # Debug print
            except ValueError:
                print("Could not parse the price.")  # Debug print
                if request.method == 'POST':
                    return jsonify({'success': False, 'message': 'Could not parse the price.'}), 500
                else:
                    flash('Could not parse the price.', 'danger')
                    return render_template('products.html')

            # Check if the product already exists for the current user
            existing_product = Product.query.filter_by(url=product_url, user_id=current_user.id).first()
            if existing_product:
                # Update the existing product
                existing_product.name = product_name
                existing_product.price = product_price_float
                db.session.commit()
                print(f"Updated product ID {existing_product.id}")  # Debug print
            else:
                # Create a new product
                new_product = Product(
                    name=product_name,
                    price=product_price_float,
                    url=product_url,
                    created_at=datetime.now(est),
                    owner=current_user  # Associate with current user
                )
                db.session.add(new_product)
                db.session.commit()
                existing_product = new_product
                print(f"Created new product ID {existing_product.id}")  # Debug print

            # Add a new price history entry
            price_history = PriceHistory(
                product_id=existing_product.id,
                price=product_price_float,
                timestamp=datetime.now(est)
            )
            db.session.add(price_history)
            db.session.commit()
            print(f"Added price history ID {price_history.id}")  # Debug print

            if request.method == 'POST':
                # Return JSON response for API calls
                return jsonify({'success': True, 'message': 'Product added successfully.'}), 200
            else:
                # Redirect to the products page after GET request
                flash('Product added successfully.', 'success')
                return redirect(url_for('view_products'))
        else:
            print("Failed to scrape product information.")  # Debug print
            if request.method == 'POST':
                return jsonify({'success': False, 'message': 'Failed to scrape product information.'}), 500
            else:
                flash('Failed to scrape product information.', 'danger')
                return render_template('products.html')
    else:
        print("No URL provided.")  # Debug print
        if request.method == 'POST':
            return jsonify({'success': False, 'message': 'Please provide a valid Amazon product URL.'}), 400
        else:
            flash('Please provide a valid Amazon product URL.', 'warning')
            return render_template('products.html')

# Optional: Route to view stored products
@app.route('/products', methods=['GET'])
@login_required
def view_products():
    products = Product.query.filter_by(user_id=current_user.id).all()
    return render_template('products.html', products=products)


if __name__ == '__main__':
    with app.app_context():
        print("Inside app context.")
        try:
            db.create_all()
            print("Database tables created.")
        except Exception as e:
            print(f"Error creating tables: {e}")
        start_price_check_scheduler(app)
    app.run(debug=True, port=5000, use_reloader=False)