from flask import Flask, render_template, redirect, url_for, flash, request, session, jsonify, abort
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, SelectField, DateField
from wtforms.validators import DataRequired, Email
import bcrypt
from flask_sqlalchemy import SQLAlchemy
import random
from datetime import datetime
import os
from werkzeug.utils import secure_filename
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = '\x8bO|\xc3\xe3\x99&h%\xb9\xebU\xf9\x1eb\xee$\x85\xf1Z\x95\x85\xe3\xdd'

# Add these configurations after the existing app configurations
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'wav', 'mp3', 'ogg', 'm4a'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create uploads directory if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Configure Gemini API
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.LargeBinary, nullable=False)
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
            
            try:
                # Generate questions using the new Gemini model
                prompt = f"""
                You are an expert interviewer for {target_company}. Generate {num_questions} interview questions
                for a {experience_level} {job_role}. The questions should be challenging and relevant
                to the job role, including technical and behavioral aspects.

                Format each question as:
                Q1: [Question text]
                Q2: [Question text]
                Q3: [Question text]
                ...
                """

                model = genai.GenerativeModel("gemini-1.5-flash")
                response = model.generate_content(prompt)
                
                # Extract questions from the response
                questions_text = response.text
                questions = []
                for line in questions_text.split('\n'):
                    if line.strip() and (line.startswith('Q') or line[0].isdigit()):
                        # Remove question number and clean the text
                        question = line.split(':', 1)[1].strip() if ':' in line else line.strip()
                        questions.append(question)
                
                if not questions:
                    flash("Failed to generate questions. Please try again.", "error")
                    return redirect(url_for('ai_interview'))
                
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
                
                # Store interview data in session for the question bank
                session['current_interview'] = {
                    'id': ai_interview.id,
                    'questions': questions,
                    'job_role': job_role,
                    'experience_level': experience_level,
                    'target_company': target_company
                }
                
                return redirect(url_for('question_bank'))
            
            except Exception as e:
                print(f"Error generating questions: {str(e)}")
                flash("An error occurred while generating questions. Please try again.", "error")
                return redirect(url_for('ai_interview'))
        
        elif 'submit_answer' in request.form:
            interview_id = request.form.get('interview_id')
            question = request.form.get('question')
            answer = request.form.get('answer')
            
            # Get the interview data
            ai_interview = AIInterview.query.get(interview_id)
            if not ai_interview:
                return jsonify({
                    'status': 'error',
                    'message': 'Interview session not found.'
                })
            
            # Evaluate answer using Gemini
            prompt = f"""
            As an expert interviewer at {ai_interview.target_company}, evaluate the following answer:

            Question: {question}
            Answer: {answer}

            Provide a detailed evaluation in this format:
            1. Score (out of 10)
            2. Key Strengths
            3. Areas for Improvement
            4. Specific Suggestions
            """

            try:
                model = genai.GenerativeModel("gemini-1.5-flash")
                response = model.generate_content(prompt)
                feedback = response.text
                
                # Update AI interview with answer and feedback
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
            except Exception as e:
                print(f"Error evaluating answer: {str(e)}")
                return jsonify({
                    'status': 'error',
                    'message': 'Failed to evaluate answer. Please try again.'
                })
    
    # Get user's AI interview history
    ai_interviews = AIInterview.query.filter_by(user_id=session['user_id']).order_by(AIInterview.date.desc()).all()
    return render_template('ai_interview.html', ai_interviews=ai_interviews)

@app.route('/question_bank')
def question_bank():
    if 'user_id' not in session or 'current_interview' not in session:
        flash("Please start an interview session first.", "warning")
        return redirect(url_for('ai_interview'))
    
    interview_data = session['current_interview']
    return render_template('question_bank.html', interview=interview_data)

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

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
