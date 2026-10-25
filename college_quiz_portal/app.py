import os
import secrets
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db, init_db

app = Flask(__name__)
app.secret_key = secrets.token_hex(24)

# Decorator to protect student/user routes
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Decorator to protect admin/faculty routes
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Access restricted to faculty and admins.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not password:
            flash('Please provide both username and password.', 'danger')
            return render_template('login.html')

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            flash(f"Welcome back, {user['full_name']}!", 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password. Please try again.', 'danger')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', 'student').strip()

        if role not in ['student', 'admin']:
            role = 'student'

        if not username or not full_name or not email or not password:
            flash('All fields are required.', 'danger')
            return render_template('register.html')

        conn = get_db()
        cursor = conn.cursor()

        # Check existing user
        cursor.execute("SELECT id FROM users WHERE username = ? OR email = ?", (username, email))
        existing = cursor.fetchone()

        if existing:
            conn.close()
            flash('Username or Email is already registered.', 'danger')
            return render_template('register.html')

        pwd_hash = generate_password_hash(password)
        cursor.execute("""
        INSERT INTO users (username, full_name, email, password_hash, role)
        VALUES (?, ?, ?, ?, ?)
        """, (username, full_name, email, pwd_hash, role))
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()

        # Auto login
        session['user_id'] = new_id
        session['username'] = username
        session['full_name'] = full_name
        session['role'] = role
        flash('Account created successfully! Welcome to College Quiz Portal.', 'success')
        return redirect(url_for('dashboard'))

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out safely.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    cursor = conn.cursor()

    # Available Quizzes with question count
    cursor.execute("""
    SELECT q.*, u.full_name as author_name,
           (SELECT COUNT(*) FROM questions WHERE quiz_id = q.id) as question_count
    FROM quizzes q
    LEFT JOIN users u ON q.created_by = u.id
    ORDER BY q.created_at DESC
    """)
    quizzes = cursor.fetchall()

    # User's recent attempts
    cursor.execute("""
    SELECT a.*, q.title as quiz_title, q.category
    FROM attempts a
    JOIN quizzes q ON a.quiz_id = q.id
    WHERE a.user_id = ?
    ORDER BY a.completed_at DESC
    """, (session['user_id'],))
    my_attempts = cursor.fetchall()

    # Calculate user stats
    total_quizzes_taken = len(my_attempts)
    avg_score = round(sum(att['percentage'] for att in my_attempts) / total_quizzes_taken, 1) if total_quizzes_taken > 0 else 0
    best_score = max((att['percentage'] for att in my_attempts), default=0)

    conn.close()

    return render_template('dashboard.html', 
                           quizzes=quizzes, 
                           my_attempts=my_attempts,
                           total_quizzes_taken=total_quizzes_taken,
                           avg_score=avg_score,
                           best_score=best_score)

@app.route('/quiz/<int:quiz_id>')
@login_required
def start_quiz(quiz_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM quizzes WHERE id = ?", (quiz_id,))
    quiz = cursor.fetchone()

    if not quiz:
        conn.close()
        flash('Quiz not found.', 'danger')
        return redirect(url_for('dashboard'))

    cursor.execute("SELECT * FROM questions WHERE quiz_id = ?", (quiz_id,))
    questions = cursor.fetchall()
    conn.close()

    if not questions:
        flash('This quiz has no questions yet. Please check back later!', 'warning')
        return redirect(url_for('dashboard'))

    return render_template('quiz.html', quiz=quiz, questions=questions, total_q=len(questions))

@app.route('/quiz/<int:quiz_id>/submit', methods=['POST'])
@login_required
def submit_quiz(quiz_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM quizzes WHERE id = ?", (quiz_id,))
    quiz = cursor.fetchone()
    if not quiz:
        conn.close()
        flash('Invalid quiz.', 'danger')
        return redirect(url_for('dashboard'))

    cursor.execute("SELECT * FROM questions WHERE quiz_id = ?", (quiz_id,))
    questions = cursor.fetchall()

    time_spent = int(request.form.get('time_spent', 0))
    tab_switches = int(request.form.get('tab_switches', 0))

    score = 0
    total_questions = len(questions)
    responses_to_save = []

    for q in questions:
        q_id = q['id']
        selected = request.form.get(f'q_{q_id}')
        is_correct = 1 if selected and selected.upper() == q['correct_option'].upper() else 0
        if is_correct:
            score += 1
        responses_to_save.append((q_id, selected, is_correct))

    percentage = round((score / total_questions) * 100, 1) if total_questions > 0 else 0.0

    # Save attempt into attempts table
    cursor.execute("""
    INSERT INTO attempts (user_id, quiz_id, score, total_questions, percentage, time_spent_seconds, tab_switches)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (session['user_id'], quiz_id, score, total_questions, percentage, time_spent, tab_switches))
    attempt_id = cursor.lastrowid

    # Save detailed responses into attempt_responses table
    for r in responses_to_save:
        cursor.execute("""
        INSERT INTO attempt_responses (attempt_id, question_id, selected_option, is_correct)
        VALUES (?, ?, ?, ?)
        """, (attempt_id, r[0], r[1], r[2]))

    conn.commit()
    conn.close()

    flash('Quiz submitted and scored successfully!', 'success')
    return redirect(url_for('view_result', attempt_id=attempt_id))

@app.route('/result/<int:attempt_id>')
@login_required
def view_result(attempt_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT a.*, q.title as quiz_title, q.category, u.full_name as student_name
    FROM attempts a
    JOIN quizzes q ON a.quiz_id = q.id
    JOIN users u ON a.user_id = u.id
    WHERE a.id = ?
    """, (attempt_id,))
    attempt = cursor.fetchone()

    if not attempt:
        conn.close()
        flash('Attempt not found.', 'danger')
        return redirect(url_for('dashboard'))

    # Security check: only the student who took it or an admin can view
    if attempt['user_id'] != session['user_id'] and session.get('role') != 'admin':
        conn.close()
        flash('You are not authorized to view this result.', 'danger')
        return redirect(url_for('dashboard'))

    # Fetch question responses breakdown
    cursor.execute("""
    SELECT ar.*, q.question_text, q.option_a, q.option_b, q.option_c, q.option_d, q.correct_option, q.explanation
    FROM attempt_responses ar
    JOIN questions q ON ar.question_id = q.id
    WHERE ar.attempt_id = ?
    """, (attempt_id,))
    breakdown = cursor.fetchall()
    conn.close()

    return render_template('result.html', attempt=attempt, breakdown=breakdown)

@app.route('/leaderboard')
@login_required
def leaderboard():
    conn = get_db()
    cursor = conn.cursor()

    # Top scores query: highest score, least time taken
    cursor.execute("""
    SELECT a.*, u.full_name, u.username, q.title as quiz_title, q.category
    FROM attempts a
    JOIN users u ON a.user_id = u.id
    JOIN quizzes q ON a.quiz_id = q.id
    ORDER BY a.percentage DESC, a.time_spent_seconds ASC
    LIMIT 20
    """)
    top_attempts = cursor.fetchall()
    conn.close()

    return render_template('leaderboard.html', top_attempts=top_attempts)

@app.route('/admin')
@admin_required
def admin_panel():
    conn = get_db()
    cursor = conn.cursor()

    # Quizzes list
    cursor.execute("""
    SELECT q.*, 
           (SELECT COUNT(*) FROM questions WHERE quiz_id = q.id) as question_count,
           (SELECT COUNT(*) FROM attempts WHERE quiz_id = q.id) as attempt_count
    FROM quizzes q
    ORDER BY q.created_at DESC
    """)
    quizzes = cursor.fetchall()

    # All student submissions
    cursor.execute("""
    SELECT a.*, u.full_name as student_name, u.username as roll_number, q.title as quiz_title
    FROM attempts a
    JOIN users u ON a.user_id = u.id
    JOIN quizzes q ON a.quiz_id = q.id
    ORDER BY a.completed_at DESC
    """)
    all_attempts = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) as total_students FROM users WHERE role = 'student'")
    total_students = cursor.fetchone()['total_students']

    cursor.execute("SELECT COUNT(*) as total_quizzes FROM quizzes")
    total_quizzes = cursor.fetchone()['total_quizzes']

    cursor.execute("SELECT COUNT(*) as total_submissions FROM attempts")
    total_submissions = cursor.fetchone()['total_submissions']

    conn.close()

    return render_template('admin.html', 
                           quizzes=quizzes, 
                           all_attempts=all_attempts,
                           total_students=total_students,
                           total_quizzes=total_quizzes,
                           total_submissions=total_submissions)

@app.route('/admin/quiz/new', methods=['POST'])
@admin_required
def create_quiz():
    title = request.form.get('title', '').strip()
    category = request.form.get('category', '').strip()
    description = request.form.get('description', '').strip()
    duration = int(request.form.get('duration_minutes', 10))

    if not title or not category:
        flash('Title and Category are required.', 'danger')
        return redirect(url_for('admin_panel'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO quizzes (title, category, description, duration_minutes, created_by)
    VALUES (?, ?, ?, ?, ?)
    """, (title, category, description, duration, session['user_id']))
    conn.commit()
    conn.close()

    flash(f"Quiz '{title}' created! Now add some questions below.", 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/question/new', methods=['POST'])
@admin_required
def add_question():
    quiz_id = int(request.form.get('quiz_id'))
    question_text = request.form.get('question_text', '').strip()
    opt_a = request.form.get('option_a', '').strip()
    opt_b = request.form.get('option_b', '').strip()
    opt_c = request.form.get('option_c', '').strip()
    opt_d = request.form.get('option_d', '').strip()
    correct = request.form.get('correct_option', '').strip().upper()
    explanation = request.form.get('explanation', '').strip()

    if not question_text or not opt_a or not opt_b or not opt_c or not opt_d or correct not in ['A', 'B', 'C', 'D']:
        flash('Please fill in all question fields and select the correct option.', 'danger')
        return redirect(url_for('admin_panel'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO questions (quiz_id, question_text, option_a, option_b, option_c, option_d, correct_option, explanation)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (quiz_id, question_text, opt_a, opt_b, opt_c, opt_d, correct, explanation))
    conn.commit()
    conn.close()

    flash('New question successfully added to the quiz!', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/quiz/<int:quiz_id>/delete', methods=['POST'])
@admin_required
def delete_quiz(quiz_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM quizzes WHERE id = ?", (quiz_id,))
    conn.commit()
    conn.close()

    flash('Quiz and associated questions deleted successfully.', 'info')
    return redirect(url_for('admin_panel'))

if __name__ == '__main__':
    init_db()
    print("Starting College Quiz Portal on http://127.0.0.1:5000 ...")
    app.run(debug=True, host='127.0.0.1', port=5000)
