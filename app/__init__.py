import os
from flask import Flask
import logging # Added for logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def create_app():
    app = Flask(__name__)

    # !!! IMPORTANT: Set a strong secret key for session management
    app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'your_very_secret_key_if_env_not_set') # Replace with a strong, random key in production

    # Load configuration from .env or config.py
    # For now, we'll keep it simple, you can expand config.py later
    # app.config.from_object('app.config.DevelopmentConfig') # Example if you add config.py

    # You might want to load environment variables here if not using python-dotenv's global load
    # app.config['API_KEY'] = os.getenv('API_KEY')
    # ... and so on for other API keys and IDs

    from .routes import main_bp
    app.register_blueprint(main_bp)

    return app 