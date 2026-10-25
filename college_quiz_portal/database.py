import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), 'quiz.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Users Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'student',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Quizzes Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS quizzes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        category TEXT NOT NULL,
        description TEXT,
        duration_minutes INTEGER NOT NULL DEFAULT 10,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (created_by) REFERENCES users(id)
    )
    """)

    # Questions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quiz_id INTEGER NOT NULL,
        question_text TEXT NOT NULL,
        option_a TEXT NOT NULL,
        option_b TEXT NOT NULL,
        option_c TEXT NOT NULL,
        option_d TEXT NOT NULL,
        correct_option TEXT NOT NULL,
        explanation TEXT,
        FOREIGN KEY (quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE
    )
    """)

    # Quiz Attempts Table (Logs each student's quiz session)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        quiz_id INTEGER NOT NULL,
        score INTEGER NOT NULL DEFAULT 0,
        total_questions INTEGER NOT NULL,
        percentage REAL NOT NULL DEFAULT 0.0,
        time_spent_seconds INTEGER NOT NULL DEFAULT 0,
        tab_switches INTEGER NOT NULL DEFAULT 0,
        status TEXT DEFAULT 'completed',
        completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (quiz_id) REFERENCES quizzes(id)
    )
    """)

    # Attempt Answers Table (Logs every individual question answer)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attempt_responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        attempt_id INTEGER NOT NULL,
        question_id INTEGER NOT NULL,
        selected_option TEXT,
        is_correct INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (attempt_id) REFERENCES attempts(id) ON DELETE CASCADE,
        FOREIGN KEY (question_id) REFERENCES questions(id)
    )
    """)

    conn.commit()
    seed_initial_data(conn)
    conn.close()

def seed_initial_data(conn):
    cursor = conn.cursor()

    # Check if admin already exists
    cursor.execute("SELECT id FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        # Seed default Admin and Student
        admin_pwd = generate_password_hash("admin123")
        student_pwd = generate_password_hash("student123")

        cursor.execute("""
        INSERT INTO users (username, full_name, email, password_hash, role)
        VALUES 
        ('admin', 'Prof. Sharma (Admin/Faculty)', 'faculty@college.edu', ?, 'admin'),
        ('student1', 'Alex Carter (Student Demo)', 'student1@college.edu', ?, 'student')
        """, (admin_pwd, student_pwd))

        conn.commit()

    # Check if quizzes already exist
    cursor.execute("SELECT COUNT(*) as count FROM quizzes")
    count = cursor.fetchone()['count']
    if count == 0:
        cursor.execute("SELECT id FROM users WHERE username = 'admin'")
        admin_id = cursor.fetchone()['id']

        # Quiz 1: Python Basics
        cursor.execute("""
        INSERT INTO quizzes (title, category, description, duration_minutes, created_by)
        VALUES ('Python Programming Fundamentals', 'Python', 'Test your knowledge on data types, loops, lists, and functions in Python.', 5, ?)
        """, (admin_id,))
        quiz1_id = cursor.lastrowid

        quiz1_questions = [
            ("Which keyword is used to define a function in Python?", "func", "define", "def", "function", "C", "In Python, the 'def' keyword is used to declare user-defined functions."),
            ("What is the output of print(type([])) in Python?", "<class 'tuple'>", "<class 'list'>", "<class 'dict'>", "<class 'set'>", "B", "Square brackets [] represent a list in Python."),
            ("Which of the following data structures is immutable in Python?", "List", "Dictionary", "Set", "Tuple", "D", "Tuples cannot be modified after creation, making them immutable."),
            ("What is the correct file extension for Python files?", ".pyth", ".pt", ".py", ".p", "C", "Standard Python source files use the .py extension."),
            ("Which operator is used for exponentiation (power) in Python?", "^", "**", "pow", "//", "B", "The ** operator computes power, e.g., 2 ** 3 = 8.")
        ]
        for q in quiz1_questions:
            cursor.execute("""
            INSERT INTO questions (quiz_id, question_text, option_a, option_b, option_c, option_d, correct_option, explanation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (quiz1_id, q[0], q[1], q[2], q[3], q[4], q[5], q[6]))

        # Quiz 2: Web Tech
        cursor.execute("""
        INSERT INTO quizzes (title, category, description, duration_minutes, created_by)
        VALUES ('Web Development Fundamentals', 'Web Development', 'Covers HTML semantics, CSS styling, and core JavaScript fundamentals.', 5, ?)
        """, (admin_id,))
        quiz2_id = cursor.lastrowid

        quiz2_questions = [
            ("Which HTML tag is used for the largest heading?", "<h6>", "<head>", "<h1>", "<heading>", "C", "<h1> defines the most important, highest-level heading in HTML."),
            ("What does CSS stand for?", "Cascading Style Sheets", "Computer Style System", "Creative Styling Syntax", "Colorful Sheet Styles", "A", "CSS stands for Cascading Style Sheets."),
            ("Which JavaScript keyword declares a block-scoped variable that cannot be reassigned?", "var", "let", "const", "static", "C", "'const' declares block-scoped constants that cannot be reassigned."),
            ("Which HTTP method is typically used to submit form data to a server?", "GET", "POST", "DELETE", "FETCH", "B", "POST is standard for submitting sensitive form and body data to a server."),
            ("Which CSS property is used to control spacing inside an element's border?", "margin", "padding", "border-spacing", "gap", "B", "Padding controls space between the content and the border.")
        ]
        for q in quiz2_questions:
            cursor.execute("""
            INSERT INTO questions (quiz_id, question_text, option_a, option_b, option_c, option_d, correct_option, explanation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (quiz2_id, q[0], q[1], q[2], q[3], q[4], q[5], q[6]))

        # Quiz 3: Campus Aptitude
        cursor.execute("""
        INSERT INTO quizzes (title, category, description, duration_minutes, created_by)
        VALUES ('Campus Placement Aptitude & Logic', 'Aptitude', 'Quick reasoning and quantitative math questions asked in campus recruitment rounds.', 5, ?)
        """, (admin_id,))
        quiz3_id = cursor.lastrowid

        quiz3_questions = [
            ("A train running at 60 km/hr crosses a pole in 9 seconds. What is the length of the train?", "120 meters", "150 meters", "180 meters", "324 meters", "B", "Speed = 60 * (5/18) = 50/3 m/s. Distance = Speed * Time = (50/3) * 9 = 150 meters."),
            ("Find the next number in sequence: 2, 6, 12, 20, 30, ?", "40", "42", "44", "48", "B", "The differences are +4, +6, +8, +10. Next difference is +12, so 30 + 12 = 42."),
            ("If a clock shows 3:15, what is the angle between the hour and minute hands?", "0 degrees", "7.5 degrees", "15 degrees", "22.5 degrees", "B", "At 3:15, the hour hand moves 15 * 0.5 = 7.5 degrees past the 3 mark. Angle = 7.5°."),
            ("A product is sold for $240 at a 20% profit. What was its cost price?", "$180", "$200", "$210", "$220", "B", "Selling Price = 1.2 * Cost Price => Cost Price = 240 / 1.2 = $200.")
        ]
        for q in quiz3_questions:
            cursor.execute("""
            INSERT INTO questions (quiz_id, question_text, option_a, option_b, option_c, option_d, correct_option, explanation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (quiz3_id, q[0], q[1], q[2], q[3], q[4], q[5], q[6]))

        conn.commit()

if __name__ == '__main__':
    init_db()
    print("Database initialized successfully at", DB_PATH)
