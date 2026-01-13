from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta

app = Flask(__name__)
app.secret_key = "your_secret_key_here"
app.permanent_session_lifetime = timedelta(days=7)

# ------------------ MYSQL CONNECTION ------------------
def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="123456",
        database="career_compass"
    )

# ------------------ CREATE DATABASE & TABLE ------------------
def reset_database():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DROP TABLE IF EXISTS users")
        conn.commit()
    except:
        pass
    finally:
        cursor.close()
        conn.close()

def setup_database():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="smvsch"
    )
    cursor = conn.cursor()
    cursor.execute("CREATE DATABASE IF NOT EXISTS careercompass")
    cursor.close()
    conn.close()


    # Connect to new database
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    username VARCHAR(80) PRIMARY KEY,
    email VARCHAR(120) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    interest VARCHAR(50),
    career_path VARCHAR(255),
    colleges VARCHAR(255)
)
    """)
    conn.commit()
    cursor.close()
    conn.close()

try:
    setup_database()
except Exception as e:
    # Don't let DB setup failures crash the whole app at import time.
    # Common case: wrong local MySQL credentials. Inform the developer and continue.
    print("Warning: setup_database() failed at startup:", repr(e))
    print("The app will continue running, but any DB actions may fail until credentials are fixed.")

# ------------------ SIGNUP ------------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username'].strip().lower()
        email = request.form['email'].strip()
        password = request.form['password']
        confirm_password = request.form['confirmPassword']

        if password != confirm_password:
            flash("Passwords do not match!", "error")
            return redirect(url_for('signup'))

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        existing_user = cursor.fetchone()

        if existing_user:
            flash("Username already exists!", "error")
            cursor.close()
            conn.close()
            return redirect(url_for('signup'))

        hashed_password = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
            (username, email, hashed_password)
        )
        conn.commit()
        cursor.close()
        conn.close()

        # Auto-login the newly created user and send them to the quiz
        session.permanent = True
        session['user'] = username
        flash("Signup successful! Please complete the interest analyzer to proceed.", "success")
        return redirect(url_for('quiz'))

    return render_template('signup.html')

# ------------------ LOGIN ------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip().lower()
        password = request.form['password']

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if not user or not check_password_hash(user['password'], password):
            flash("Invalid username or password!", "error")
            return redirect(url_for('login'))

        session.permanent = True
        session['user'] = username
        flash("Login successful!", "success")
        return redirect(url_for('home'))

    return render_template('login.html')

# ------------------ LOGOUT ------------------
@app.route('/logout')
def logout():
    session.pop('user', None)
    flash("Logged out successfully!", "success")
    return redirect(url_for('login'))

# ------------------ HOME ------------------
@app.route('/')
def home():
    if 'user' in session:
        return render_template('home.html', user=session['user'])
    return redirect(url_for('login'))

# ------------------ QUIZ ------------------
questions = [
    {"question": "What do you enjoy the most?", "options": ["Solving problems", "Creating designs", "Helping people", "Exploring new ideas"]},
    {"question": "Which subject do you like most?", "options": ["Math & Science", "Art & Design", "Social Studies", "Technology"]},
    {"question": "Which activity excites you?", "options": ["Building apps/websites", "Drawing or Designing", "Teaching others", "Experimenting in labs"]},
    {"question": "Which career sounds more exciting?", "options": ["Engineer", "Designer", "Doctor/Teacher", "Entrepreneur"]},
    {"question": "What type of environment do you prefer?", "options": ["Working with computers & tech", "Creative studio", "Hospitals/Classrooms", "Business/startup office"]},
    {"question": "Which skill do you want to improve most?", "options": ["Analytical & Logical", "Creative Thinking", "Communication", "Leadership"]}
]

@app.route('/quiz', methods=['GET', 'POST'])
def quiz():
    if 'user' not in session:
        return redirect(url_for('login'))

    username = session['user']

    # Check if user already has interest saved in DB or session (prevents retake)
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT interest FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        # If DB has interest for this user, or we have computed results for this username in session, prevent retake
        if (user and user.get('interest')) or session.get('computed_results', {}).get(username):
            cursor.close()
            conn.close()
            return redirect(url_for('results'))
    except mysql.connector.Error:
        # if DB query fails, still prevent retake within this session if we have computed values for this username
        if session.get('computed_results', {}).get(username):
            try:
                cursor.close()
                conn.close()
            except:
                pass
            return redirect(url_for('results'))
    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass

    if 'quiz_progress' not in session:
        session['quiz_progress'] = 0
        session['quiz_answers'] = {}

    progress = session['quiz_progress']

    if request.method == 'POST':
        selected_answer = request.form.get('answer')
        if not selected_answer:
            flash("Please select an option to continue.", "error")
            return redirect(url_for('quiz'))

        session['quiz_answers'][str(progress)] = selected_answer
        session.modified = True
        progress += 1
        session['quiz_progress'] = progress

        if progress >= len(questions):
            answers = list(session['quiz_answers'].values())

            stem_keywords = ["Solving problems", "Math & Science", "Technology", "Engineer", "Analytical & Logical", "Building apps/websites", "Experimenting in labs"]
            creative_keywords = ["Creating designs", "Art & Design", "Designer", "Drawing or Designing", "Creative Thinking"]
            social_keywords = ["Helping people", "Doctor/Teacher", "Hospitals/Classrooms", "Communication", "Teaching others"]
            business_keywords = ["Entrepreneur", "Business/startup office", "Leadership"]

            counts = {"STEM": 0, "Creative": 0, "Social": 0, "Business": 0}
            for ans in answers:
                if ans in stem_keywords:
                    counts["STEM"] += 1
                elif ans in creative_keywords:
                    counts["Creative"] += 1
                elif ans in social_keywords:
                    counts["Social"] += 1
                elif ans in business_keywords:
                    counts["Business"] += 1

            interest = max(counts, key=counts.get)

            career_paths = {
                "STEM": "Engineering, AI, Data Science",
                "Creative": "Design, Animation, Media",
                "Social": "Medicine, UPSC, Teaching",
                "Business": "Entrepreneurship, MBA"
            }
            colleges = {
                "STEM": "IITs, NITs, VIT, SRM",
                "Creative": "NID, FTII, Srishti School of Design",
                "Social": "AIIMS, JNU, TISS",
                "Business": "IIMs, ISB, XLRI"
            }

            # store computed results in session as a fallback per-username to avoid leaking between accounts
            computed = session.setdefault('computed_results', {})
            computed[username] = {
                'interest': interest,
                'career': career_paths[interest],
                'colleges': colleges[interest]
            }
            session['computed_results'] = computed
            session.modified = True

            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE users
                    SET interest = %s, career_path = %s, colleges = %s
                    WHERE username = %s
                """, (interest, career_paths[interest], colleges[interest], username))
                conn.commit()
            except mysql.connector.Error as err:
                # on DB error, keep computed results in session and notify user
                flash("An error occurred while saving your results to the database. Showing results from this session.", "warning")
            finally:
                try:
                    cursor.close()
                    conn.close()
                except:
                    pass

            # clear quiz session state regardless of DB success so questions don't repeat
            session.pop('quiz_progress', None)
            session.pop('quiz_answers', None)
            return redirect(url_for('results'))

        return redirect(url_for('quiz'))

    if progress < len(questions):
        question_data = questions[progress]
        return render_template('quiz.html', question=question_data, question_num=progress + 1, total_questions=len(questions), user=username)

    return redirect(url_for('home'))

# ------------------ RESULTS ------------------
@app.route('/results')
def results():
    if 'user' not in session:
        return redirect(url_for('login'))

    username = session['user']

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    # If DB has no interest yet, fall back to computed values stored in session (set during quiz) for this username
    if (not user or not user.get('interest')) and not session.get('computed_results', {}).get(username):
        flash("You haven't completed the quiz yet.", "error")
        return redirect(url_for('quiz'))

    if user and user.get('interest'):
        interest = user['interest']
        career_path = user.get('career_path')
        colleges = user.get('colleges')
    else:
        # use fallback values stored in session (from the quiz computation) for this username
        computed = session.get('computed_results', {}).get(username, {})
        interest = computed.get('interest')
        career_path = computed.get('career')
        colleges = computed.get('colleges')

    DETAILS = {
        "STEM": {
            "description": "You are inclined towards Science, Technology, Engineering, and Math.",
            "exams": ["JEE Main & Advanced", "BITSAT", "VITEEE", "SRMJEEE"],
            "tips": ["Practice problem solving", "Learn programming", "Join competitions"]
        },
        "Creative": {
            "description": "You are creatively inclined.",
            "exams": ["UCEED", "NID DAT", "NIFT Entrance"],
            "tips": ["Build a portfolio", "Learn digital tools", "Join contests"]
        },
        "Social": {
            "description": "You have a passion for helping others.",
            "exams": ["NEET", "CUET", "TISSNET"],
            "tips": ["Volunteer", "Improve communication", "Prepare for exams"]
        },
        "Business": {
            "description": "You are interested in Business and Leadership.",
            "exams": ["CAT", "XAT", "MAT", "IPMAT"],
            "tips": ["Follow business trends", "Learn finance", "Join competitions"]
        }
    }

    detail = DETAILS.get(interest, {"description": "General", "exams": [], "tips": []})

    return render_template(
        'results.html',
        user=username,
        interest=interest,
        career_path=career_path,
        colleges=colleges,
        description=detail['description'],
        exams=detail['exams'],
        tips=detail['tips']
    )


# ------------------ CHAT ------------------
@app.route('/chat', methods=['POST'])
def chat():
    if 'user' not in session:
        return jsonify({"answer": "Please login first!"})

    user_question = request.form.get('question', '').lower()
    answers = {
        "jee": "JEE Main & Advanced are key exams for engineering.",
        "neet": "NEET is required for medical courses.",
        "tips": "Start early, practice regularly, use NPTEL, YouTube.",
        "colleges": "Top colleges: IITs, NITs, NID, AIIMS, IIMs."
    }

    response = "Sorry, I don't have an answer for that. Try asking about exams, tips, or colleges."
    for key in answers:
        if key in user_question:
            response = answers[key]
            break

    return jsonify({"answer": response})


# ------------------ ROADMAP ------------------
@app.route('/roadmap')
def roadmap():
    if 'user' not in session:
        return redirect(url_for('login'))

    username = session['user']

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT interest FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        # prefer DB value, but fall back to session-computed value if present
        if user and user.get('interest'):
            interest = user.get('interest')
        else:
            interest = session.get('computed_results', {}).get(username, {}).get('interest', "General")
    except mysql.connector.Error:
        interest = "General"
        flash("An error occurred while fetching your profile. Showing general roadmap.", "error")
    finally:
        cursor.close()
        conn.close()

    # Map each interest area to roadmap steps
    ROADMAPS = {
        "STEM": [
            {"title": "Focus Areas", "points": [
                "Prioritize Math, Physics, and Chemistry in school.",
                "Practice logical reasoning and problem solving.",
                "Learn programming basics (Python, Java, C++)."
            ]},
            {"title": "Minimum School Marks", "points": [
                "Class 10: Aim for 75% or more.",
                "Class 12: Minimum 75% in PCM (for JEE eligibility).",
                "Target 85%+ for top-tier institutions."
            ]},
            {"title": "Entrance Exams", "points": [
                "JEE Main & Advanced (for IITs/NITs)",
                "BITSAT (BITS Pilani, Goa, Hyderabad)",
                "VITEEE / SRMJEEE / MET (private colleges)"
            ]},
            {"title": "Recommended Courses", "points": [
                "B.Tech in Computer Science / Mechanical / Electrical",
                "B.Sc in Data Science / Physics / Mathematics",
                "Integrated M.Tech or Dual Degree in Engineering"
            ]},
            {"title": "Top Colleges", "points": [
                "IIT Bombay, IIT Madras, IIT Delhi",
                "NIT Trichy, NIT Surathkal",
                "IIIT Hyderabad, BITS Pilani"
            ]},
            {"title": "Internships & Skill Building", "points": [
                "Practice coding on LeetCode, Codeforces",
                "Contribute to GitHub projects",
                "Do summer internships from 2nd year"
            ]}
        ],
        "Creative": [
            {"title": "Focus Areas", "points": [
                "Practice drawing, designing, and illustration.",
                "Learn digital tools like Photoshop, Illustrator, Figma.",
                "Explore animation, UI/UX, and creative storytelling."
            ]},
            {"title": "Minimum School Marks", "points": [
                "Class 10: Aim for 70% or more.",
                "Class 12: Minimum 70% in any stream (Arts, Commerce, or Science).",
                "Top design schools may prefer 80%+ for entrance eligibility."
            ]},
            {"title": "Entrance Exams", "points": [
                "UCEED (for IIT Design programs)",
                "NID DAT (for National Institute of Design)",
                "NIFT Entrance (for fashion/design colleges)"
            ]},
            {"title": "Recommended Courses", "points": [
                "B.Des (Bachelor of Design)",
                "BFA (Fine Arts) or Animation",
                "BA in Multimedia / Visual Communication"
            ]},
            {"title": "Top Colleges", "points": [
                "NID Ahmedabad, IIT Bombay IDC",
                "Srishti School of Art, Pearl Academy",
                "MIT ID, NIFT"
            ]},
            {"title": "Internships & Skill Building", "points": [
                "Create a portfolio on Behance or Dribbble",
                "Intern at design studios or media agencies",
                "Join online creative contests and workshops"
            ]}
        ],
        "Social": [
            {"title": "Focus Areas", "points": [
                "Focus on Biology, Psychology, and Social Studies.",
                "Improve communication and empathy skills.",
                "Participate in social service and teaching activities."
            ]},
            {"title": "Minimum School Marks", "points": [
                "Class 10: 70% or above.",
                "Class 12: Biology/Arts with 75%+ recommended.",
                "Higher marks improve chances in top universities."
            ]},
            {"title": "Entrance Exams", "points": [
                "NEET (for Medicine/Healthcare)",
                "CUET (for Social Sciences and Teaching courses)",
                "TISSNET (for Social Work and Policy)"
            ]},
            {"title": "Recommended Courses", "points": [
                "MBBS / Nursing / BPT (Physiotherapy)",
                "BA in Psychology / Education",
                "Masters in Social Work (MSW)"
            ]},
            {"title": "Top Colleges", "points": [
                "AIIMS, Christian Medical College",
                "JNU (Jawaharlal Nehru University)",
                "TISS (Tata Institute of Social Sciences)"
            ]},
            {"title": "Internships & Skill Building", "points": [
                "Volunteer in NGOs and community programs",
                "Work as a teaching assistant or tutor",
                "Shadow doctors or healthcare professionals"
            ]}
        ],
        "Business": [
            {"title": "Focus Areas", "points": [
                "Strengthen Mathematics, Economics, and Business Studies.",
                "Develop leadership and entrepreneurial skills.",
                "Stay updated with current affairs and finance news."
            ]},
            {"title": "Minimum School Marks", "points": [
                "Class 10: 70% or more.",
                "Class 12: Commerce stream with 75%+ recommended.",
                "Some BBA/MBA programs prefer 80%+."
            ]},
            {"title": "Entrance Exams", "points": [
                "CAT / XAT / MAT (for MBA)",
                "IPMAT (for IIM Integrated MBA)",
                "CUET (for B.Com / BBA programs)"
            ]},
            {"title": "Recommended Courses", "points": [
                "BBA / BBM / BMS (Business Studies)",
                "B.Com (Accounting/Finance)",
                "MBA in Finance, Marketing, or Entrepreneurship"
            ]},
            {"title": "Top Colleges", "points": [
                "IIM Ahmedabad, Bangalore, Calcutta",
                "ISB Hyderabad",
                "XLRI Jamshedpur"
            ]},
            {"title": "Internships & Skill Building", "points": [
                "Work in startups or family business",
                "Do internships in finance/marketing firms",
                "Participate in case study competitions"
            ]}
        ],
    }

    steps = ROADMAPS.get(interest, [])

    return render_template(
        'roadmap.html',
        user=username,
        interest=interest,
        roadmap_steps=steps  # updated variable name for HTML loop
    )

# ------------------ CAREER GRAPH ------------------
@app.route('/career-graph')
def career_graph():
    course_data = [
        {"course": "Data Science", "popularity": 95, "future_scope": 98},
        {"course": "Cybersecurity", "popularity": 85, "future_scope": 90},
        {"course": "UI/UX Design", "popularity": 80, "future_scope": 88},
        {"course": "Digital Marketing", "popularity": 75, "future_scope": 80},
        {"course": "AI & ML", "popularity": 92, "future_scope": 97},
        {"course": "Web Development", "popularity": 70, "future_scope": 75},
    ]
    return render_template('career_graph.html', course_data=course_data)


# ------------------ MAIN ------------------
if __name__ == '__main__':
    print("🚀 Flask server starting...")
    app.run(debug=True)
