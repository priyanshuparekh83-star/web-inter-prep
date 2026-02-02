"""
Configuration file for Mock Interview Application
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Base configuration class"""
    
    # API Keys
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', 'AIzaSyDhj5eznHfo9Dt80Ptvm_pi-LVqd_2i8oc')
    
    # Flask Configuration
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-here-change-in-production')
    
    # Database Configuration
    if os.environ.get('RENDER'):
        # Production database URL from Render
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    else:
        # Local database URL - using SQLite for easier setup
        SQLALCHEMY_DATABASE_URI = 'sqlite:///interview_prep.db'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # File Upload Configuration
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
    PROFILE_PHOTOS_FOLDER = os.path.join(os.getcwd(), 'static', 'profile_photos')
    ALLOWED_EXTENSIONS = {'wav', 'mp3', 'ogg', 'm4a'}
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    
    # Rate Limiting Configuration
    API_RATE_LIMIT_DELAY = 1  # seconds between API calls
    MAX_RETRIES = 3  # maximum retries for API calls
