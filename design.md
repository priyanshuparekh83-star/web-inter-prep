# Technical Design Document - WEB-INTER-PREP

## Project Overview
**Project Name:** WEB-INTER-PREP  
**Version:** 1.0  
**Date:** January 2025  
**Type:** Interview Preparation Platform  

### Executive Summary
Comprehensive technical design for an AI-powered interview preparation platform built with Flask, featuring intelligent question generation, avatar-based interviews, and advanced analytics.

---

## 1. System Architecture

### 1.1 High-Level Architecture
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Client Layer  │    │  Application    │    │   Data Layer    │
│                 │    │     Layer       │    │                 │
│ • Web Browser   │◄──►│ • Flask App     │◄──►│ • SQLite/MySQL  │
│ • Mobile Device │    │ • API Routes    │    │ • File Storage  │
│ • JavaScript    │    │ • Business      │    │ • Session Store │
│                 │    │   Logic         │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │ External APIs   │
                       │                 │
                       │ • Google Gemini │
                       │ • D-ID Talk     │
                       │ • Web Speech    │
                       └─────────────────┘
```

### 1.2 Technology Stack
| Layer | Technology | Version | Purpose |
|-------|------------|---------|---------|
| Backend | Flask | 3.0.2 | Web framework |
| Database ORM | SQLAlchemy | 2.0.28 | Database abstraction |
| Database | SQLite/MySQL | 3.50+/8.0+ | Data persistence |
| AI Engine | Google Gemini | 0.3.2 | Question generation |
| Avatar API | D-ID Talk | Latest | Avatar interviews |
| Frontend | HTML5, CSS3, Bootstrap 5 | Latest | User interface |
| Authentication | bcrypt | 4.1.2 | Password hashing |
| File Processing | PyPDF2, Pillow | Latest | Document handling |
| Deployment | Gunicorn, Render | 21.2.0 | Production server |

---

## 2. Database Design

### 2.1 Core Database Models

#### Users Table
```sql
CREATE TABLE user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password BLOB NOT NULL,
    profile_photo VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### Interviews Table
```sql
CREATE TABLE interview (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company VARCHAR(100) NOT NULL,
    position VARCHAR(100) NOT NULL,
    date DATETIME NOT NULL,
    notes TEXT,
    status VARCHAR(20) DEFAULT 'Upcoming',
    performance INTEGER,
    user_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id)
);
```

#### AI Interview Sessions
```sql
CREATE TABLE ai_interview_session (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    position VARCHAR(100) NOT NULL,
    questions_asked INTEGER DEFAULT 0,
    questions_answered INTEGER DEFAULT 0,
    average_score FLOAT DEFAULT 0.0,
    completed BOOLEAN DEFAULT FALSE,
    session_data TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    FOREIGN KEY (user_id) REFERENCES user(id)
);
```

#### Avatar Interview Sessions
```sql
CREATE TABLE avatar_interview_session (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    job_role VARCHAR(100) NOT NULL,
    company VARCHAR(100),
    experience_level VARCHAR(50),
    questions_count INTEGER DEFAULT 0,
    questions_completed INTEGER DEFAULT 0,
    average_score FLOAT DEFAULT 0.0,
    completed BOOLEAN DEFAULT FALSE,
    video_recorded BOOLEAN DEFAULT FALSE,
    posture_score FLOAT,
    session_file VARCHAR(255),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id)
);
```
#### Additional Tracking Tables
```sql
-- DSA Practice Sessions
CREATE TABLE dsa_practice_session (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    problem_title VARCHAR(200) NOT NULL,
    problem_category VARCHAR(100),
    difficulty VARCHAR(20),
    solved BOOLEAN DEFAULT FALSE,
    attempts INTEGER DEFAULT 1,
    time_taken INTEGER,
    solution_code TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id)
);

-- English Booster Sessions
CREATE TABLE english_booster_session (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    session_type VARCHAR(50),
    exercises_completed INTEGER DEFAULT 0,
    score FLOAT DEFAULT 0.0,
    improvement_areas TEXT,
    duration_minutes INTEGER,
    completed BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id)
);

-- Company Preparation Sessions
CREATE TABLE company_prep_session (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    company_name VARCHAR(100) NOT NULL,
    prep_type VARCHAR(50),
    topics_covered TEXT,
    progress_percentage FLOAT DEFAULT 0.0,
    completed BOOLEAN DEFAULT FALSE,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id)
);

-- Resume Uploads
CREATE TABLE resume_upload (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255),
    file_size INTEGER,
    file_type VARCHAR(50),
    analysis_score FLOAT,
    suggestions TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES user(id)
);
```

### 2.2 Data Relationships
- One-to-Many: User → Interviews, AI Interviews, Sessions
- Foreign Keys: All session tables reference user.id
- JSON Storage: Complex data stored as JSON in TEXT fields
- Indexing: Primary keys, foreign keys, and email field indexed

---

## 3. Application Architecture
### 3.1 Flask Application Structure
```
app.py (Main Application)
├── Configuration
│   ├── Database setup (SQLite/MySQL)
│   ├── API key configuration
│   ├── File upload settings
│   └── Session management
├── Models (SQLAlchemy)
│   ├── User, Interview, AIInterview
│   ├── Session tracking models
│   └── Relationship definitions
├── Forms (WTForms)
│   ├── RegistrationForm, LoginForm
│   ├── InterviewForm
│   └── Validation rules
├── Routes
│   ├── Authentication routes
│   ├── Dashboard and profile
│   ├── Interview management
│   ├── AI interview features
│   ├── Avatar interview system
│   ├── English skills modules
│   ├── Career development
│   └── API endpoints
└── Helper Functions
    ├── Database utilities
    ├── File handling
    ├── Statistics calculation
    └── AI integration
```

### 3.2 Route Organization

#### Authentication Routes
```python
@app.route('/register', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
@app.route('/logout')
```

#### Core Application Routes
```python
@app.route('/')                    # Landing page
@app.route('/dashboard')           # Main dashboard
@app.route('/interview_progress')  # Interview tracking
@app.route('/ai_interview')        # AI interview practice
@app.route('/avatar_interview')    # Avatar interviews
@app.route('/english_booster')     # English skills
@app.route('/career_roadmap')      # Career planning
@app.route('/company_prep')        # Company preparation
@app.route('/dsa')                 # DSA practice
@app.route('/resources')           # Learning resources
```

#### API Routes
```python
@app.route('/api/generate_question', methods=['POST'])
@app.route('/api/evaluate_answer_detailed', methods=['POST'])
@app.route('/api/create_avatar_talk', methods=['POST'])
@app.route('/api/save_interview_video', methods=['POST'])
@app.route('/api/check_grammar', methods=['POST'])
@app.route('/api/track_*', methods=['POST'])  # Various tracking endpoints
```

### 3.3 Configuration Management
```python
class Config:
    # API Keys
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    
    # Database
    if os.environ.get('RENDER'):
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    else:
        SQLALCHEMY_DATABASE_URI = 'sqlite:///interview_prep.db'
    
    # File Upload
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
    PROFILE_PHOTOS_FOLDER = os.path.join(os.getcwd(), 'static', 'profile_photos')
    
    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY')
```

---

## 4. Frontend Design
### 4.1 User Interface Architecture
```
Frontend Structure
├── Templates (Jinja2)
│   ├── layout.html (Base template)
│   ├── Authentication
│   │   ├── login.html
│   │   └── register.html
│   ├── Core Features
│   │   ├── dashboard.html
│   │   ├── ai_interview.html
│   │   ├── avatar_interview.html
│   │   ├── english_booster.html
│   │   └── career_roadmap.html
│   └── Management
│       ├── interview_progress.html
│       ├── company_prep.html
│       └── resources.html
├── Static Assets
│   ├── CSS
│   │   ├── style.css (Main styles)
│   │   ├── dashboard.css
│   │   ├── ai_interview.css
│   │   └── avatar_interview.css
│   ├── JavaScript
│   │   ├── script.js (Main functionality)
│   │   └── avatar_interview.js
│   ├── Images
│   │   ├── hero-image.svg
│   │   ├── pattern.svg
│   │   └── companies/ (Company logos)
│   └── Resources
│       └── PDF files (Learning materials)
```

### 4.2 Responsive Design System
**Breakpoints**
```css
/* Mobile First Approach */
@media (min-width: 576px) { /* Small devices */ }
@media (min-width: 768px) { /* Medium devices */ }
@media (min-width: 992px) { /* Large devices */ }
@media (min-width: 1200px) { /* Extra large devices */ }
```

**Component Design**
- Navigation: Responsive navbar with mobile hamburger menu
- Cards: Bootstrap card components for feature sections
- Forms: Styled forms with validation feedback
- Modals: Interactive dialogs for profile management
- Progress Bars: Visual progress indicators
- Charts: Statistics visualization (custom CSS)

### 4.3 JavaScript Architecture
**Main Script (script.js)**
```javascript
// DOM Content Loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeAnimations();
    setupEventListeners();
    loadUserData();
});

// Feature Modules
const InterviewModule = {
    generateQuestion: async function() { /* API call */ },
    evaluateAnswer: async function() { /* API call */ },
    updateProgress: function() { /* UI update */ }
};

const AvatarModule = {
    initializeCamera: function() { /* Camera setup */ },
    startRecording: function() { /* Video recording */ },
    analyzePosture: function() { /* Posture detection */ }
};
```

---

## 5. AI Integration Design
### 5.1 Google Gemini Integration

**Question Generation**
```python
def generate_interview_questions(job_role, experience_level, target_company, num_questions):
    prompt = f"""
    You are an expert interviewer at {target_company}. 
    Generate exactly {num_questions} interview questions
    for a {experience_level} {job_role}.
    Ensure they assess both technical and behavioral skills.
    """
    
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    return parse_questions(response.text)
```

**Answer Evaluation**
```python
def evaluate_response(question, user_answer):
    prompt = f"""
    Evaluate this interview answer:
    Question: {question}
    Answer: {user_answer}
    
    Provide:
    1. Score (1-10)
    2. Strengths
    3. Areas for improvement
    4. Specific suggestions
    """
    
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    return parse_evaluation(response.text)
```

### 5.2 D-ID Avatar Integration

**Avatar Talk API**
```python
def create_avatar_talk(script_text, avatar_id="default"):
    headers = {
        'Authorization': f'Basic {DID_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'script': {
            'type': 'text',
            'input': script_text
        },
        'source_url': avatar_id
    }
    
    response = requests.post(DID_TALK_URL, json=payload, headers=headers)
    return response.json()
```

### 5.3 Speech Recognition Integration

**Web Speech API (Primary)**
```javascript
const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
recognition.continuous = true;
recognition.interimResults = true;
recognition.lang = 'en-US';

recognition.onresult = function(event) {
    const transcript = event.results[event.results.length - 1][0].transcript;
    processTranscript(transcript);
};
```

**Whisper Fallback**
```python
import whisper

def transcribe_audio_whisper(audio_file):
    model = whisper.load_model("base")
    result = model.transcribe(audio_file)
    return result["text"]
```

---

## 6. Security Design
### 6.1 Authentication Security

**Password Hashing**
```python
import bcrypt

def hash_password(password):
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed)
```

**Session Management**
```python
@app.before_request
def check_authentication():
    protected_routes = ['dashboard', 'ai_interview', 'avatar_interview']
    if request.endpoint in protected_routes and 'user_id' not in session:
        return redirect(url_for('login'))
```

### 6.2 Input Validation

**Form Validation (WTForms)**
```python
class RegistrationForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Register")
```

**File Upload Security**
```python
ALLOWED_EXTENSIONS = {'wav', 'mp3', 'ogg', 'm4a', 'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def secure_upload(file):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        return filename
    return None
```

### 6.3 API Security

**Rate Limiting**
```python
from functools import wraps
import time

def rate_limit(max_requests=10, window=60):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Rate limiting logic
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/api/generate_question', methods=['POST'])
@rate_limit(max_requests=5, window=60)
def generate_question():
    # API logic
    pass
```

**CSRF Protection**
```python
from flask_wtf.csrf import CSRFProtect
csrf = CSRFProtect(app)
```

---

## 7. File Management Design
### 7.1 File Storage Structure
```
Project Root
├── uploads/                    # User uploads
│   ├── audio/                 # Audio recordings
│   ├── videos/                # Interview videos
│   └── documents/             # Resume uploads
├── static/
│   ├── profile_photos/        # User profile pictures
│   ├── resources/             # Learning materials
│   ├── css/                   # Stylesheets
│   ├── js/                    # JavaScript files
│   └── images/                # Static images
└── data/
    └── interviews/            # Interview session data
```

### 7.2 File Upload Handling

**Profile Photo Upload**
```python
@app.route('/upload_profile_photo', methods=['POST'])
def upload_profile_photo():
    if 'file' not in request.files:
        return jsonify({'error': 'No file selected'})
    
    file = request.files['file']
    if file and allowed_image(file.filename):
        filename = secure_filename(file.filename)
        user_id = session['user_id']
        filename = f"user_{user_id}_{filename}"
        
        file_path = os.path.join(app.config['PROFILE_PHOTOS_FOLDER'], filename)
        file.save(file_path)
        
        # Update user profile
        user = User.query.get(user_id)
        user.profile_photo = filename
        db.session.commit()
        
        return jsonify({'success': True, 'filename': filename})
```

**Video Recording Save**
```python
@app.route('/api/save_interview_video', methods=['POST'])
def save_interview_video():
    try:
        video_data = request.files['video']
        session_id = request.form.get('session_id')
        
        filename = f"interview_{session_id}_{int(time.time())}.webm"
        video_path = os.path.join('data', 'interviews', filename)
        
        video_data.save(video_path)
        
        return jsonify({
            'success': True,
            'video_path': video_path,
            'message': 'Video saved successfully'
        })
    except Exception as e:
        return jsonify({'error': str(e)})
```

---

## 8. Performance Optimization
### 8.1 Database Optimization

**Connection Pooling**
```python
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 3600,
    'pool_size': 10,
    'max_overflow': 20
}
```

**Query Optimization**
```python
# Eager loading to prevent N+1 queries
def get_user_interviews(user_id):
    return Interview.query.filter_by(user_id=user_id)\
                         .options(joinedload(Interview.user))\
                         .all()

# Pagination for large datasets
def get_paginated_interviews(user_id, page=1, per_page=10):
    return Interview.query.filter_by(user_id=user_id)\
                         .paginate(page=page, per_page=per_page)
```

### 8.2 Caching Strategy

**Session-based Caching**
```python
@app.route('/dashboard')
def dashboard():
    cache_key = f"user_stats_{session['user_id']}"
    
    if cache_key in session:
        stats = session[cache_key]
    else:
        stats = get_comprehensive_stats(session['user_id'])
        session[cache_key] = stats
    
    return render_template('dashboard.html', stats=stats)
```

**Static Asset Optimization**
```html
<!-- CSS/JS Minification and Compression -->
<link rel="stylesheet" href="{{ url_for('static', filename='css/style.min.css') }}">
<script src="{{ url_for('static', filename='js/script.min.js') }}"></script>

<!-- Image Optimization -->
<img src="{{ url_for('static', filename='images/hero-image.webp') }}" 
     alt="Hero Image" loading="lazy">
```

### 8.3 API Response Optimization

**Response Compression**
```python
from flask import jsonify, request
import gzip

def compress_response(response):
    if 'gzip' in request.headers.get('Accept-Encoding', ''):
        response.data = gzip.compress(response.data)
        response.headers['Content-Encoding'] = 'gzip'
    return response
```

**Async Processing for Heavy Operations**
```python
import threading

def generate_career_roadmap_async(user_id, job_role, experience):
    def background_task():
        # Heavy AI processing
        roadmap = generate_detailed_roadmap(job_role, experience)
        # Save to database
        save_roadmap(user_id, roadmap)
    
    thread = threading.Thread(target=background_task)
    thread.start()
    
    return jsonify({'status': 'processing', 'message': 'Roadmap generation started'})
```

---

## 9. Error Handling and Logging
### 9.1 Error Handling Strategy

**Global Error Handlers**
```python
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500

@app.errorhandler(Exception)
def handle_exception(e):
    # Log the error
    app.logger.error(f"Unhandled exception: {str(e)}")
    
    # Return JSON error for API routes
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Internal server error'}), 500
    
    # Return HTML error page for regular routes
    return render_template('errors/500.html'), 500
```

**Database Error Recovery**
```python
def safe_database_operation(operation):
    try:
        result = operation()
        db.session.commit()
        return result
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Database error: {str(e)}")
        
        # Attempt recovery
        try:
            db.create_all()
            app.logger.info("Database tables recreated")
        except Exception as recovery_error:
            app.logger.error(f"Recovery failed: {str(recovery_error)}")
        
        raise e
```

### 9.2 Logging Configuration

**Logging Setup**
```python
import logging
from logging.handlers import RotatingFileHandler

if not app.debug:
    file_handler = RotatingFileHandler('logs/interview_prep.log', 
                                     maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Interview Prep startup')
```

---

## 10. Deployment Architecture
### 10.1 Production Deployment (Render)

**render.yaml Configuration**
```yaml
services:
  - type: web
    name: mock-interview-app
    env: python
    region: oregon
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn app:app
    envVars:
      - key: PYTHON_VERSION
        value: 3.13.0
      - key: FLASK_ENV
        value: production
      - key: DATABASE_URL
        sync: false
      - key: SECRET_KEY
        generateValue: true
      - key: GEMINI_API_KEY
        sync: false
    healthCheckPath: /
    autoDeploy: true
    disk:
      name: uploads
      mountPath: /opt/render/project/src/uploads
```

**Gunicorn Configuration**
```python
# gunicorn.conf.py
import multiprocessing

bind = "0.0.0.0:10000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 120
keepalive = 2
max_requests = 1000
max_requests_jitter = 100
preload_app = True
```

### 10.2 Environment Configuration

**Development Environment**
```bash
# .env.development
FLASK_ENV=development
FLASK_DEBUG=True
DATABASE_URL=sqlite:///interview_prep.db
GEMINI_API_KEY=your_dev_api_key
SECRET_KEY=dev_secret_key
```

**Production Environment**
```bash
# Environment variables set in Render
FLASK_ENV=production
DATABASE_URL=mysql://user:pass@host:port/db
GEMINI_API_KEY=production_api_key
SECRET_KEY=secure_production_key
```

### 10.3 Monitoring and Health Checks

**Health Check Endpoint**
```python
@app.route('/health')
def health_check():
    try:
        # Check database connection
        db.session.execute('SELECT 1')
        
        # Check AI API availability
        test_ai_connection()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '1.0'
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500
```

---

## 11. Key Features Implementation