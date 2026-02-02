#!/usr/bin/env python3
"""
Sample data population script for testing real data tracking
Run this after creating a user account to see the dashboard with real data
"""

from app import app, db
from app import (AIInterviewSession, AvatarInterviewSession, DSAPracticeSession, 
                 EnglishBoosterSession, CompanyPrepSession, ResumeUpload, User)
from datetime import datetime, timedelta
import json
import random

def populate_sample_data(user_id=1):
    """Populate sample data for testing dashboard"""
    with app.app_context():
        try:
            # Check if user exists
            user = User.query.get(user_id)
            if not user:
                print(f"❌ User with ID {user_id} not found. Please register first.")
                return
            
            print(f"📊 Populating sample data for user: {user.name} (ID: {user_id})")
            
            # 1. AI Interview Sessions
            ai_sessions = [
                {"position": "Software Engineer", "questions": 5, "completed": True, "score": 8.5},
                {"position": "Data Scientist", "questions": 4, "completed": True, "score": 7.2},
                {"position": "Frontend Developer", "questions": 6, "completed": False, "score": 0},
            ]
            
            for session_data in ai_sessions:
                session = AIInterviewSession(
                    user_id=user_id,
                    position=session_data["position"],
                    questions_asked=session_data["questions"],
                    questions_answered=session_data["questions"] if session_data["completed"] else 2,
                    average_score=session_data["score"],
                    completed=session_data["completed"],
                    session_data=json.dumps({"sample": True}),
                    created_at=datetime.utcnow() - timedelta(days=random.randint(1, 30))
                )
                db.session.add(session)
            
            # 2. Avatar Interview Sessions
            avatar_sessions = [
                {"role": "Product Manager", "company": "Google", "completed": True, "score": 9.1},
                {"role": "Software Engineer", "company": "Microsoft", "completed": True, "score": 8.7},
                {"role": "Data Analyst", "company": "Amazon", "completed": False, "score": 0},
            ]
            
            for session_data in avatar_sessions:
                session = AvatarInterviewSession(
                    user_id=user_id,
                    job_role=session_data["role"],
                    company=session_data["company"],
                    experience_level="Mid Level",
                    questions_count=5,
                    questions_completed=5 if session_data["completed"] else 2,
                    average_score=session_data["score"],
                    completed=session_data["completed"],
                    video_recorded=session_data["completed"],
                    posture_score=85.5 if session_data["completed"] else None,
                    created_at=datetime.utcnow() - timedelta(days=random.randint(1, 20))
                )
                db.session.add(session)
            
            # 3. DSA Practice Sessions
            dsa_problems = [
                {"title": "Two Sum", "category": "Array", "difficulty": "Easy", "solved": True},
                {"title": "Binary Tree Inorder", "category": "Tree", "difficulty": "Medium", "solved": True},
                {"title": "Merge Sort", "category": "Sorting", "difficulty": "Medium", "solved": True},
                {"title": "Graph DFS", "category": "Graph", "difficulty": "Medium", "solved": True},
                {"title": "Dynamic Programming - Knapsack", "category": "DP", "difficulty": "Hard", "solved": False},
                {"title": "Linked List Reverse", "category": "LinkedList", "difficulty": "Easy", "solved": True},
                {"title": "Binary Search", "category": "Array", "difficulty": "Easy", "solved": True},
                {"title": "Heap Sort", "category": "Heap", "difficulty": "Medium", "solved": False},
            ]
            
            for problem in dsa_problems:
                session = DSAPracticeSession(
                    user_id=user_id,
                    problem_title=problem["title"],
                    problem_category=problem["category"],
                    difficulty=problem["difficulty"],
                    solved=problem["solved"],
                    attempts=1 if problem["solved"] else 2,
                    time_taken=random.randint(15, 60) if problem["solved"] else None,
                    created_at=datetime.utcnow() - timedelta(days=random.randint(1, 15)),
                    solved_at=datetime.utcnow() - timedelta(days=random.randint(1, 15)) if problem["solved"] else None
                )
                db.session.add(session)
            
            # 4. English Booster Sessions
            english_sessions = [
                {"type": "Grammar", "score": 75.5, "exercises": 10},
                {"type": "Speaking", "score": 82.3, "exercises": 8},
                {"type": "Vocabulary", "score": 88.7, "exercises": 15},
                {"type": "Grammar", "score": 85.2, "exercises": 12},
                {"type": "Speaking", "score": 89.1, "exercises": 6},
            ]
            
            for i, session_data in enumerate(english_sessions):
                session = EnglishBoosterSession(
                    user_id=user_id,
                    session_type=session_data["type"],
                    exercises_completed=session_data["exercises"],
                    score=session_data["score"],
                    duration_minutes=random.randint(20, 45),
                    completed=True,
                    created_at=datetime.utcnow() - timedelta(days=random.randint(1, 25)),
                    completed_at=datetime.utcnow() - timedelta(days=random.randint(1, 25))
                )
                db.session.add(session)
            
            # 5. Company Prep Sessions
            company_sessions = [
                {"company": "Google", "type": "Technical", "progress": 85.0},
                {"company": "Microsoft", "type": "Behavioral", "progress": 92.5},
                {"company": "Amazon", "type": "Culture", "progress": 78.0},
                {"company": "Apple", "type": "Technical", "progress": 65.0},
            ]
            
            for session_data in company_sessions:
                session = CompanyPrepSession(
                    user_id=user_id,
                    company_name=session_data["company"],
                    prep_type=session_data["type"],
                    progress_percentage=session_data["progress"],
                    completed=session_data["progress"] >= 80,
                    topics_covered=json.dumps([f"{session_data['type']} prep", "Interview questions", "Company culture"]),
                    created_at=datetime.utcnow() - timedelta(days=random.randint(1, 30))
                )
                db.session.add(session)
            
            # 6. Resume Upload
            resume = ResumeUpload(
                user_id=user_id,
                filename="resume_optimized.pdf",
                original_filename="my_resume.pdf",
                file_size=245760,  # ~240KB
                file_type="pdf",
                analysis_score=87.5,
                suggestions=json.dumps([
                    "Add more quantified achievements",
                    "Include relevant keywords for ATS",
                    "Improve formatting consistency"
                ]),
                uploaded_at=datetime.utcnow() - timedelta(days=5)
            )
            db.session.add(resume)
            
            # Commit all changes
            db.session.commit()
            
            print("✅ Sample data populated successfully!")
            print("\n📈 Dashboard Statistics Preview:")
            print(f"   • AI Interviews: {len(ai_sessions)} sessions")
            print(f"   • Avatar Interviews: {len(avatar_sessions)} sessions") 
            print(f"   • DSA Problems: {len([p for p in dsa_problems if p['solved']])}/{len(dsa_problems)} solved")
            print(f"   • English Booster: {len(english_sessions)} sessions")
            print(f"   • Company Prep: {len(company_sessions)} companies")
            print(f"   • Resume: 1 uploaded with {resume.analysis_score}% analysis score")
            print("\n🎯 Visit /dashboard to see your real data in action!")
            
        except Exception as e:
            print(f"❌ Error populating sample data: {e}")
            db.session.rollback()

if __name__ == "__main__":
    print("🚀 Sample Data Population Script")
    print("=" * 40)
    
    # You can change this user_id to match your registered user
    user_id = input("Enter user ID to populate data for (default: 1): ").strip()
    user_id = int(user_id) if user_id.isdigit() else 1
    
    populate_sample_data(user_id)
