from flask import Flask, render_template, redirect, url_for, flash, request, session, jsonify, abort, send_from_directory
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, SelectField, DateField, FileField
from wtforms.validators import DataRequired, Email
import bcrypt
from flask_sqlalchemy import SQLAlchemy
import random
from datetime import datetime
import os
from werkzeug.utils import secure_filename
import google.generativeai as genai
from dotenv import load_dotenv
import sys

# For the career roadmap feature, you might need to install:
# pip install PyMuPDF (for PDF parsing)

# Load environment variables
load_dotenv()

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = '\x8bO|\xc3\xe3\x99&h%\xb9\xebU\xf9\x1eb\xee$\x85\xf1Z\x95\x85\xe3\xdd'

# Add these configurations after the existing app configurations
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
PROFILE_PHOTOS_FOLDER = os.path.join(os.getcwd(), 'static', 'profile_photos')
ALLOWED_EXTENSIONS = {'wav', 'mp3', 'ogg', 'm4a'}
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROFILE_PHOTOS_FOLDER'] = PROFILE_PHOTOS_FOLDER

# Create uploads directory if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROFILE_PHOTOS_FOLDER, exist_ok=True)
print(f"Profile photos folder: {PROFILE_PHOTOS_FOLDER}")

# Configure Gemini API
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

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
    performance = db.Column(db.Integer, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

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
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        new_user = User(name=name, email=email, password=hashed_password)
        try:
            db.session.add(new_user)
            db.session.commit()
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for('login'))
        except Exception as e:
            flash("An error occurred while registering. Please try again.", "danger")
            print("Database Error:", e)
            db.session.rollback()
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        user = User.query.filter_by(email=email).first()
        if user and bcrypt.checkpw(password.encode('utf-8'), user.password):
            session['user_id'] = user.id
            flash("Login successful!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Login unsuccessful. Please check your email and password.", "danger")
    return render_template('login.html', form=form)

@app.route('/resume_template')
def resume_template():
    return render_template('resume_template.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return render_template('dashboard.html', user=None, interviews=[], stats={
            'total': 0,
            'completed': 0,
            'upcoming': 0,
            'offers': 0,
            'avg_performance': 0
        }, not_logged_in=True)
    
    user = User.query.get(session['user_id'])
    # Get the user's interviews for the dashboard
    interviews = Interview.query.filter_by(user_id=user.id).order_by(Interview.date.desc()).all()
    
    # Calculate some statistics
    completed_interviews = [i for i in interviews if i.status == 'Completed']
    upcoming_interviews = [i for i in interviews if i.status == 'Upcoming']
    offers = [i for i in interviews if i.status == 'Offered']
    
    avg_performance = 0
    if completed_interviews:
        performances = [i.performance for i in completed_interviews if i.performance]
        if performances:
            avg_performance = sum(performances) / len(performances)
    
    stats = {
        'total': len(interviews),
        'completed': len(completed_interviews),
        'upcoming': len(upcoming_interviews),
        'offers': len(offers),
        'avg_performance': round(avg_performance, 1)
    }
    
    return render_template('dashboard.html', user=user, interviews=interviews, stats=stats)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash("You have been logged out successfully.", "info")
    return redirect(url_for('login'))

@app.route('/dsa')
def dsa():
    return render_template('dsa.html')

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

@app.route('/ai_interview', methods=['GET', 'POST'])
def ai_interview():
    if 'user_id' not in session:
        flash("Please log in to access the AI Interview feature.", "warning")
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        if 'start_interview' in request.form:
            job_role = request.form.get('job_role')
            experience_level = request.form.get('experience_level')
            target_company = request.form.get('target_company')
            num_questions = int(request.form.get('num_questions', 5))
            
            # Generate questions using Gemini
            prompt = f"""
            You are an expert interviewer at {target_company}. Generate exactly {num_questions} interview questions
            for a {experience_level} {job_role}. Ensure they assess both technical and behavioral skills.

            Provide the questions in this exact format:
            1. [First Question]
            2. [Second Question]
            3. [Third Question]
            ...
            """

            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)
            questions = response.text.strip().split("\n")
            questions = [q.strip() for q in questions if q.strip()]
            
            # Save AI interview session
            ai_interview = AIInterview(
                job_role=job_role,
                experience_level=experience_level,
                target_company=target_company,
                questions="\n".join(questions),
                user_id=session['user_id']
            )
            db.session.add(ai_interview)
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'questions': questions,
                'interview_id': ai_interview.id
            })
        
        elif 'submit_answer' in request.form:
            interview_id = request.form.get('interview_id')
            question = request.form.get('question')
            answer = request.form.get('answer')
            
            # Evaluate answer using Gemini
            prompt = f"""
            Evaluate the following answer based on clarity, relevance, and accuracy:

            Question: {question}
            Answer: {answer}

            Provide:
            1. A score out of 10
            2. Constructive feedback on how to improve
            """

            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)
            feedback = response.text
            
            # Update AI interview with answer and feedback
            ai_interview = AIInterview.query.get(interview_id)
            if ai_interview:
                current_answers = ai_interview.answers or ""
                current_feedback = ai_interview.feedback or ""
                
                ai_interview.answers = current_answers + f"\nQ: {question}\nA: {answer}\n"
                ai_interview.feedback = current_feedback + f"\nFeedback for '{question}':\n{feedback}\n"
                
                # Calculate average performance
                if ai_interview.performance is None:
                    ai_interview.performance = 0
                
                db.session.commit()
                
                return jsonify({
                    'status': 'success',
                    'feedback': feedback
                })
    
    # Get user's AI interview history
    ai_interviews = AIInterview.query.filter_by(user_id=session['user_id']).order_by(AIInterview.date.desc()).all()
    return render_template('ai_interview.html', ai_interviews=ai_interviews)

@app.route('/transcribe_audio', methods=['POST'])
def transcribe_audio():
    if 'audio' not in request.files:
        return jsonify({'status': 'error', 'message': 'No audio file provided'}), 400
    
    file = request.files['audio']
    if file:
        filename = secure_filename(file.filename or 'recording.wav')
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            # Return a message about browser transcription
            transcribed_text = "Audio transcription will be handled by the browser's speech recognition API."
            
            # Clean up the file after processing
            os.remove(filepath)
            
            return jsonify({
                'status': 'success',
                'transcribed_text': transcribed_text
            })
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500
    
    return jsonify({'status': 'error', 'message': 'Invalid audio file'}), 400

@app.route('/ai_interview/<int:interview_id>/feedback', methods=['GET'])
def get_interview_feedback(interview_id):
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401
    
    ai_interview = AIInterview.query.get_or_404(interview_id)
    if ai_interview.user_id != session['user_id']:
        return jsonify({'status': 'error', 'message': 'Not authorized'}), 403
    
    feedback_html = "<h4>Questions and Answers</h4>"
    
    if ai_interview.questions and ai_interview.answers:
        questions = ai_interview.questions.split("\n")
        answers_feedback = ai_interview.answers.split("\nQ: ")
        
        for i, question in enumerate(questions):
            if i == 0:
                answer_block = answers_feedback[0] if answers_feedback else "No answer provided"
            else:
                try:
                    answer_block = "Q: " + answers_feedback[i]
                except IndexError:
                    answer_block = "No answer provided"
            
            feedback_html += f"<div class='question-block'><p><strong>Question {i+1}:</strong> {question}</p>"
            feedback_html += f"<p><strong>Your Answer:</strong></p><p>{answer_block}</p></div>"
    
    feedback_html += "<h4>Feedback</h4>"
    if ai_interview.feedback:
        feedback_html += f"<div class='feedback-block'>{ai_interview.feedback}</div>"
    else:
        feedback_html += "<p>No feedback available</p>"
    
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
    roadmap_result = None
    
    if request.method == 'POST':
        role = request.form.get('role')
        experience = request.form.get('experience')
        company = request.form.get('company')
        resume_text = ""
        
        # Check if a resume was uploaded
        if 'resume' in request.files:
            file = request.files['resume']
            if file and file.filename:
                # Save the resume temporarily
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                
                # Extract text from PDF if it's a PDF file
                if filename.lower().endswith('.pdf'):
                    try:
                        import fitz  # PyMuPDF for PDF parsing
                        doc = fitz.open(filepath)
                        for page in doc:
                            resume_text += page.get_text()
                        doc.close()
                    except ImportError:
                        flash("PyMuPDF is not installed. Unable to parse PDF resume.", "warning")
                        resume_text = "PDF parsing unavailable"
                else:
                    # Read text file directly
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        resume_text = f.read()
                
                # Clean up the file after processing
                os.remove(filepath)
        
        # Generate the roadmap using Gemini
        prompt = f"""
        Generate a detailed, personalized career roadmap for a {role} with {experience} years of experience at {company}.
        Include:
        - Key learning milestones
        - Daily tasks for growth
        - Skills to master
        - Career tips & recommendations
        """
        
        if resume_text:
            prompt += f"\n\nHere is the resume for deeper personalization:\n{resume_text}"
        
        try:
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)
            roadmap_result = response.text
        except Exception as e:
            flash(f"Error generating roadmap: {str(e)}", "danger")
            return redirect(url_for('career_roadmap'))
    
    return render_template('career_roadmap.html', roadmap=roadmap_result)

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

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True) 