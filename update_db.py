#!/usr/bin/env python3
"""
Database update script to change performance column from Integer to Float
"""
import sqlite3
import os

def update_database():
    db_path = 'interview_prep.db'
    
    if not os.path.exists(db_path):
        print("Database not found. It will be created when the app runs.")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if AIInterview table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ai_interview'")
        if not cursor.fetchone():
            print("AIInterview table not found. It will be created when the app runs.")
            conn.close()
            return
        
        # Check current schema
        cursor.execute("PRAGMA table_info(ai_interview)")
        columns = cursor.fetchall()
        
        # Find performance column
        performance_col = None
        for col in columns:
            if col[1] == 'performance':
                performance_col = col
                break
        
        if performance_col and 'INTEGER' in performance_col[2].upper():
            print("Updating performance column from INTEGER to REAL...")
            
            # Create new table with correct schema
            cursor.execute('''
                CREATE TABLE ai_interview_new (
                    id INTEGER PRIMARY KEY,
                    job_role VARCHAR(100) NOT NULL,
                    experience_level VARCHAR(50) NOT NULL,
                    target_company VARCHAR(100) NOT NULL,
                    date DATETIME NOT NULL,
                    questions TEXT NOT NULL,
                    answers TEXT,
                    feedback TEXT,
                    performance REAL,
                    user_id INTEGER NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES user(id)
                )
            ''')
            
            # Copy data from old table to new table
            cursor.execute('''
                INSERT INTO ai_interview_new 
                SELECT id, job_role, experience_level, target_company, date, 
                       questions, answers, feedback, performance, user_id 
                FROM ai_interview
            ''')
            
            # Drop old table and rename new table
            cursor.execute('DROP TABLE ai_interview')
            cursor.execute('ALTER TABLE ai_interview_new RENAME TO ai_interview')
            
            conn.commit()
            print("Database updated successfully!")
        else:
            print("Performance column is already correct type or not found.")
        
        conn.close()
        
    except Exception as e:
        print(f"Error updating database: {e}")
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    update_database()
