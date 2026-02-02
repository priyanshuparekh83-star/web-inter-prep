import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GENAI_API_KEY",'AIzaSyDhj5eznHfo9Dt80Ptvm_pi-LVqd_2i8oc'))
genai.configure(api_key='AIzaSyDhj5eznHfo9Dt80Ptvm_pi-LVqd_2i8oc')

def generate_interview_questions(job_role, experience_level, target_company, num_questions):
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

    # Ensure correct numbering and clean formatting
    questions = response.text.strip().split("\n")
    questions = [q.strip() for q in questions if q.strip()]  # Remove empty lines
    return questions[:num_questions]  # Ensure the correct number of questions

def evaluate_response(question, user_answer):
    prompt = f"""
    Evaluate the following answer based on clarity, relevance, and accuracy:

    Question: {question}
    Answer: {user_answer}

    Provide:
    1. A score out of 10
    2. Constructive feedback on how to improve
    """

    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    return response.text

def transcribe_audio(audio_file):
    # Since we're using the browser's built-in speech recognition,
    # we'll just return a placeholder message
    return "Audio transcription will be handled by the browser's speech recognition API." 