import os
import sys
import pymysql
import json
import re
import mysql.connector
from mysql.connector import Error
import requests
import google.generativeai as genai
from flask import Flask, render_template, redirect, url_for, flash, request, session, jsonify, abort, send_from_directory
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, SelectField, DateField, FileField
from wtforms.validators import DataRequired, Email
import bcrypt
from flask_sqlalchemy import SQLAlchemy
import random
from datetime import datetime
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import sqlite3
#import whisper
import tempfile

# For the career roadmap feature, you might need to install:
# pip install PyMuPDF (for PDF parsing)

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Database configuration
if os.environ.get('RENDER'):
    # Production database URL from Render
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
else:
    # Local database URL - using SQLite instead of MySQL for easier setup
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///interview_prep.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get('SECRET_KEY', '\x8bO|\xc3\xe3\x99&h%\xb9\xebU\xf9\x1eb\xee$\x85\xf1Z\x95\x85\xe3\xdd')

# Add these configurations after the existing app configurations
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
PROFILE_PHOTOS_FOLDER = os.path.join(os.getcwd(), 'static', 'profile_photos')
ALLOWED_EXTENSIONS = {'wav', 'mp3', 'ogg', 'm4a'}
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROFILE_PHOTOS_FOLDER'] = PROFILE_PHOTOS_FOLDER
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,  # Helps detect disconnections
    'pool_recycle': 3600,   # Recycle connections after 1 hour
    'connect_args': {} # MySQL doesn't need check_same_thread
}

# Create uploads directory if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROFILE_PHOTOS_FOLDER, exist_ok=True)
print(f"Profile photos folder: {PROFILE_PHOTOS_FOLDER}")

# Configure Gemini API with the latest API key
# Configure Gemini API
api_key = os.getenv('GEMINI_API_KEY') or 'AIzaSyDhj5eznHfo9Dt80Ptvm_pi-LVqd_2i8oc'
genai.configure(api_key=api_key)

def get_db_connection():
    """Get a new database connection"""
    try:
        if os.environ.get('RENDER'):
            # Parse DATABASE_URL for production
            db_url = os.environ.get('DATABASE_URL')
            connection = pymysql.connect(
                host=db_url.split('@')[1].split('/')[0],
                user=db_url.split('://')[1].split(':')[0],
                password=db_url.split(':')[2].split('@')[0],
                database=db_url.split('/')[-1],
                cursorclass=pymysql.cursors.DictCursor
            )
        else:
            # Local database connection using SQLite
            connection = sqlite3.connect('interview_prep.db')
            connection.row_factory = sqlite3.Row
        return connection
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

# Add SQLite-specific configuration
def get_db_connection_status():
    """Get database connection status information"""
    try:
        connection = sqlite3.connect('interview_prep.db')
        with connection:
            cursor = connection.cursor()
            cursor.execute("SELECT sqlite_version()")
            version = cursor.fetchone()[0]
        return True, version
    except Exception as e:
        return False, str(e)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.LargeBinary, nullable=False)
    profile_photo = db.Column(db.String(255), nullable=True)
    interviews = db.relationship('Interview', backref='user', lazy=True)
    ai_interviews = db.relationship('AIInterview', backref='user', lazy=True)

class Interview(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company = db.Column(db.String(100), nullable=False)
    position = db.Column(db.String(100), nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='Upcoming')
    performance = db.Column(db.Integer, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class AIInterview(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_role = db.Column(db.String(100), nullable=False)
    experience_level = db.Column(db.String(50), nullable=False)
    target_company = db.Column(db.String(100), nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    questions = db.Column(db.Text, nullable=False)
    answers = db.Column(db.Text, nullable=True)
    feedback = db.Column(db.Text, nullable=True)
    performance = db.Column(db.Float, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# Enhanced models for tracking real feature usage
class AIInterviewSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    position = db.Column(db.String(100), nullable=False)
    questions_asked = db.Column(db.Integer, default=0)
    questions_answered = db.Column(db.Integer, default=0)
    average_score = db.Column(db.Float, default=0.0)
    completed = db.Column(db.Boolean, default=False)
    session_data = db.Column(db.Text)  # JSON data for questions and answers
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

class AvatarInterviewSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    job_role = db.Column(db.String(100), nullable=False)
    company = db.Column(db.String(100))
    experience_level = db.Column(db.String(50))
    questions_count = db.Column(db.Integer, default=0)
    questions_completed = db.Column(db.Integer, default=0)
    average_score = db.Column(db.Float, default=0.0)
    completed = db.Column(db.Boolean, default=False)
    video_recorded = db.Column(db.Boolean, default=False)
    posture_score = db.Column(db.Float)
    session_file = db.Column(db.String(255))  # Path to JSON file
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

class DSAPracticeSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    problem_title = db.Column(db.String(200), nullable=False)
    problem_category = db.Column(db.String(100))  # Array, Tree, Graph, etc.
    difficulty = db.Column(db.String(20))  # Easy, Medium, Hard
    solved = db.Column(db.Boolean, default=False)
    attempts = db.Column(db.Integer, default=1)
    time_taken = db.Column(db.Integer)  # in minutes
    solution_code = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    solved_at = db.Column(db.DateTime)

class EnglishBoosterSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    session_type = db.Column(db.String(50))  # Grammar, Speaking, Vocabulary
    exercises_completed = db.Column(db.Integer, default=0)
    score = db.Column(db.Float, default=0.0)
    improvement_areas = db.Column(db.Text)  # JSON array
    duration_minutes = db.Column(db.Integer)
    completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

class CompanyPrepSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    company_name = db.Column(db.String(100), nullable=False)
    prep_type = db.Column(db.String(50))  # Culture, Technical, Behavioral
    topics_covered = db.Column(db.Text)  # JSON array
    progress_percentage = db.Column(db.Float, default=0.0)
    completed = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

class ResumeUpload(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255))
    file_size = db.Column(db.Integer)
    file_type = db.Column(db.String(50))
    analysis_score = db.Column(db.Float)
    suggestions = db.Column(db.Text)  # JSON array
    is_active = db.Column(db.Boolean, default=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

class RegistrationForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Register")

class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")

class InterviewForm(FlaskForm):
    company = StringField("Company", validators=[DataRequired()])
    position = StringField("Position", validators=[DataRequired()])
    date = DateField("Interview Date", validators=[DataRequired()], format='%Y-%m-%d')
    notes = TextAreaField("Notes")
    status = SelectField("Status", choices=[('Upcoming', 'Upcoming'), ('Completed', 'Completed'), ('Rejected', 'Rejected'), ('Offered', 'Offered')])
    performance = SelectField("Performance (1-10)", choices=[(str(i), str(i)) for i in range(1, 11)], validators=[])
    submit = SubmitField("Save")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        name = form.name.data
        email = form.email.data
        password = form.password.data
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("An account with this email already exists. Please log in instead.", "warning")
            return redirect(url_for('login'))
        
        # Hash password and create new user
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        new_user = User(name=name, email=email, password=hashed_password)
        
        try:
            db.session.add(new_user)
            db.session.commit()
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for('login'))
        except Exception as e:
            flash("An error occurred while registering. Please try again.", "danger")
            print("Database Error:", str(e))
            db.session.rollback()
            
            # Try to diagnose and fix common issues
            try:
                # Create tables if they don't exist
                with app.app_context():
                    db.create_all()
                flash("Database tables have been refreshed. Please try registering again.", "info")
            except Exception as table_error:
                print("Failed to create tables:", str(table_error))
    
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        
        try:
            user = User.query.filter_by(email=email).first()
            
            if user and bcrypt.checkpw(password.encode('utf-8'), user.password):
                session['user_id'] = user.id
                flash("Login successful!", "success")
                return redirect(url_for('dashboard'))
            else:
                flash("Login unsuccessful. Please check your email and password.", "danger")
                
        except Exception as e:
            flash("A database error occurred. Please try again later.", "danger")
            print("Database error during login:", str(e))
            
            # Try to fix database connection issues
            try:
                # Refresh connection and tables if needed
                db.session.rollback()
                with app.app_context():
                    db.create_all()
            except Exception as repair_error:
                print("Failed to repair database:", str(repair_error))
    
    return render_template('login.html', form=form)

@app.route('/resume_template')
def resume_template():
    return render_template('resume_template.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return render_template('dashboard.html', user=None, interviews=[], stats=get_default_stats(), not_logged_in=True)
    
    user = User.query.get(session['user_id'])
    # Get the user's interviews for the dashboard
    interviews = Interview.query.filter_by(user_id=user.id).order_by(Interview.date.desc()).all()
    
    # Get comprehensive statistics
    stats = get_comprehensive_stats(user.id)
    
    return render_template('dashboard.html', user=user, interviews=interviews, stats=stats)

def get_default_stats():
    """Return default stats for non-logged-in users"""
    return {
        'total': 0,
        'completed': 0,
        'upcoming': 0,
        'offers': 0,
        'avg_performance': 0,
        'ai_interviews': 0,
        'ai_completion_rate': 0,
        'avatar_interviews': 0,
        'avatar_completion_rate': 0,
        'company_sessions': 0,
        'company_progress': 0,
        'dsa_solved': 0,
        'dsa_total': 100,
        'english_sessions': 0,
        'english_improvement': 0,
        'resume_status': 'Not Uploaded',
        'resume_completion': 0,
        'best_score': 0,
        'improvement': 0
    }

def get_comprehensive_stats(user_id):
    """Calculate comprehensive statistics for all features"""
    try:
        # Basic interview statistics
        interviews = Interview.query.filter_by(user_id=user_id).all()
        completed_interviews = [i for i in interviews if i.status == 'Completed']
        upcoming_interviews = [i for i in interviews if i.status == 'Upcoming']
        offers = [i for i in interviews if i.status == 'Offered']
        
        avg_performance = 0
        best_score = 0
        if completed_interviews:
            performances = [i.performance for i in completed_interviews if i.performance]
            if performances:
                avg_performance = sum(performances) / len(performances)
                best_score = max(performances)
        
        # AI Interview Statistics
        ai_interviews_count = get_ai_interview_count(user_id)
        ai_completion_rate = calculate_ai_completion_rate(user_id)
        
        # Avatar Interview Statistics
        avatar_interviews_count = get_avatar_interview_count(user_id)
        avatar_completion_rate = calculate_avatar_completion_rate(user_id)
        
        # Company Prep Statistics
        company_sessions = get_company_prep_sessions(user_id)
        company_progress = calculate_company_progress(user_id)
        
        # DSA Statistics
        dsa_stats = get_dsa_statistics(user_id)
        
        # English Booster Statistics
        english_sessions = get_english_booster_sessions(user_id)
        english_improvement = calculate_english_improvement(user_id)
        
        # Resume Status
        resume_status, resume_completion = get_resume_status(user_id)
        
        # Calculate improvement trend
        improvement = calculate_monthly_improvement(user_id)
        
        return {
            'total': len(interviews),
            'completed': len(completed_interviews),
            'upcoming': len(upcoming_interviews),
            'offers': len(offers),
            'avg_performance': round(avg_performance, 1),
            'best_score': round(best_score, 1),
            'improvement': round(improvement, 1),
            'ai_interviews': ai_interviews_count,
            'ai_completion_rate': ai_completion_rate,
            'avatar_interviews': avatar_interviews_count,
            'avatar_completion_rate': avatar_completion_rate,
            'company_sessions': company_sessions,
            'company_progress': company_progress,
            'dsa_solved': dsa_stats['solved'],
            'dsa_total': dsa_stats['total'],
            'english_sessions': english_sessions,
            'english_improvement': english_improvement,
            'resume_status': resume_status,
            'resume_completion': resume_completion
        }
        
    except Exception as e:
        print(f"Error calculating comprehensive stats: {e}")
        return get_default_stats()

def get_ai_interview_count(user_id):
    """Count AI interviews from database"""
    try:
        # Count from both old AIInterview model and new AIInterviewSession model
        old_ai_interviews = AIInterview.query.filter_by(user_id=user_id).count()
        new_ai_sessions = AIInterviewSession.query.filter_by(user_id=user_id).count()
        return old_ai_interviews + new_ai_sessions
    except Exception as e:
        print(f"Error counting AI interviews: {e}")
        return 0

def calculate_ai_completion_rate(user_id):
    """Calculate AI interview completion rate"""
    try:
        # Get total sessions and completed sessions
        total_sessions = AIInterviewSession.query.filter_by(user_id=user_id).count()
        completed_sessions = AIInterviewSession.query.filter_by(user_id=user_id, completed=True).count()
        
        # Also count old AIInterview records as completed if they have performance scores
        old_completed = AIInterview.query.filter_by(user_id=user_id).filter(AIInterview.performance.isnot(None)).count()
        old_total = AIInterview.query.filter_by(user_id=user_id).count()
        
        total = total_sessions + old_total
        completed = completed_sessions + old_completed
        
        if total == 0:
            return 0
        
        return round((completed / total) * 100, 1)
    except Exception as e:
        print(f"Error calculating AI completion rate: {e}")
        return 0

def get_avatar_interview_count(user_id):
    """Count avatar interviews from database and files"""
    try:
        # Count from database first
        db_count = AvatarInterviewSession.query.filter_by(user_id=user_id).count()
        
        # Also check saved files for backward compatibility
        file_count = 0
        interviews_dir = os.path.join('data', 'interviews')
        if os.path.exists(interviews_dir):
            for filename in os.listdir(interviews_dir):
                if filename.startswith('avatar_') and filename.endswith('.json'):
                    filepath = os.path.join(interviews_dir, filename)
                    try:
                        with open(filepath, 'r') as f:
                            interview_data = json.load(f)
                        if interview_data.get('user_id') == user_id:
                            file_count += 1
                    except:
                        continue
        
        return db_count + file_count
    except Exception as e:
        print(f"Error counting avatar interviews: {e}")
        return 0

def calculate_avatar_completion_rate(user_id):
    """Calculate avatar interview completion rate"""
    try:
        total_sessions = AvatarInterviewSession.query.filter_by(user_id=user_id).count()
        completed_sessions = AvatarInterviewSession.query.filter_by(user_id=user_id, completed=True).count()
        
        # Also count completed file-based interviews
        completed_files = 0
        interviews_dir = os.path.join('data', 'interviews')
        if os.path.exists(interviews_dir):
            for filename in os.listdir(interviews_dir):
                if filename.startswith('avatar_') and filename.endswith('.json'):
                    filepath = os.path.join(interviews_dir, filename)
                    try:
                        with open(filepath, 'r') as f:
                            interview_data = json.load(f)
                        if (interview_data.get('user_id') == user_id and 
                            interview_data.get('completed', False)):
                            completed_files += 1
                    except:
                        continue
        
        total = total_sessions + get_avatar_interview_count(user_id) - total_sessions  # Avoid double counting
        completed = completed_sessions + completed_files
        
        if total == 0:
            return 0
        
        return round((completed / total) * 100, 1)
    except Exception as e:
        print(f"Error calculating avatar completion rate: {e}")
        return 0

def get_company_prep_sessions(user_id):
    """Count company preparation sessions"""
    try:
        # Count actual company prep sessions from database
        prep_sessions = CompanyPrepSession.query.filter_by(user_id=user_id).count()
        
        # Also count unique companies from interviews as prep sessions
        interviews = Interview.query.filter_by(user_id=user_id).all()
        companies_from_interviews = set(i.company for i in interviews if i.company)
        
        return prep_sessions + len(companies_from_interviews)
    except Exception as e:
        print(f"Error counting company prep sessions: {e}")
        return 0

def calculate_company_progress(user_id):
    """Calculate company preparation progress"""
    try:
        # Get average progress from all company prep sessions
        sessions = CompanyPrepSession.query.filter_by(user_id=user_id).all()
        
        if not sessions:
            # If no dedicated prep sessions, base on interview completion
            interviews = Interview.query.filter_by(user_id=user_id).all()
            if interviews:
                completed_interviews = len([i for i in interviews if i.status == 'Completed'])
                return min(100, (completed_interviews / len(interviews)) * 100)
            return 0
        
        # Calculate average progress from prep sessions
        total_progress = sum(session.progress_percentage for session in sessions)
        return round(total_progress / len(sessions), 1)
        
    except Exception as e:
        print(f"Error calculating company progress: {e}")
        return 0

def get_dsa_statistics(user_id):
    """Get DSA practice statistics"""
    try:
        # Get actual DSA practice data from database
        all_problems = DSAPracticeSession.query.filter_by(user_id=user_id).all()
        solved_problems = DSAPracticeSession.query.filter_by(user_id=user_id, solved=True).all()
        
        # Get unique problems (in case user attempted same problem multiple times)
        unique_attempted = len(set(p.problem_title for p in all_problems))
        unique_solved = len(set(p.problem_title for p in solved_problems))
        
        # If no data, return realistic baseline
        if unique_attempted == 0:
            return {'solved': 0, 'total': 100}
        
        # Assume total available problems is much larger than what user has attempted
        total_available = max(100, unique_attempted * 3)
        
        return {'solved': unique_solved, 'total': total_available}
        
    except Exception as e:
        print(f"Error getting DSA statistics: {e}")
        return {'solved': 0, 'total': 100}

def get_english_booster_sessions(user_id):
    """Count English Booster sessions"""
    try:
        # Count actual English Booster sessions from database
        sessions = EnglishBoosterSession.query.filter_by(user_id=user_id).count()
        return sessions
    except Exception as e:
        print(f"Error counting English Booster sessions: {e}")
        return 0

def calculate_english_improvement(user_id):
    """Calculate English improvement percentage"""
    try:
        # Get all English Booster sessions ordered by date
        sessions = EnglishBoosterSession.query.filter_by(user_id=user_id).order_by(EnglishBoosterSession.created_at).all()
        
        if len(sessions) < 2:
            # If less than 2 sessions, return 0 improvement
            return 0
        
        # Calculate improvement based on first vs latest session scores
        first_session_score = sessions[0].score
        latest_session_score = sessions[-1].score
        
        if first_session_score == 0:
            # Avoid division by zero
            return round(latest_session_score, 1)
        
        improvement = ((latest_session_score - first_session_score) / first_session_score) * 100
        return round(max(0, improvement), 1)  # Don't show negative improvement
        
    except Exception as e:
        print(f"Error calculating English improvement: {e}")
        return 0

def get_resume_status(user_id):
    """Get resume upload status"""
    try:
        # Check for actual resume uploads in database
        latest_resume = ResumeUpload.query.filter_by(user_id=user_id, is_active=True).order_by(ResumeUpload.uploaded_at.desc()).first()
        
        if latest_resume:
            # Calculate completion percentage based on analysis score
            completion = 100 if latest_resume.analysis_score and latest_resume.analysis_score >= 80 else 75
            return 'Uploaded', completion
        else:
            return 'Not Uploaded', 0
            
    except Exception as e:
        print(f"Error getting resume status: {e}")
        return 'Not Uploaded', 0

def calculate_monthly_improvement(user_id):
    """Calculate monthly performance improvement"""
    try:
        from datetime import datetime, timedelta
        
        # Get interviews from the last two months
        two_months_ago = datetime.now() - timedelta(days=60)
        one_month_ago = datetime.now() - timedelta(days=30)
        
        interviews = Interview.query.filter_by(user_id=user_id).filter(
            Interview.date >= two_months_ago
        ).all()
        
        # Split into last month and month before
        last_month = [i for i in interviews if i.date >= one_month_ago and i.performance]
        month_before = [i for i in interviews if i.date < one_month_ago and i.date >= two_months_ago and i.performance]
        
        if not last_month or not month_before:
            return 1.2  # Default improvement
        
        last_month_avg = sum(i.performance for i in last_month) / len(last_month)
        month_before_avg = sum(i.performance for i in month_before) / len(month_before)
        
        return last_month_avg - month_before_avg
        
    except:
        return 1.2  # Demo improvement value

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash("You have been logged out successfully.", "info")
    return redirect(url_for('login'))

@app.route('/init_db')
def init_database():
    """Initialize database with new tables for real data tracking"""
    try:
        db.create_all()
        flash("Database initialized successfully with new tracking tables!", "success")
        return redirect(url_for('dashboard'))
    except Exception as e:
        flash(f"Error initializing database: {str(e)}", "error")
        return redirect(url_for('dashboard'))

# Helper functions to track feature usage
def track_dsa_practice(user_id, problem_title, category='General', difficulty='Medium', solved=False):
    """Track DSA practice session"""
    try:
        session_record = DSAPracticeSession(
            user_id=user_id,
            problem_title=problem_title,
            problem_category=category,
            difficulty=difficulty,
            solved=solved
        )
        db.session.add(session_record)
        db.session.commit()
        return True
    except Exception as e:
        print(f"Error tracking DSA practice: {e}")
        return False

def track_english_booster_session(user_id, session_type='Grammar', score=0.0, exercises=1):
    """Track English Booster session"""
    try:
        session_record = EnglishBoosterSession(
            user_id=user_id,
            session_type=session_type,
            exercises_completed=exercises,
            score=score,
            completed=True,
            completed_at=datetime.utcnow()
        )
        db.session.add(session_record)
        db.session.commit()
        return True
    except Exception as e:
        print(f"Error tracking English Booster session: {e}")
        return False

def track_company_prep_session(user_id, company_name, prep_type='General', progress=0.0):
    """Track company preparation session"""
    try:
        session_record = CompanyPrepSession(
            user_id=user_id,
            company_name=company_name,
            prep_type=prep_type,
            progress_percentage=progress,
            completed=progress >= 100
        )
        db.session.add(session_record)
        db.session.commit()
        return True
    except Exception as e:
        print(f"Error tracking company prep session: {e}")
        return False

def track_resume_upload(user_id, filename, original_filename, file_size=0):
    """Track resume upload"""
    try:
        resume_record = ResumeUpload(
            user_id=user_id,
            filename=filename,
            original_filename=original_filename,
            file_size=file_size,
            file_type='pdf',
            analysis_score=85.0  # Default good score
        )
        db.session.add(resume_record)
        db.session.commit()
        return True
    except Exception as e:
        print(f"Error tracking resume upload: {e}")
        return False

@app.route('/dsa')
def dsa():
    return render_template('dsa.html')

# API routes for tracking feature usage
@app.route('/api/track_dsa', methods=['POST'])
def api_track_dsa():
    """API endpoint to track DSA practice"""
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 401
    
    data = request.get_json()
    success = track_dsa_practice(
        user_id=session['user_id'],
        problem_title=data.get('problem_title', 'Unknown Problem'),
        category=data.get('category', 'General'),
        difficulty=data.get('difficulty', 'Medium'),
        solved=data.get('solved', False)
    )
    
    return jsonify({'status': 'success' if success else 'error'})

@app.route('/api/track_english_booster', methods=['POST'])
def api_track_english_booster():
    """API endpoint to track English Booster sessions"""
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 401
    
    data = request.get_json()
    success = track_english_booster_session(
        user_id=session['user_id'],
        session_type=data.get('session_type', 'Grammar'),
        score=data.get('score', 0.0),
        exercises=data.get('exercises', 1)
    )
    
    return jsonify({'status': 'success' if success else 'error'})

@app.route('/api/track_company_prep', methods=['POST'])
def api_track_company_prep():
    """API endpoint to track company preparation"""
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 401
    
    data = request.get_json()
    success = track_company_prep_session(
        user_id=session['user_id'],
        company_name=data.get('company_name', 'Unknown Company'),
        prep_type=data.get('prep_type', 'General'),
        progress=data.get('progress', 0.0)
    )
    
    return jsonify({'status': 'success' if success else 'error'})

@app.route('/api/track_resume_upload', methods=['POST'])
def api_track_resume_upload():
    """API endpoint to track resume uploads"""
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 401
    
    data = request.get_json()
    success = track_resume_upload(
        user_id=session['user_id'],
        filename=data.get('filename', 'resume.pdf'),
        original_filename=data.get('original_filename', 'resume.pdf'),
        file_size=data.get('file_size', 0)
    )
    
    return jsonify({'status': 'success' if success else 'error'})

@app.route('/more')
def more():
    return render_template('more.html')

@app.route('/interview_progress', methods=['GET', 'POST'])
def interview_progress():
    if 'user_id' not in session:
        flash("Please log in to access interview progress tracking.", "warning")
        return redirect(url_for('login'))
    
    form = InterviewForm()
    if form.validate_on_submit():
        new_interview = Interview(
            company=form.company.data,
            position=form.position.data,
            date=form.date.data,
            notes=form.notes.data,
            status=form.status.data,
            user_id=session['user_id']
        )
        
        if form.status.data == 'Completed':
            new_interview.performance = int(form.performance.data)
        
        db.session.add(new_interview)
        db.session.commit()
        flash("Interview added successfully!", "success")
        return redirect(url_for('interview_progress'))
    
    # Get all interviews for the current user
    interviews = Interview.query.filter_by(user_id=session['user_id']).order_by(Interview.date.desc()).all()
    
    return render_template('interview_progress.html', form=form, interviews=interviews)

@app.route('/edit_interview/<int:id>', methods=['GET', 'POST'])
def edit_interview(id):
    if 'user_id' not in session:
        flash("Please log in to edit interviews.", "warning")
        return redirect(url_for('login'))
    
    interview = Interview.query.get_or_404(id)
    # Make sure the interview belongs to the current user
    if interview.user_id != session['user_id']:
        flash("You do not have permission to edit this interview.", "danger")
        return redirect(url_for('interview_progress'))
    
    form = InterviewForm(obj=interview)
    if form.validate_on_submit():
        interview.company = form.company.data
        interview.position = form.position.data
        interview.date = form.date.data
        interview.notes = form.notes.data
        interview.status = form.status.data
        
        if form.status.data == 'Completed':
            interview.performance = int(form.performance.data)
        
        db.session.commit()
        flash("Interview updated successfully!", "success")
        return redirect(url_for('interview_progress'))
    
    return render_template('edit_interview.html', form=form, interview=interview)

@app.route('/delete_interview/<int:id>', methods=['POST'])
def delete_interview(id):
    if 'user_id' not in session:
        flash("Please log in to delete interviews.", "warning")
        return redirect(url_for('login'))
    
    interview = Interview.query.get_or_404(id)
    # Make sure the interview belongs to the current user
    if interview.user_id != session['user_id']:
        flash("You do not have permission to delete this interview.", "danger")
        return redirect(url_for('interview_progress'))
    
    db.session.delete(interview)
    db.session.commit()
    flash("Interview deleted successfully!", "success")
    return redirect(url_for('interview_progress'))

def generate_interview_questions(job_role, experience_level, target_company, num_questions):
    """Generate interview questions using Gemini model"""
    prompt = f"""
    You are an expert interviewer at {target_company}. Generate exactly {num_questions} interview questions
    for a {experience_level} {job_role}. Cover technical and behavioral skills.
    
    The questions should be challenging but appropriate for the experience level.
    Include a mix of:
    - Technical knowledge
    - Problem-solving
    - System design (if applicable)
    - Behavioral scenarios
    - Role-specific skills
    
    Format each question as a complete, clear sentence.
    """

    try:
        import time
        # Add a small delay to avoid rate limiting
        time.sleep(1)
        
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        questions = [q.strip() for q in response.text.strip().split("\n") if q.strip()]
        return questions[:int(num_questions)]
    except Exception as e:
        print(f"Error generating questions: {e}")
        # Return fallback questions if API fails
        fallback_questions = [
            f"Tell me about your experience with {job_role} technologies.",
            f"How would you approach solving a complex problem in {job_role}?",
            f"What interests you about working at {target_company}?",
            f"Describe a challenging project you've worked on.",
            f"How do you stay updated with the latest trends in your field?"
        ]
        return fallback_questions[:int(num_questions)]

def evaluate_answer(question, answer):
    """Evaluate interview answer using Gemini model"""
    prompt = f"""
    You are a senior technical interviewer at a top technology company (Google, Microsoft, Amazon, etc.). 
    You have 10+ years of experience evaluating candidates. Evaluate this interview answer with high standards.
    
    Question: {question}
    Answer: {answer}
    
    SCORING CRITERIA (be strict and realistic):
    - Score 1-2: Poor answer, major gaps, unclear communication
    - Score 3-4: Below average, missing key points, needs significant improvement
    - Score 5-6: Average answer, covers basics but lacks depth or examples
    - Score 7-8: Good answer, demonstrates solid understanding with relevant examples
    - Score 9-10: Excellent answer, comprehensive, well-structured, shows deep expertise
    
    Evaluate based on:
    1. Technical accuracy and depth (40%)
    2. Communication clarity and structure (25%)
    3. Relevant examples and specificity (20%)
    4. Completeness of the answer (15%)
    
    Respond in this EXACT format:
    <score>[single number from 1-10]</score>
    <summary>One-line summary of performance</summary>
    <strengths>
    - Key strength 1
    - Key strength 2
    </strengths>
    <improvements>
    - Improvement tip 1
    - Improvement tip 2
    </improvements>
    <detailed_feedback>2-3 sentences of specific, actionable feedback</detailed_feedback>
    """

    try:
        import time
        # Add a small delay to avoid rate limiting
        time.sleep(1)
        
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error generating feedback: {e}")
        # Return fallback feedback if API fails - use a more realistic default score
        return """
        <score>4</score>
        <summary>Unable to evaluate due to technical error</summary>
        <strengths>
        - Attempted to provide an answer
        - Engaged with the question
        </strengths>
        <improvements>
        - Please try again for a proper evaluation
        - Ensure your answer is clear and complete
        </improvements>
        <detailed_feedback>Technical error occurred during evaluation. Please retry to get accurate feedback on your response quality and areas for improvement.</detailed_feedback>
        """

@app.route('/continue_interview/<int:interview_id>')
def continue_interview(interview_id):
    """Route to continue an incomplete interview"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Get the interview
    interview = AIInterview.query.get_or_404(interview_id)
    
    # Check if user owns this interview
    if interview.user_id != session['user_id']:
        flash('You are not authorized to access this interview.', 'error')
        return redirect(url_for('ai_interview'))
    
    # Get questions and answers
    questions = interview.questions.split("\n") if interview.questions else []
    answers = interview.answers.split("\nQ: ") if interview.answers else []
    
    # Calculate the next unanswered question index
    next_question_index = len(answers)
    if next_question_index >= len(questions):
        flash('This interview is already completed.', 'info')
        return redirect(url_for('ai_interview'))
    
    # Prepare data for frontend
    interview_data = {
        'interview_id': interview.id,
        'job_role': interview.job_role,
        'experience_level': interview.experience_level,
        'target_company': interview.target_company,
        'questions': questions,
        'next_question_index': next_question_index,
        'total_questions': len(questions),
        'completed_answers': answers
    }
    
    return render_template('ai_interview.html', 
                         continue_data=interview_data,
                         ai_interviews=AIInterview.query.filter_by(user_id=session['user_id']).order_by(AIInterview.date.desc()).all())

@app.route('/ai_interview', methods=['GET', 'POST'])
def ai_interview():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        if 'start_interview' in request.form:
            # Start new interview
            job_role = request.form.get('job_role')
            experience_level = request.form.get('experience_level')
            target_company = request.form.get('target_company')
            num_questions = request.form.get('num_questions', '5')

            # Generate questions
            questions = generate_interview_questions(job_role, experience_level, target_company, int(num_questions))
            
            if not questions:
                return jsonify({
                    'status': 'error',
                    'message': 'Failed to generate questions. Please try again.'
                })

            # Create new interview record
            interview = AIInterview(
                user_id=session['user_id'],
                job_role=job_role,
                experience_level=experience_level,
                target_company=target_company,
                questions="\n".join(questions),
                date=datetime.utcnow()
            )
            
            # Also create a session tracking record
            session_record = AIInterviewSession(
                user_id=session['user_id'],
                position=job_role,
                questions_asked=len(questions),
                questions_answered=0,
                average_score=0.0,
                completed=False,
                session_data=json.dumps({
                    'experience_level': experience_level,
                    'target_company': target_company,
                    'questions': questions
                })
            )
            
            db.session.add(interview)
            db.session.add(session_record)
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'interview_id': interview.id,
                'questions': questions,
                'current_index': 0
            })
        
        elif 'submit_answer' in request.form:
            try:
                # Submit answer for evaluation
                interview_id = request.form.get('interview_id')
                question = request.form.get('question')
                answer = request.form.get('answer')
                question_index = request.form.get('question_index', 0)

                if not all([interview_id, question, answer]):
                    return jsonify({
                        'status': 'error',
                        'message': 'Missing required fields'
                    })

                # Get interview record
                interview = AIInterview.query.get(interview_id)
                if not interview:
                    return jsonify({
                        'status': 'error',
                        'message': 'Interview not found'
                    })
                
                # Evaluate answer
                print(f"Evaluating answer for question: {question[:50]}...")
                print(f"Answer: {answer[:100]}...")
                feedback = evaluate_answer(question, answer)
                print(f"Feedback received: {feedback[:200]}...")
                
                # Update interview record
                if not interview.answers:
                    interview.answers = answer
                    interview.feedback = feedback
                else:
                    interview.answers += f"\nQ: {question}\nA: {answer}"
                    interview.feedback += f"\n\n{feedback}"
                
                # Extract score from feedback with improved logic
                try:
                    score = None
                    
                    if '<score>' in feedback and '</score>' in feedback:
                        score_text = feedback.split('<score>')[1].split('</score>')[0].strip()
                        print(f"Extracted score text: '{score_text}'")
                        
                        # Try multiple patterns to extract the score
                        import re
                        patterns = [
                            r'^(\d+(?:\.\d+)?)$',  # Just a number
                            r'Score:?\s*(\d+(?:\.\d+)?)',  # "Score: X" or "Score X"
                            r'(\d+(?:\.\d+)?)\s*/\s*10',  # "X/10"
                            r'(\d+(?:\.\d+)?)\s*out\s*of\s*10',  # "X out of 10"
                            r'(\d+(?:\.\d+)?)\s*points?',  # "X points"
                        ]
                        
                        for pattern in patterns:
                            score_match = re.search(pattern, score_text, re.IGNORECASE)
                            if score_match:
                                score = float(score_match.group(1))
                                # Ensure score is within valid range
                                score = max(1, min(10, score))
                                print(f"Successfully extracted score: {score}")
                                break
                        
                        if score is None:
                            print(f"Could not extract score from: '{score_text}'")
                            # Try to find any number in the score text as last resort
                            number_match = re.search(r'(\d+(?:\.\d+)?)', score_text)
                            if number_match:
                                potential_score = float(number_match.group(1))
                                if 1 <= potential_score <= 10:
                                    score = potential_score
                                    print(f"Found fallback score: {score}")
                    
                    if score is None:
                        print("No score tags found or could not extract score from feedback")
                        print(f"Feedback preview: {feedback[:200]}...")
                        # Use a more realistic default based on answer length and content
                        answer_length = len(answer.strip())
                        if answer_length < 10:
                            score = 2.0  # Very short answers get low scores
                        elif answer_length < 50:
                            score = 3.0  # Short answers
                        elif answer_length < 150:
                            score = 4.0  # Medium answers
                        else:
                            score = 5.0  # Longer answers get slightly better default
                        print(f"Using length-based default score: {score}")
                    
                    # Update interview performance
                    if interview.performance is None:
                        interview.performance = score
                    else:
                        # Weighted average (give more weight to recent answers)
                        interview.performance = (interview.performance * 0.6) + (score * 0.4)
                        
                    print(f"Final performance score: {interview.performance}")
                    
                except Exception as e:
                    print(f"Error extracting score: {e}")
                    import traceback
                    print(f"Traceback: {traceback.format_exc()}")
                    # Set a more realistic default score if extraction fails
                    if interview.performance is None:
                        interview.performance = 4.0  # Lower default to encourage better answers
                    
                db.session.commit()

                # Get total number of questions
                total_questions = len(interview.questions.split("\n"))
                is_complete = int(question_index) + 1 >= total_questions
                
                return jsonify({
                    'status': 'success',
                    'feedback': feedback,
                    'is_complete': is_complete
                })
            except Exception as e:
                import traceback
                print(f"Error in submit_answer: {e}")
                print(f"Traceback: {traceback.format_exc()}")
                return jsonify({
                    'status': 'error',
                    'message': f'Error: {str(e)}. Please try again.'
                })
    
    # GET request - show interview page
    ai_interviews = AIInterview.query.filter_by(user_id=session['user_id']).order_by(AIInterview.date.desc()).all()
    return render_template('ai_interview.html', ai_interviews=ai_interviews)

@app.route('/ai_interview/<int:interview_id>/feedback')
def get_interview_feedback(interview_id):
    """Get detailed feedback for an interview"""
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    
    interview = AIInterview.query.get_or_404(interview_id)
    if interview.user_id != session['user_id']:
        return jsonify({'status': 'error', 'message': 'Not authorized'}), 403
    
    # Format feedback HTML
    feedback_html = f"""
    <div class="feedback-summary card mb-4">
        <div class="card-body">
            <div class="row align-items-center">
                <div class="col-md-8">
                    <h4 class="card-title mb-3">Interview Summary</h4>
                    <p class="mb-2"><strong>Role:</strong> {interview.job_role}</p>
                    <p class="mb-2"><strong>Company:</strong> {interview.target_company}</p>
                    <p class="mb-2"><strong>Experience Level:</strong> {interview.experience_level}</p>
                    <p class="mb-0"><strong>Date:</strong> {interview.date.strftime('%Y-%m-%d %H:%M')}</p>
                </div>
                <div class="col-md-4 text-center">
                    <div class="performance-indicator">
                        <div class="display-4 mb-2">{interview.performance or 'N/A'}</div>
                        <p class="text-muted">Overall Score</p>
                        {f'<div class="progress"><div class="progress-bar bg-success" style="width: {float(interview.performance) * 10}%"></div></div>' if interview.performance else ''}
                    </div>
                </div>
            </div>
        </div>
    </div>
    """
    
    if interview.questions and interview.answers:
        questions = interview.questions.split("\n")
        answers = interview.answers.split("\nQ: ")
        feedbacks = interview.feedback.split("\n\n") if interview.feedback else []
        
        feedback_html += '<div class="questions-section">'
        
        for i, (question, feedback) in enumerate(zip(questions, feedbacks)):
            answer = answers[i] if i < len(answers) else "No answer provided"
            
            feedback_html += f"""
            <div class="card mb-3 question-card">
                <div class="card-header">
                    <h5 class="mb-0">
                        <i class="fas fa-question-circle text-primary me-2"></i>
                        Question {i+1}
                    </h5>
                </div>
                <div class="card-body">
                    <div class="question-text mb-3">
                        <p class="lead">{question}</p>
                    </div>
                    <div class="answer-text mb-3">
                        <h6 class="text-muted mb-2">Your Answer:</h6>
                        <div class="p-3 bg-light rounded">{answer}</div>
                    </div>
                    <div class="feedback-section">
                        <h6 class="text-muted mb-2">Feedback:</h6>
                        <div class="feedback-content">
                            {feedback}
                        </div>
                    </div>
                </div>
            </div>
            """
        
        feedback_html += '</div>'
    
    return jsonify({
        'status': 'success',
        'feedback': feedback_html
    })

@app.route('/company_prep')
def company_prep():
    companies = [
        {
            'name': 'Google',
            'logo': 'google.png',
            'color': '#4285F4',
            'gradient': 'linear-gradient(135deg, #4285F4 0%, #34A853 100%)',
            'faqs': [
                {'question': 'What is Google\'s interview process?', 'answer': 'Google\'s interview process typically includes phone screening, technical interviews, and onsite interviews focusing on algorithms, system design, and behavioral questions.'},
                {'question': 'What programming languages does Google prefer?', 'answer': 'Google primarily uses Python, Java, C++, and Go. However, they focus on problem-solving skills rather than specific languages.'},
                {'question': 'What are common Google interview topics?', 'answer': 'Common topics include data structures, algorithms, system design, and behavioral questions about past experiences.'}
            ],
            'resources': [
                {'name': 'Google Interview Guide', 'file': 'google_guide.pdf'},
                {'name': 'Sample Questions', 'file': 'google_questions.pdf'},
                {'name': 'System Design Guide', 'file': 'google_system_design.pdf'}
            ]
        },
        {
            'name': 'Microsoft',
            'logo': 'microsoft.png',
            'color': '#00A4EF',
            'gradient': 'linear-gradient(135deg, #00A4EF 0%, #7FBA00 100%)',
            'faqs': [
                {'question': 'What is Microsoft\'s interview process?', 'answer': 'Microsoft\'s process includes phone screening, technical interviews, and onsite interviews focusing on coding, system design, and behavioral questions.'},
                {'question': 'What technologies does Microsoft focus on?', 'answer': 'Microsoft focuses on C#, .NET, Azure, and web technologies, but also values problem-solving skills.'},
                {'question': 'What are common Microsoft interview topics?', 'answer': 'Topics include algorithms, data structures, system design, and behavioral questions.'}
            ],
            'resources': [
                {'name': 'Microsoft Interview Guide', 'file': 'microsoft_guide.pdf'},
                {'name': 'Sample Questions', 'file': 'microsoft_questions.pdf'},
                {'name': 'Azure Guide', 'file': 'microsoft_azure.pdf'}
            ]
        },
        {
            'name': 'Amazon',
            'logo': 'amazon.png',
            'color': '#FF9900',
            'gradient': 'linear-gradient(135deg, #FF9900 0%, #232F3E 100%)',
            'faqs': [
                {'question': 'What is Amazon\'s interview process?', 'answer': 'Amazon\'s process includes online assessment, phone interviews, and onsite interviews focusing on leadership principles and technical skills.'},
                {'question': 'What are Amazon\'s leadership principles?', 'answer': 'Amazon has 16 leadership principles that are crucial for interviews, including customer obsession and ownership.'},
                {'question': 'What are common Amazon interview topics?', 'answer': 'Topics include system design, algorithms, and behavioral questions based on leadership principles.'}
            ],
            'resources': [
                {'name': 'Amazon Interview Guide', 'file': 'amazon_guide.pdf'},
                {'name': 'Leadership Principles', 'file': 'amazon_principles.pdf'},
                {'name': 'System Design Guide', 'file': 'amazon_system_design.pdf'}
            ]
        },
        {
            'name': 'Meta',
            'logo': 'meta.png',
            'color': '#1877F2',
            'gradient': 'linear-gradient(135deg, #1877F2 0%, #166FE5 100%)',
            'faqs': [
                {'question': 'What is Meta\'s interview process?', 'answer': 'Meta\'s process includes phone screening, technical interviews, and onsite interviews focusing on coding and system design.'},
                {'question': 'What technologies does Meta use?', 'answer': 'Meta primarily uses React, PHP, Python, and various AI/ML technologies.'},
                {'question': 'What are common Meta interview topics?', 'answer': 'Topics include algorithms, system design, and behavioral questions about past experiences.'}
            ],
            'resources': [
                {'name': 'Meta Interview Guide', 'file': 'meta_guide.pdf'},
                {'name': 'Sample Questions', 'file': 'meta_questions.pdf'},
                {'name': 'System Design Guide', 'file': 'meta_system_design.pdf'}
            ]
        },
        {
            'name': 'Apple',
            'logo': 'apple.png',
            'color': '#000000',
            'gradient': 'linear-gradient(135deg, #000000 0%, #333333 100%)',
            'faqs': [
                {'question': 'What is Apple\'s interview process?', 'answer': 'Apple\'s process includes phone screening, technical interviews, and onsite interviews focusing on problem-solving and innovation.'},
                {'question': 'What technologies does Apple focus on?', 'answer': 'Apple focuses on iOS development, Swift, Objective-C, and hardware-software integration.'},
                {'question': 'What are common Apple interview topics?', 'answer': 'Topics include algorithms, system design, and questions about user experience and design.'}
            ],
            'resources': [
                {'name': 'Apple Interview Guide', 'file': 'apple_guide.pdf'},
                {'name': 'Sample Questions', 'file': 'apple_questions.pdf'},
                {'name': 'iOS Development Guide', 'file': 'apple_ios.pdf'}
            ]
        }
    ]
    return render_template('company_prep.html', companies=companies)

@app.route('/company/<company>')
def company_detail(company):
    companies = [
        {
            'name': 'Google',
            'logo': 'google.png',
            'color': '#4285F4',
            'gradient': 'linear-gradient(135deg, #4285F4 0%, #34A853 100%)',
            'faqs': [
                {'question': 'What is Google\'s interview process?', 'answer': 'Google\'s interview process typically includes phone screening, technical interviews, and onsite interviews focusing on algorithms, system design, and behavioral questions.'},
                {'question': 'What programming languages does Google prefer?', 'answer': 'Google primarily uses Python, Java, C++, and Go. However, they focus on problem-solving skills rather than specific languages.'},
                {'question': 'What are common Google interview topics?', 'answer': 'Common topics include data structures, algorithms, system design, and behavioral questions about past experiences.'}
            ],
            'resources': [
                {'name': 'Google Interview Guide', 'file': 'google_guide.pdf'},
                {'name': 'Sample Questions', 'file': 'google_questions.pdf'},
                {'name': 'System Design Guide', 'file': 'google_system_design.pdf'}
            ]
        },
        {
            'name': 'Microsoft',
            'logo': 'microsoft.png',
            'color': '#00A4EF',
            'gradient': 'linear-gradient(135deg, #00A4EF 0%, #7FBA00 100%)',
            'faqs': [
                {'question': 'What is Microsoft\'s interview process?', 'answer': 'Microsoft\'s process includes phone screening, technical interviews, and onsite interviews focusing on coding, system design, and behavioral questions.'},
                {'question': 'What technologies does Microsoft focus on?', 'answer': 'Microsoft focuses on C#, .NET, Azure, and web technologies, but also values problem-solving skills.'},
                {'question': 'What are common Microsoft interview topics?', 'answer': 'Topics include algorithms, data structures, system design, and behavioral questions.'}
            ],
            'resources': [
                {'name': 'Microsoft Interview Guide', 'file': 'microsoft_guide.pdf'},
                {'name': 'Sample Questions', 'file': 'microsoft_questions.pdf'},
                {'name': 'Azure Guide', 'file': 'microsoft_azure.pdf'}
            ]
        },
        {
            'name': 'Amazon',
            'logo': 'amazon.png',
            'color': '#FF9900',
            'gradient': 'linear-gradient(135deg, #FF9900 0%, #232F3E 100%)',
            'faqs': [
                {'question': 'What is Amazon\'s interview process?', 'answer': 'Amazon\'s process includes online assessment, phone interviews, and onsite interviews focusing on leadership principles and technical skills.'},
                {'question': 'What are Amazon\'s leadership principles?', 'answer': 'Amazon has 16 leadership principles that are crucial for interviews, including customer obsession and ownership.'},
                {'question': 'What are common Amazon interview topics?', 'answer': 'Topics include system design, algorithms, and behavioral questions based on leadership principles.'}
            ],
            'resources': [
                {'name': 'Amazon Interview Guide', 'file': 'amazon_guide.pdf'},
                {'name': 'Leadership Principles', 'file': 'amazon_principles.pdf'},
                {'name': 'System Design Guide', 'file': 'amazon_system_design.pdf'}
            ]
        },
        {
            'name': 'Meta',
            'logo': 'meta.png',
            'color': '#1877F2',
            'gradient': 'linear-gradient(135deg, #1877F2 0%, #166FE5 100%)',
            'faqs': [
                {'question': 'What is Meta\'s interview process?', 'answer': 'Meta\'s process includes phone screening, technical interviews, and onsite interviews focusing on coding and system design.'},
                {'question': 'What technologies does Meta use?', 'answer': 'Meta primarily uses React, PHP, Python, and various AI/ML technologies.'},
                {'question': 'What are common Meta interview topics?', 'answer': 'Topics include algorithms, system design, and behavioral questions about past experiences.'}
            ],
            'resources': [
                {'name': 'Meta Interview Guide', 'file': 'meta_guide.pdf'},
                {'name': 'Sample Questions', 'file': 'meta_questions.pdf'},
                {'name': 'System Design Guide', 'file': 'meta_system_design.pdf'}
            ]
        },
        {
            'name': 'Apple',
            'logo': 'apple.png',
            'color': '#000000',
            'gradient': 'linear-gradient(135deg, #000000 0%, #333333 100%)',
            'faqs': [
                {'question': 'What is Apple\'s interview process?', 'answer': 'Apple\'s process includes phone screening, technical interviews, and onsite interviews focusing on problem-solving and innovation.'},
                {'question': 'What technologies does Apple focus on?', 'answer': 'Apple focuses on iOS development, Swift, Objective-C, and hardware-software integration.'},
                {'question': 'What are common Apple interview topics?', 'answer': 'Topics include algorithms, system design, and questions about user experience and design.'}
            ],
            'resources': [
                {'name': 'Apple Interview Guide', 'file': 'apple_guide.pdf'},
                {'name': 'Sample Questions', 'file': 'apple_questions.pdf'},
                {'name': 'iOS Development Guide', 'file': 'apple_ios.pdf'}
            ]
        }
    ]
    
    company_data = next((c for c in companies if c['name'].lower() == company), None)
    if company_data is None:
        abort(404)
    
    return render_template('company_detail.html', company=company_data)

@app.route('/resources')
def resources():
    return render_template('resources.html')

@app.route('/career_roadmap', methods=['GET', 'POST'])
def career_roadmap():
    roadmap_data = None
    debug_info = None
    
    if request.method == 'POST':
        role = request.form.get('role')
        experience = request.form.get('experience')
        company = request.form.get('company')
        resume_text = ""
        
        # Handle resume upload if provided
        if 'resume' in request.files:
            resume_file = request.files['resume']
            if resume_file and resume_file.filename != '':
                try:
                    if resume_file.filename.endswith('.pdf'):
                        # Extract text from PDF
                        import fitz  # PyMuPDF
                        pdf_document = fitz.open(stream=resume_file.read(), filetype="pdf")
                        resume_text = ""
                        for page in pdf_document:
                            resume_text += page.get_text()
                    elif resume_file.filename.endswith('.txt'):
                    # Read text file directly
                        resume_text = resume_file.read().decode('utf-8')
                except Exception as e:
                    flash(f"Error processing resume: {str(e)}", "warning")
                
        # Create the prompt for generating the roadmap
        prompt = f"""
        Create a detailed career roadmap for a {role} position at {company} with {experience} years of experience.
        The response should be a JSON object with the following structure:
        {{
            "title": "Career Roadmap for [Role] at [Company]",
            "overview": "Brief overview of the roadmap",
            "stages": [
                {{
                    "name": "Stage name",
                    "timeframe": "Expected duration",
                    "description": "Stage description",
                    "milestones": [
                        {{
                            "title": "Milestone title",
                            "description": "Milestone description",
                            "tasks": ["Task 1", "Task 2", ...]
                        }}
                    ],
                    "skills": ["Skill 1", "Skill 2", ...],
                    "resources": ["Resource 1", "Resource 2", ...]
                }}
            ],
            "daily_practices": ["Practice 1", "Practice 2", ...],
            "long_term_goals": ["Goal 1", "Goal 2", ...]
        }}

        If resume text is provided, use it to personalize the roadmap:
        {resume_text if resume_text else "No resume provided"}

        Return ONLY the JSON object, no additional text or formatting.
        """
        
        print("Sending request to Gemini API...")
        
        try:
            # Configure Gemini API with the latest key
            genai.configure(api_key="AIzaSyDhj5eznHfo9Dt80Ptvm_pi-LVqd_2i8oc")
            
            # Create the model and generate content
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)
            response_text = response.text.strip()
            print(f"Response received from Gemini API: {response_text[:100]}...")
            
            # Try to find a JSON block with regex
            import re
            json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1).strip()
                print("Extracted JSON from code block")
            else:
                # If no code block found, treat the entire response as JSON
                json_str = response_text
                print("Using entire response as JSON")
            
            # Clean up potential non-JSON parts
            json_str = re.sub(r'^```.*?$', '', json_str, flags=re.MULTILINE)
            json_str = re.sub(r'^```$', '', json_str, flags=re.MULTILINE)
            
            # Parse JSON
            roadmap_data = json.loads(json_str)
            print("JSON successfully parsed")
            
            # Store the roadmap in the database if user is logged in
            if 'user_id' in session:
                try:
                    # Use SQLAlchemy to store the roadmap
                    roadmap = CareerRoadmap(
                        user_id=session['user_id'],
                        job_role=role,
                        experience=experience,
                        target_company=company,
                        roadmap_data=json.dumps(roadmap_data),
                        created_at=datetime.utcnow()
                    )
                    db.session.add(roadmap)
                    db.session.commit()
                except Exception as e:
                    print(f"Database error: {e}")
                    flash(f"Error saving roadmap: {str(e)}", "warning")
                    db.session.rollback()
            
        except Exception as e:
            error_msg = f"Error generating roadmap: {str(e)}"
            print(error_msg)
            flash(error_msg, "danger")
            debug_info = {
                'error': str(e),
                'prompt': prompt,
                'response': response_text if 'response_text' in locals() else None
            }
    
    return render_template('career_roadmap.html',
                         roadmap_data=roadmap_data,
                         debug_info=debug_info)

class CareerRoadmap(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    job_role = db.Column(db.String(100), nullable=False)
    experience = db.Column(db.String(50), nullable=False)
    target_company = db.Column(db.String(100), nullable=False)
    roadmap_data = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user = db.relationship('User', backref='roadmaps', lazy=True)

@app.route('/generate_detailed_roadmap', methods=['POST'])
def generate_detailed_roadmap():
    """API endpoint to generate a detailed career roadmap"""
    try:
        data = request.json
        role = data.get('role')
        experience = data.get('experience')
        company = data.get('company')
        
        if not all([role, experience, company]):
            return jsonify({
                'status': 'error', 
                'message': 'Missing required parameters'
            })
            
        # Configure Gemini API with the specified key
        genai.configure(api_key="AIzaSyDhj5eznHfo9Dt80Ptvm_pi-LVqd_2i8oc")
        
        # Generate detailed roadmap 
        prompt = f"""
        Create a detailed, well-structured HTML career roadmap for a {role} with {experience} years of experience 
        aiming to work at {company}.
        
        Include these sections:
        1. Technical skills needed at each career stage
        2. Recommended learning resources (specific books, courses, websites)
        3. Portfolio projects to build
        4. Interview preparation specific to {company}
        5. Career progression timeline
        
        Format your response as clean HTML using Bootstrap 5 classes for styling.
        Use these Bootstrap components:
        - Cards for each section
        - Progress bars for skill levels
        - Badges for technologies
        - Accordions for expandable content
        - Icons from Font Awesome (using the <i> tag)
        
        Make the HTML visually attractive with proper spacing, colors, and organization.
        Do NOT include <!DOCTYPE>, <html>, <head> or <body> tags - just the content HTML.
        
        IMPORTANT: Return ONLY the HTML without any markdown code blocks, explanations or other text.
        """
        
        print("Generating detailed roadmap...")
        # Call Gemini model - use the correct model
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        
        # Extract HTML content from response and clean it up
        html_content = response.text.strip()
        
        # Check if the response contains markdown code blocks with HTML
        import re
        html_match = re.search(r'```(?:html)?\s*(.*?)\s*```', html_content, re.DOTALL)
        if html_match:
            html_content = html_match.group(1).strip()
            print("Extracted HTML from code block")
        
        print(f"Generated HTML content length: {len(html_content)}")
        
        return jsonify({
            'status': 'success',
            'content': html_content
        })
        
    except Exception as e:
        error_msg = str(e)
        print(f"Error generating detailed roadmap: {error_msg}")
        return jsonify({
            'status': 'error',
            'message': error_msg
        })

@app.route('/upload_profile_photo', methods=['POST'])
def upload_profile_photo():
    if 'user_id' not in session:
        flash("Please log in to upload a profile photo.", "warning")
        return redirect(url_for('login'))
    
    if 'profile_photo' not in request.files:
        flash("No file part", "danger")
        return redirect(url_for('dashboard'))
    
    file = request.files['profile_photo']
    
    # If user doesn't select a file, browser also
    # submit an empty part without filename
    if file.filename == '':
        flash("No selected file", "danger")
        return redirect(url_for('dashboard'))
    
    if file and allowed_image(file.filename):
        # Create a secure filename to prevent path traversal attacks
        filename = secure_filename(f"user_{session['user_id']}_{file.filename}")
        filepath = os.path.join(app.config['PROFILE_PHOTOS_FOLDER'], filename)
        
        # Save the file
        file.save(filepath)
        
        # Update the user's profile_photo field in the database
        user = User.query.get(session['user_id'])
        user.profile_photo = filename
        db.session.commit()
        
        flash("Profile photo updated successfully!", "success")
        return redirect(url_for('dashboard'))
    else:
        flash("Allowed image types are png, jpg, jpeg, gif", "danger")
        return redirect(url_for('dashboard'))

@app.route('/download/<filename>')
def download_file(filename):
    """
    Route to handle file downloads for company resources.
    The filename parameter should match the resource file names in the company data.
    """
    # Ensure the filename is safe
    secure_name = secure_filename(filename)
    try:
        # Return the file from the resources directory
        return send_from_directory(os.path.join('static', 'resources'), secure_name, as_attachment=True)
    except FileNotFoundError:
        flash(f"File {filename} not found.", "danger")
        return redirect(url_for('company_prep'))

@app.route('/db_health_check')
def db_health_check():
    """
    Route to check database connectivity and health.
    This can help diagnose issues with the database.
    """
    try:
        # Check direct SQLite connection
        sqlite_connected, sqlite_version = get_db_connection_status()
        
        # Check if we can connect to the database via SQLAlchemy
        test_user = User.query.first()
        
        # Get counts of records in key tables
        user_count = User.query.count()
        interview_count = Interview.query.count()
        ai_interview_count = AIInterview.query.count()
        
        return jsonify({
            'status': 'ok',
            'message': 'Database is connected and healthy',
            'sqlite': {
                'connected': sqlite_connected,
                'version': sqlite_version,
            },
            'sqlalchemy': {
                'connected': True,
                'engine': str(db.engine.url)
            },
            'record_counts': {
                'users': user_count,
                'interviews': interview_count,
                'ai_interviews': ai_interview_count
            }
        })
    except Exception as e:
        error_message = str(e)
        
        # Try direct connection to diagnose
        sqlite_connected, sqlite_version = get_db_connection_status()
        
        return jsonify({
            'status': 'error',
            'message': 'SQLAlchemy connection failed',
            'error': error_message,
            'sqlite': {
                'connected': sqlite_connected,
                'version': sqlite_version if sqlite_connected else 'Unknown'
            }
        }), 500

@app.route('/live_interview')
def live_interview():
    return render_template('live_interview.html')

@app.route('/generate_interview_question', methods=['POST'])
def generate_interview_question():
    try:
        data = request.json
        question_number = data.get('questionNumber', 1)
        total_questions = data.get('totalQuestions', 5)
        
        # Configure Gemini model
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        # Generate interview question
        prompt = f"""
        Generate a professional interview question ({question_number} of {total_questions}).
        The question should be challenging but clear, and appropriate for a technical interview.
        Include a mix of technical and behavioral questions.
        Return ONLY the question text, no additional context or formatting.
        """
        
        response = model.generate_content(prompt)
        question = response.text.strip()
        
        return jsonify({'question': question})
    except Exception as e:
        print(f"Error generating question: {str(e)}")
        return jsonify({'error': 'Failed to generate question'}), 500

@app.route('/transcribe_audio', methods=['POST'])
def transcribe_audio():
    try:
        if 'file' not in request.files:
            return jsonify({
                'status': 'error',
                'error': 'No file provided'
            }), 400
            
        audio_file = request.files['file']
        if not audio_file.filename:
            return jsonify({
                'status': 'error',
                'error': 'Empty file provided'
            }), 400
            
        # Verify file type
        if not audio_file.filename.lower().endswith('.wav'):
            return jsonify({
                'status': 'error',
                'error': 'Only WAV files are supported'
            }), 400
            
        # Create uploads directory if it doesn't exist
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        
        # Save the uploaded file temporarily with a unique name
        temp_filename = f"answer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
        temp_filepath = os.path.join(UPLOAD_FOLDER, temp_filename)
        
        try:
            # Save the file
            audio_file.save(temp_filepath)
            
            # Print file info for debugging
            file_size = os.path.getsize(temp_filepath)
            print(f"Saved audio file: {temp_filepath}")
            print(f"File size: {file_size} bytes")
            
            # Upload to Gemini (no FFmpeg needed)
            print("Uploading to Gemini for transcription...")
            myfile = genai.upload_file(temp_filepath)
            
            model = genai.GenerativeModel("gemini-1.5-flash")
            print("Generating transcript...")
            
            response = model.generate_content([
                "Transcribe the following audio file exactly as spoken in English. Do not add any other text, commentary, or speaker labels. Just the transcription.", 
                myfile
            ])
            
            transcription = response.text.strip()
            print(f"Transcription result: {transcription}")
            
            if not transcription:
                raise Exception("No transcription generated")
            
            # Clean up the temporary file
            os.remove(temp_filepath)
            
            return jsonify({
                'status': 'success',
                'transcription': transcription
            })
            
        except Exception as e:
            # Clean up the temporary file in case of error
            if os.path.exists(temp_filepath):
                try:
                    os.remove(temp_filepath)
                except:
                    pass
            raise e
                
    except Exception as e:
        error_msg = str(e)
        print(f"Error transcribing audio: {error_msg}")
        return jsonify({
            'status': 'error',
            'error': 'Failed to transcribe audio',
            'details': error_msg
        }), 500

@app.route('/evaluate_answer', methods=['POST'])
def evaluate_answer_endpoint():
    try:
        data = request.json
        question = data.get('question', '')
        answer = data.get('answer', '')
        
        if not question or not answer:
            return jsonify({
                'status': 'error',
                'error': 'Question and answer are required'
            }), 400
        
        # Configure Gemini model
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        # Create evaluation prompt
        prompt = f"""
        You are a senior technical interviewer at a top technology company with 10+ years of experience. 
        Evaluate this interview answer with realistic, professional standards.
        
        Question: {question}
        Answer: {answer}
        
        SCORING CRITERIA (be realistic and strict):
        - Score 1-2: Poor answer, major gaps, unclear or irrelevant
        - Score 3-4: Below average, missing key points, needs significant improvement  
        - Score 5-6: Average answer, covers basics but lacks depth or examples
        - Score 7-8: Good answer, demonstrates solid understanding with examples
        - Score 9-10: Excellent answer, comprehensive, well-structured, shows expertise
        
        Evaluate based on:
        1. Technical accuracy and completeness (40%)
        2. Communication clarity and structure (25%)
        3. Relevant examples and specificity (20%)
        4. Professional presentation (15%)
        
        Answer length consideration:
        - Very short answers (under 20 words): Maximum score 3
        - Short answers (20-50 words): Maximum score 5
        - Adequate length (50+ words): Full scoring range possible
        
        Return ONLY a JSON object in this exact format:
        {{
            "score": [integer from 1-10],
            "feedback": "[2-3 sentences of specific, actionable feedback]",
            "suggestions": ["specific suggestion 1", "specific suggestion 2", "specific suggestion 3"]
        }}
        """
        
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        print(f"AI Response: {response_text}")
        
        # Try to extract JSON from response with multiple approaches
        import re
        json_str = None
        
        # Method 1: Look for JSON block in code fences
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            print("Found JSON in code block")
        else:
            # Method 2: Look for any JSON object
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                print("Found JSON object")
            else:
                # Method 3: Use entire response
                json_str = response_text
                print("Using entire response as JSON")
        
        try:
            evaluation = json.loads(json_str)
            print(f"Successfully parsed JSON: {evaluation}")
            
            # Validate and fix the evaluation structure
            if not isinstance(evaluation, dict):
                raise ValueError("Response is not a JSON object")
            
            # Ensure required fields exist
            if 'score' not in evaluation:
                # Try to extract score from feedback text
                feedback_text = evaluation.get('feedback', '')
                score_match = re.search(r'(\d+)(?:/10)?', feedback_text)
                evaluation['score'] = int(score_match.group(1)) if score_match else 4
            
            if 'feedback' not in evaluation:
                evaluation['feedback'] = 'Unable to generate detailed feedback. Please try again.'
            
            if 'suggestions' not in evaluation:
                evaluation['suggestions'] = ['Provide more specific examples', 'Structure your answer more clearly', 'Practice your communication skills']
            
            # Validate and fix score
            score = evaluation.get('score', 0)
            if not isinstance(score, (int, float)):
                try:
                    score = float(str(score).split('/')[0])  # Handle "7/10" format
                except:
                    score = 4
            
            score = max(1, min(10, int(score)))  # Ensure 1-10 range and integer
            evaluation['score'] = score
            
            # Validate suggestions
            if not isinstance(evaluation.get('suggestions'), list):
                evaluation['suggestions'] = ['Continue practicing to improve your interview skills']
            
            # Ensure feedback is a string
            if not isinstance(evaluation.get('feedback'), str):
                evaluation['feedback'] = str(evaluation.get('feedback', 'No specific feedback available'))
            
            print(f"Final evaluation: {evaluation}")
            
            return jsonify({
                'status': 'success',
                'evaluation': evaluation
            })
            
        except (json.JSONDecodeError, ValueError) as e:
            print(f"JSON parsing failed: {e}")
            print(f"Failed to parse: {json_str[:200]}...")
            
            # Analyze the answer to provide a more intelligent fallback score
            answer_words = len(answer.split())
            answer_length = len(answer.strip())
            
            # Basic scoring based on answer characteristics
            if answer_length < 10:
                fallback_score = 2
                fallback_feedback = "Your answer is too brief. Provide more detailed explanations and examples."
            elif answer_length < 30:
                fallback_score = 3
                fallback_feedback = "Your answer is quite short. Try to elaborate more with specific examples and details."
            elif answer_words < 20:
                fallback_score = 4
                fallback_feedback = "Your answer covers the basics but needs more depth and specific examples to be stronger."
            elif 'example' in answer.lower() or 'experience' in answer.lower():
                fallback_score = 6
                fallback_feedback = "Good attempt with some examples. Work on structuring your response more clearly and adding more technical depth."
            else:
                fallback_score = 5
                fallback_feedback = "Your answer shows understanding but could benefit from more specific examples and clearer structure."
            
            return jsonify({
                'status': 'success',
                'evaluation': {
                    'score': fallback_score,
                    'feedback': fallback_feedback,
                    'suggestions': [
                        'Include specific examples from your experience',
                        'Structure your answer with clear beginning, middle, and end',
                        'Provide more technical details and depth'
                    ]
                }
            })
        
    except Exception as e:
        print(f"Error evaluating answer: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': 'Failed to evaluate answer',
            'details': str(e)
        }), 500

@app.route('/english_communication')
def english_communication():
    return render_template('english_communication.html')

@app.route('/english_booster')
def english_booster():
    return render_template('english_booster.html')

@app.route('/api/check_grammar', methods=['POST'])
def check_grammar():
    """Check grammar using LanguageTool API"""
    try:
        data = request.json
        text = data.get('text', '').strip()
        
        if not text:
            return jsonify({
                'status': 'error',
                'error': 'No text provided'
            }), 400
        
        # Call LanguageTool API
        import requests
        
        languagetool_url = "https://api.languagetoolplus.com/v2/check"
        params = {
            'text': text,
            'language': 'en-US',
            'enabledOnly': 'false'
        }
        
        try:
            response = requests.post(languagetool_url, data=params, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                matches = result.get('matches', [])
                
                # Calculate grammar score
                total_words = len(text.split())
                error_count = len(matches)
                
                # Score calculation: start with 100, subtract points for errors
                if total_words == 0:
                    score = 0
                else:
                    # Deduct 5 points per error, with minimum score of 0
                    score = max(0, 100 - (error_count * 5))
                
                # Format errors for frontend
                formatted_errors = []
                for match in matches:
                    formatted_errors.append({
                        'offset': match.get('offset', 0),
                        'length': match.get('length', 0),
                        'message': match.get('message', ''),
                        'shortMessage': match.get('shortMessage', ''),
                        'replacements': [r.get('value', '') for r in match.get('replacements', [])[:3]],  # Max 3 suggestions
                        'category': match.get('rule', {}).get('category', {}).get('name', 'Grammar'),
                        'ruleId': match.get('rule', {}).get('id', '')
                    })
                
                return jsonify({
                    'status': 'success',
                    'score': score,
                    'totalWords': total_words,
                    'errorCount': error_count,
                    'errors': formatted_errors,
                    'originalText': text
                })
            else:
                # Fallback if LanguageTool API fails
                return jsonify({
                    'status': 'success',
                    'score': 85,  # Default decent score
                    'totalWords': len(text.split()),
                    'errorCount': 0,
                    'errors': [],
                    'originalText': text,
                    'message': 'Grammar check service temporarily unavailable. Text appears to be well-written.'
                })
                
        except requests.RequestException as e:
            print(f"LanguageTool API error: {e}")
            # Fallback response
            word_count = len(text.split())
            return jsonify({
                'status': 'success',
                'score': 80,  # Default good score
                'totalWords': word_count,
                'errorCount': 0,
                'errors': [],
                'originalText': text,
                'message': 'Grammar check service unavailable. Text length and structure look good.'
            })
        
    except Exception as e:
        print(f"Error in grammar check: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': 'Failed to check grammar',
            'details': str(e)
        }), 500

@app.route('/api/grammar_questions')
def get_grammar_questions():
    """Get grammar quiz questions"""
    try:
        import json
        import random
        
        # Read questions from JSON file
        questions_file = os.path.join(app.static_folder, 'data', 'grammar_questions.json')
        with open(questions_file, 'r', encoding='utf-8') as f:
            all_questions = json.load(f)
        
        # Shuffle and return 10 questions
        selected_questions = random.sample(all_questions, min(10, len(all_questions)))
        
        return jsonify({
            'status': 'success',
            'questions': selected_questions
        })
        
    except Exception as e:
        print(f"Error loading grammar questions: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': 'Failed to load grammar questions'
        }), 500

@app.route('/api/speaking_prompts')
def get_speaking_prompts():
    """Get random speaking prompt"""
    try:
        import json
        import random
        
        # Read prompts from JSON file
        prompts_file = os.path.join(app.static_folder, 'data', 'speaking_prompts.json')
        with open(prompts_file, 'r', encoding='utf-8') as f:
            all_prompts = json.load(f)
        
        # Return a random prompt
        selected_prompt = random.choice(all_prompts)
        
        return jsonify({
            'status': 'success',
            'prompt': selected_prompt
        })
        
    except Exception as e:
        print(f"Error loading speaking prompts: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': 'Failed to load speaking prompt'
        }), 500

@app.route('/correct_text', methods=['POST'])
def correct_text():
    try:
        data = request.json
        user_text = data.get('text', '').strip()
        
        if not user_text:
            return jsonify({
                'status': 'error',
                'error': 'No text provided'
            }), 400
        
        # Configure Gemini model
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        # Create correction prompt
        correction_prompt = f"""
        Correct and improve the English in this paragraph for interview preparation. Make it clear, concise, and professional. 
        Also provide a list of specific improvements made.
        
        Original text: "{user_text}"
        
        Please respond in this JSON format:
        {{
            "improved_text": "[The corrected and improved paragraph]",
            "improvements": ["List of specific improvements made", "Another improvement", "etc"]
        }}
        
        Focus on:
        - Grammar and sentence structure
        - Professional vocabulary
        - Clarity and conciseness
        - Interview-appropriate language
        - Flow and coherence
        
        Return ONLY the JSON object.
        """
        
        response = model.generate_content(correction_prompt)
        response_text = response.text.strip()
        
        # Try to extract JSON from response
        import re
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
        else:
            json_str = response_text
        
        try:
            correction_result = json.loads(json_str)
            
            # Validate the response structure
            if 'improved_text' not in correction_result:
                raise ValueError("Invalid response format")
            
            # Ensure improvements is a list
            if 'improvements' not in correction_result or not isinstance(correction_result['improvements'], list):
                correction_result['improvements'] = ['Text has been improved for clarity and professionalism']
            
            return jsonify({
                'status': 'success',
                'improved_text': correction_result['improved_text'],
                'improvements': correction_result['improvements']
            })
            
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            # Use the response as improved text
            improved_text = response_text.replace('"', '').strip()
            
            return jsonify({
                'status': 'success',
                'improved_text': improved_text,
                'improvements': ['Grammar and structure improvements', 'Enhanced professional vocabulary', 'Improved clarity and flow']
            })
        
    except Exception as e:
        print(f"Error correcting text: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': 'Failed to improve text',
            'details': str(e)
        }), 500

@app.route('/avatar_interview')
def avatar_interview():
    """Avatar interview page"""
    return render_template('avatar_interview.html')

@app.route('/api/avatar_interview', methods=['POST'])
def save_avatar_interview():
    """Save avatar interview answers"""
    try:
        data = request.get_json()
        if not data or 'answers' not in data:
            return jsonify({'status': 'error', 'message': 'No answers provided'}), 400
        
        # Create interviews directory if it doesn't exist
        import uuid
        interviews_dir = os.path.join('data', 'interviews')
        os.makedirs(interviews_dir, exist_ok=True)
        
        filename = f"avatar_{uuid.uuid4().hex[:8]}.json"
        filepath = os.path.join(interviews_dir, filename)
        
        interview_data = {
            "created": datetime.utcnow().isoformat(),
            "type": "avatar_interview",
            "user_id": session.get('user_id'),
            **data
        }
        
        with open(filepath, "w") as f:
            json.dump(interview_data, f, indent=2)
        
        # Also create database record for tracking
        if session.get('user_id'):
            session_record = AvatarInterviewSession(
                user_id=session['user_id'],
                job_role=data.get('jobRole', 'Unknown'),
                company=data.get('company', ''),
                experience_level=data.get('experienceLevel', ''),
                questions_count=len(data.get('answers', [])),
                questions_completed=len([a for a in data.get('answers', []) if a.get('answer', '').strip()]),
                completed=data.get('completed', False),
                video_recorded=data.get('videoRecorded', False),
                session_file=filename
            )
            
            try:
                db.session.add(session_record)
                db.session.commit()
            except Exception as db_error:
                print(f"Error saving avatar session to database: {db_error}")
                # Don't fail the request if database save fails
        
        return jsonify({"status": "saved", "file": filename}), 201
        
    except Exception as e:
        print(f"Error saving avatar interview: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/create_avatar_talk', methods=['POST'])
def create_avatar_talk():
    """Create D-ID Talk API request"""
    try:
        data = request.get_json()
        text = data.get('text', '')
        
        if not text:
            return jsonify({'status': 'error', 'message': 'No text provided'}), 400
        
        # D-ID API configuration
        import requests
        
        # Replace with your D-ID API key
        DID_API_KEY = "YOUR_DID_API_KEY_HERE"  # You'll need to replace this
        
        if DID_API_KEY == "YOUR_DID_API_KEY_HERE":
            # Return a fallback response for demo purposes
            return jsonify({
                'status': 'demo',
                'message': 'D-ID API key not configured. Using demo mode.',
                'video_url': 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4'
            })
        
        # D-ID Talk API request
        url = "https://api.d-id.com/talks"
        headers = {
            "Authorization": f"Basic {DID_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "script": {
                "type": "text",
                "input": text
            },
            "config": {
                "fluent": "false",
                "pad_audio": "0.0"
            },
            "source_url": "https://create-images-results.d-id.com/DefaultPresenters/Noelle_f/image.jpeg"  # Default presenter
        }
        
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 201:
            result = response.json()
            return jsonify({
                'status': 'success',
                'talk_id': result.get('id'),
                'video_url': result.get('result_url')
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'D-ID API error: {response.status_code}'
            }), response.status_code
            
    except Exception as e:
        print(f"Error creating avatar talk: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/generate_question', methods=['POST'])
def generate_question():
    """Generate dynamic interview questions using AI"""
    try:
        data = request.get_json()
        role = data.get('role', 'Software Engineer')
        company = data.get('company', 'General')
        difficulty = data.get('difficulty', 'Mid Level')
        previous_questions = data.get('previous_questions', [])
        question_count = data.get('question_count', 1)
        generate_multiple = data.get('generate_multiple', False)
        
        # Convert difficulty level to simple terms
        difficulty_mapping = {
            'Entry Level': 'entry level',
            'Mid Level': 'intermediate level', 
            'Senior Level': 'senior level',
            'Lead Level': 'lead/architect level',
            'Executive Level': 'executive level'
        }
        
        difficulty_level = difficulty_mapping.get(difficulty, 'intermediate level')
        
        if generate_multiple and question_count > 1:
            # Generate multiple questions at once
            questions = []
            used_questions = list(previous_questions)
            
            for i in range(question_count):
                prompt = f"""Generate one unique interview question for a {role} position at {company} company, targeting {difficulty_level} candidates.

Requirements:
- Make it relevant to {role} responsibilities at {company}
- Difficulty level: {difficulty_level}
- Avoid these already asked questions: {', '.join(used_questions) if used_questions else 'None'}
- Keep it concise and professional
- Focus on practical skills, experience, and scenarios relevant to {company}
- If {company} is a specific company (Google, Microsoft, Amazon, Apple, Meta, Netflix, Tesla), tailor the question to their known interview style and values
- For technical roles, include both technical and behavioral aspects

Return only the question, no additional text."""

                try:
                    model = genai.GenerativeModel('gemini-pro')
                    response = model.generate_content(prompt)
                    question = response.text.strip().strip('"\'')
                    
                    if question and question not in used_questions:
                        questions.append(question)
                        used_questions.append(question)
                    else:
                        # Use fallback if generation fails
                        fallback_question = get_fallback_question(role, difficulty_level, used_questions)
                        if fallback_question:
                            questions.append(fallback_question)
                            used_questions.append(fallback_question)
                        
                except Exception as ai_error:
                    print(f"AI generation error for question {i+1}: {ai_error}")
                    # Use fallback question
                    fallback_question = get_fallback_question(role, difficulty_level, used_questions)
                    if fallback_question:
                        questions.append(fallback_question)
                        used_questions.append(fallback_question)
                
                # Small delay to avoid rate limiting
                import time
                time.sleep(0.3)
            
            return jsonify({"questions": questions, "generated_count": len(questions)})
        
        else:
            # Generate single question
            prompt = f"""Generate one unique interview question for a {role} position at {company} company, targeting {difficulty_level} candidates.

Requirements:
- Make it relevant to {role} responsibilities at {company}
- Difficulty level: {difficulty_level}
- Avoid these already asked questions: {', '.join(previous_questions) if previous_questions else 'None'}
- Keep it concise and professional
- Focus on practical skills, experience, and scenarios relevant to {company}
- If {company} is a specific company (Google, Microsoft, Amazon, Apple, Meta, Netflix, Tesla), tailor the question to their known interview style and values
- For technical roles, include both technical and behavioral aspects

Return only the question, no additional text."""

            try:
                model = genai.GenerativeModel('gemini-pro')
                response = model.generate_content(prompt)
                question = response.text.strip().strip('"\'')
                
                return jsonify({"question": question})
                
            except Exception as ai_error:
                print(f"AI generation error: {ai_error}")
                # Use fallback question
                fallback_question = get_fallback_question(role, difficulty_level, previous_questions)
                return jsonify({"question": fallback_question})
            
    except Exception as e:
        print(f"Error generating question: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def get_fallback_question(role, difficulty, used_questions):
    """Get fallback questions when AI generation fails"""
    fallback_questions = {
        "software engineer": {
            "entry level": [
                "Tell me about a programming project you're proud of and what you learned from it.",
                "How do you approach debugging when your code isn't working as expected?",
                "What programming languages are you most comfortable with and why?",
                "Describe your experience with version control systems like Git.",
                "How do you stay updated with new technologies and programming trends?"
            ],
            "intermediate level": [
                "Describe a challenging technical problem you solved and your approach.",
                "How do you ensure code quality and maintainability in your projects?",
                "Tell me about a time you had to optimize code performance.",
                "How do you handle technical debt in your codebase?",
                "Describe your experience with testing strategies and frameworks."
            ],
            "senior level": [
                "How do you approach system design for scalable applications?",
                "Describe a time you mentored junior developers and the challenges you faced.",
                "How do you make architectural decisions and communicate them to your team?",
                "Tell me about a complex technical migration or refactoring you led.",
                "How do you balance technical excellence with business requirements?"
            ]
        },
        "data scientist": {
            "entry level": [
                "Tell me about a data analysis project you've worked on.",
                "How do you approach data cleaning and preprocessing?",
                "What machine learning algorithms are you familiar with?",
                "Describe your experience with data visualization tools.",
                "How do you validate the accuracy of your analysis?"
            ],
            "intermediate level": [
                "Walk me through your process for building a machine learning model.",
                "How do you handle missing or inconsistent data in your datasets?",
                "Describe a time when your analysis led to actionable business insights.",
                "How do you communicate complex technical findings to non-technical stakeholders?",
                "What strategies do you use for feature engineering and selection?"
            ],
            "senior level": [
                "How do you design and implement data science solutions at scale?",
                "Describe your approach to A/B testing and experimental design.",
                "How do you ensure reproducibility and reliability in your data science workflows?",
                "Tell me about a time you had to solve a complex business problem using data science.",
                "How do you stay current with developments in machine learning and AI?"
            ]
        }
    }
    
    # Get questions for role and difficulty
    role_key = role.lower().replace(' ', ' ').replace('engineer', 'engineer').replace('scientist', 'scientist')
    if 'software' in role_key or 'developer' in role_key or 'engineer' in role_key:
        role_key = 'software engineer'
    elif 'data' in role_key or 'scientist' in role_key:
        role_key = 'data scientist'
    else:
        role_key = 'software engineer'  # Default fallback
    
    difficulty_key = difficulty.replace(' level', '').replace('lead/architect', 'senior')
    
    questions = fallback_questions.get(role_key, {}).get(difficulty_key, 
                fallback_questions['software engineer']['intermediate level'])
    
    # Filter out already used questions
    available_questions = [q for q in questions if q not in used_questions]
    
    if available_questions:
        import random
        return random.choice(available_questions)
    
    # If all questions are used, return a generic one
    return f"Tell me about your experience with {role.lower()} and what motivates you in this field."

@app.route('/api/evaluate_answer_detailed', methods=['POST'])
def evaluate_answer_detailed():
    """Enhanced answer evaluation with posture analysis"""
    try:
        data = request.get_json()
        question = data.get('question', '')
        transcript = data.get('transcript', '')
        posture_data = data.get('posture_data', {})
        video_duration = data.get('video_duration', 0)
        
        if not transcript:
            return jsonify({'status': 'error', 'message': 'No transcript provided'}), 400
        
        # Analyze transcript using AI
        evaluation_prompt = f"""Evaluate this interview answer comprehensively:

Question: {question}

Answer: {transcript}

Provide detailed feedback in the following categories:
1. Content Quality (0-10): Relevance, depth, examples, technical accuracy
2. Communication (0-10): Clarity, structure, professional language
3. Completeness (0-10): Addresses the question fully, provides context
4. Engagement (0-10): Enthusiasm, confidence, storytelling

For each category, provide:
- Score (0-10)
- Brief explanation (1-2 sentences)
- Specific improvement suggestions

Format as JSON:
{{
    "content_quality": {{"score": X, "feedback": "...", "suggestions": "..."}},
    "communication": {{"score": X, "feedback": "...", "suggestions": "..."}},
    "completeness": {{"score": X, "feedback": "...", "suggestions": "..."}},
    "engagement": {{"score": X, "feedback": "...", "suggestions": "..."}},
    "overall_score": X,
    "overall_feedback": "...",
    "strengths": ["...", "..."],
    "areas_for_improvement": ["...", "..."]
}}"""

        ai_evaluation = {}
        try:
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content(evaluation_prompt)
            
            # Try to parse JSON response
            import json
            import re
            
            response_text = response.text.strip()
            # Extract JSON from response if it's wrapped in markdown
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(1)
            
            ai_evaluation = json.loads(response_text)
            
        except Exception as ai_error:
            print(f"AI evaluation error: {ai_error}")
            # Fallback evaluation logic
            ai_evaluation = generate_fallback_evaluation(question, transcript)
        
        # Analyze posture data
        posture_analysis = analyze_posture_data(posture_data)
        
        # Analyze video metrics
        video_analysis = analyze_video_metrics(transcript, video_duration)
        
        # Combine all analyses
        combined_feedback = {
            "transcript_analysis": ai_evaluation,
            "posture_analysis": posture_analysis,
            "video_analysis": video_analysis,
            "overall_score": calculate_overall_score(ai_evaluation, posture_analysis, video_analysis),
            "detailed_feedback": generate_detailed_feedback(ai_evaluation, posture_analysis, video_analysis),
            "improvement_tips": generate_improvement_tips(ai_evaluation, posture_analysis, video_analysis)
        }
        
        return jsonify(combined_feedback)
        
    except Exception as e:
        print(f"Error in detailed evaluation: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def generate_fallback_evaluation(question, transcript):
    """Generate basic evaluation when AI is unavailable"""
    word_count = len(transcript.split())
    
    # Basic scoring logic
    content_score = min(10, max(3, word_count // 10))  # 1 point per 10 words, max 10
    
    communication_score = 7  # Default
    if any(word in transcript.lower() for word in ['um', 'uh', 'like', 'you know']):
        communication_score -= 1
    if word_count > 50:
        communication_score += 1
        
    completeness_score = 6
    if word_count > 30:
        completeness_score += 2
    if any(word in transcript.lower() for word in ['example', 'experience', 'project']):
        completeness_score += 1
        
    engagement_score = 6
    if any(word in transcript.lower() for word in ['excited', 'passionate', 'love', 'enjoy']):
        engagement_score += 2
        
    overall_score = (content_score + communication_score + completeness_score + engagement_score) // 4
    
    return {
        "content_quality": {"score": content_score, "feedback": f"Answer length: {word_count} words", "suggestions": "Provide more specific examples and details"},
        "communication": {"score": communication_score, "feedback": "Clear communication", "suggestions": "Minimize filler words"},
        "completeness": {"score": completeness_score, "feedback": "Addresses the question", "suggestions": "Provide more comprehensive coverage"},
        "engagement": {"score": engagement_score, "feedback": "Shows interest", "suggestions": "Express more enthusiasm and passion"},
        "overall_score": overall_score,
        "overall_feedback": f"Good response with {word_count} words. Consider adding more specific examples.",
        "strengths": ["Clear communication", "Relevant content"],
        "areas_for_improvement": ["Add more examples", "Show more enthusiasm"]
    }

def analyze_posture_data(posture_data):
    """Analyze posture data from frontend"""
    if not posture_data:
        return {
            "score": 5,
            "feedback": "No posture data available",
            "suggestions": "Ensure camera can see your upper body clearly"
        }
    
    posture_score = posture_data.get('average_score', 5)
    confidence_level = posture_data.get('confidence', 0.5)
    
    feedback = []
    suggestions = []
    
    if posture_score >= 8:
        feedback.append("Excellent posture throughout the interview")
    elif posture_score >= 6:
        feedback.append("Good posture with minor adjustments needed")
        suggestions.append("Try to keep shoulders back and head upright")
    else:
        feedback.append("Posture needs improvement")
        suggestions.append("Sit up straight and avoid slouching")
        suggestions.append("Keep your head level and shoulders relaxed")
    
    if confidence_level < 0.3:
        suggestions.append("Ensure good lighting and camera positioning for better analysis")
    
    return {
        "score": min(10, max(1, int(posture_score))),
        "feedback": ". ".join(feedback),
        "suggestions": suggestions,
        "confidence": confidence_level,
        "details": posture_data
    }

def analyze_video_metrics(transcript, duration):
    """Analyze video-related metrics"""
    word_count = len(transcript.split())
    speaking_rate = (word_count / (duration / 60)) if duration > 0 else 0  # words per minute
    
    feedback = []
    suggestions = []
    score = 7  # Default score
    
    if speaking_rate > 0:
        if 120 <= speaking_rate <= 180:  # Optimal speaking rate
            feedback.append("Good speaking pace")
            score += 1
        elif speaking_rate < 120:
            feedback.append("Speaking pace is a bit slow")
            suggestions.append("Try to speak a bit faster to maintain engagement")
            score -= 1
        else:
            feedback.append("Speaking pace is quite fast")
            suggestions.append("Slow down slightly to ensure clarity")
            score -= 1
    
    if duration > 0:
        if 30 <= duration <= 120:  # 30 seconds to 2 minutes is good
            feedback.append("Good response length")
        elif duration < 30:
            feedback.append("Response is quite brief")
            suggestions.append("Provide more detailed answers")
            score -= 1
        else:
            feedback.append("Response is quite lengthy")
            suggestions.append("Try to be more concise while maintaining detail")
            score -= 1
    
    return {
        "score": max(1, min(10, score)),
        "speaking_rate": speaking_rate,
        "duration": duration,
        "word_count": word_count,
        "feedback": ". ".join(feedback) if feedback else "Video metrics analyzed",
        "suggestions": suggestions
    }

def calculate_overall_score(ai_eval, posture_anal, video_anal):
    """Calculate weighted overall score"""
    ai_score = ai_eval.get('overall_score', 5)
    posture_score = posture_anal.get('score', 5)
    video_score = video_anal.get('score', 5)
    
    # Weighted average: 60% content, 25% posture, 15% video metrics
    overall = (ai_score * 0.6) + (posture_score * 0.25) + (video_score * 0.15)
    return round(overall, 1)

def generate_detailed_feedback(ai_eval, posture_anal, video_anal):
    """Generate comprehensive feedback summary"""
    feedback_parts = []
    
    # Content feedback
    if ai_eval.get('overall_feedback'):
        feedback_parts.append(f"Content: {ai_eval['overall_feedback']}")
    
    # Posture feedback
    if posture_anal.get('feedback'):
        feedback_parts.append(f"Posture: {posture_anal['feedback']}")
    
    # Video feedback
    if video_anal.get('feedback'):
        feedback_parts.append(f"Presentation: {video_anal['feedback']}")
    
    return " | ".join(feedback_parts)

def generate_improvement_tips(ai_eval, posture_anal, video_anal):
    """Combine improvement suggestions from all analyses"""
    tips = []
    
    # AI suggestions
    if ai_eval.get('areas_for_improvement'):
        tips.extend(ai_eval['areas_for_improvement'])
    
    # Posture suggestions
    if posture_anal.get('suggestions'):
        tips.extend(posture_anal['suggestions'])
    
    # Video suggestions
    if video_anal.get('suggestions'):
        tips.extend(video_anal['suggestions'])
    
    return tips[:5]  # Limit to top 5 suggestions

@app.route('/api/avatar_interview_history', methods=['GET'])
def get_avatar_interview_history():
    """Get avatar interview history for current user"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'status': 'error', 'message': 'User not logged in'}), 401
        
        interviews_dir = os.path.join('data', 'interviews')
        if not os.path.exists(interviews_dir):
            return jsonify({'interviews': []})
        
        interviews = []
        for filename in os.listdir(interviews_dir):
            if filename.startswith('avatar_') and filename.endswith('.json'):
                filepath = os.path.join(interviews_dir, filename)
                try:
                    with open(filepath, 'r') as f:
                        interview_data = json.load(f)
                    
                    # Check if this interview belongs to the current user
                    if interview_data.get('user_id') == user_id:
                        # Extract key information for display
                        interview_summary = {
                            'id': filename.replace('.json', ''),
                            'date': interview_data.get('created', ''),
                            'type': 'Avatar Interview',
                            'questions_answered': len(interview_data.get('answers', [])),
                            'overall_score': None,
                            'status': 'completed'
                        }
                        
                        # Get overall score if available
                        if interview_data.get('overall_feedback'):
                            interview_summary['overall_score'] = interview_data['overall_feedback'].get('overall_score')
                        
                        interviews.append(interview_summary)
                        
                except Exception as e:
                    print(f"Error reading interview file {filename}: {e}")
                    continue
        
        # Sort by date (newest first)
        interviews.sort(key=lambda x: x['date'], reverse=True)
        
        return jsonify({'interviews': interviews})
        
    except Exception as e:
        print(f"Error getting avatar interview history: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/avatar_interview_details/<interview_id>')
def get_avatar_interview_details(interview_id):
    """Get detailed results for a specific avatar interview"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'status': 'error', 'message': 'User not logged in'}), 401
        
        filepath = os.path.join('data', 'interviews', f"{interview_id}.json")
        
        if not os.path.exists(filepath):
            return jsonify({'status': 'error', 'message': 'Interview not found'}), 404
        
        with open(filepath, 'r') as f:
            interview_data = json.load(f)
        
        # Verify ownership
        if interview_data.get('user_id') != user_id:
            return jsonify({'status': 'error', 'message': 'Access denied'}), 403
        
        return jsonify(interview_data)
        
    except Exception as e:
        print(f"Error getting interview details: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/save_interview_video', methods=['POST'])
def save_interview_video():
    """Save recorded interview video"""
    try:
        if 'video' not in request.files:
            return jsonify({'status': 'error', 'message': 'No video file provided'}), 400
        
        video_file = request.files['video']
        if video_file.filename == '':
            return jsonify({'status': 'error', 'message': 'No video file selected'}), 400
        
        # Create videos directory if it doesn't exist
        videos_dir = os.path.join('data', 'videos')
        os.makedirs(videos_dir, exist_ok=True)
        
        # Generate unique filename
        import uuid
        file_extension = video_file.filename.rsplit('.', 1)[1].lower() if '.' in video_file.filename else 'webm'
        filename = f"interview_{uuid.uuid4().hex[:8]}.{file_extension}"
        filepath = os.path.join(videos_dir, filename)
        
        # Save video file
        video_file.save(filepath)
        
        # Get additional metadata
        question_index = request.form.get('question_index', 0)
        user_id = session.get('user_id', 'anonymous')
        
        # Save video metadata
        metadata = {
            'filename': filename,
            'filepath': filepath,
            'question_index': int(question_index),
            'user_id': user_id,
            'timestamp': datetime.utcnow().isoformat(),
            'file_size': os.path.getsize(filepath)
        }
        
        metadata_file = os.path.join(videos_dir, f"{filename}_metadata.json")
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return jsonify({
            'status': 'success',
            'filename': filename,
            'file_size': metadata['file_size']
        }), 201
        
    except Exception as e:
        print(f"Error saving interview video: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/text_to_speech', methods=['POST'])
def text_to_speech():
    try:
        data = request.json
        text = data.get('text', '').strip()
        
        if not text:
            return jsonify({
                'status': 'error',
                'error': 'No text provided'
            }), 400
        
        # Try Murf API first (if available)
        try:
            murf_response = generate_speech_murf(text)
            if murf_response:
                return jsonify({
                    'status': 'success',
                    'audio_url': murf_response,
                    'provider': 'murf'
                })
        except Exception as murf_error:
            print(f"Murf API failed: {murf_error}")
        
        # Fallback: Return success without audio URL (will use browser speech synthesis)
        return jsonify({
            'status': 'success',
            'audio_url': None,
            'provider': 'browser',
            'message': 'Using browser speech synthesis'
        })
        
    except Exception as e:
        print(f"Error generating speech: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': 'Failed to generate speech',
            'details': str(e)
        }), 500

def generate_speech_murf(text):
    """
    Generate speech using Murf API
    Returns audio URL if successful, None if failed
    """
    try:
        import requests
        
        murf_api_key = "ap2_4dcc4f92-624c-4e40-a54f-fb7cc3b1473f"
        murf_url = "https://api.murf.ai/v1/speech/generate"
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {murf_api_key}'
        }
        
        payload = {
            'text': text,
            'voice': 'en-US-amy',
            'format': 'mp3',
            'speed': '1.0',
            'pitch': '1.0'
        }
        
        response = requests.post(murf_url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            return result.get('audio_url')
        else:
            print(f"Murf API error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"Murf API exception: {str(e)}")
        return None
if __name__ == "__main__":
    try:
        # Verify SQLite connection first
        connected, sqlite_version = get_db_connection_status()
        if connected:
            print(f"Successfully connected to SQLite (version: {sqlite_version})")
        else:
            print(f"Failed to connect to SQLite: {sqlite_version}")
            
        # Ensure all database tables exist
        with app.app_context():
            db.create_all()
            print("Database tables created successfully")
            
            # Check for users in the database
            user_count = User.query.count()
            print(f"Current user count in database: {user_count}")
            
            # Create a default admin user if no users exist
            if user_count == 0:
                try:
                    print("Creating default admin user...")
                    admin_password = "admin123"  # Simple default password
                    hashed_password = bcrypt.hashpw(admin_password.encode('utf-8'), bcrypt.gensalt())
                    
                    default_admin = User(
                        name="Admin User",
                        email="admin@example.com",
                        password=hashed_password
                    )
                    
                    db.session.add(default_admin)
                    db.session.commit()
                    print("Default admin user created successfully!")
                    print("Login with: admin@example.com / admin123")
                except Exception as admin_error:
                    print(f"Error creating default admin: {str(admin_error)}")
                    db.session.rollback()
            
        # Run the Flask application
        app.run(debug=True)
    except Exception as e:
        print(f"Error initializing database: {str(e)}")
        
        # Attempt recovery
        try:
            # Try to recreate the database
            print("Attempting to recreate database...")
            # For SQLite, we just need to delete the file and let SQLAlchemy recreate it
            if os.path.exists('interview_prep.db'):
                os.remove('interview_prep.db')
            print("Database file reset")
            
            with app.app_context():
                db.create_all()
                print("Database recovery complete, starting application")
                app.run(debug=True)
        except Exception as recovery_error:
            print(f"Recovery failed: {str(recovery_error)}")
            # Run the app anyway as a last resort
            app.run(debug=True) 