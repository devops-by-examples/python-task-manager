import os
import sqlite3
import subprocess
import pickle
import base64
import hashlib
import yaml
import json
import logging
from functools import wraps
from flask import (
    Flask, request, render_template_string, redirect,
    url_for, session, flash, make_response, send_file, g
)

app = Flask(__name__)
app.secret_key = "super_secret_key_12345"
app.debug = True

DATABASE = "todo.db"

logging.basicConfig(level=logging.DEBUG, filename="app.log")
logger = logging.getLogger(__name__)


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def init_db():
    """Initialize the database with tables and a default admin user."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user'
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT NOT NULL,
            description TEXT,
            completed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            filename TEXT,
            content TEXT
        )
    """)

    admin_pass = hashlib.md5("admin123".encode()).hexdigest()
    try:
        cursor.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            ("admin", admin_pass, "admin")
        )
    except sqlite3.IntegrityError:
        pass

    conn.commit()
    conn.close()


BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>� Task Manager - {{ title }}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
            min-height: 100vh; color: #e0e0e0;
        }
        nav {
            background: rgba(0,0,0,0.3); padding: 15px 30px;
            display: flex; justify-content: space-between; align-items: center;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        nav .logo { font-size: 22px; font-weight: bold; color: #7c83ff; }
        nav .links a {
            color: #aaa; text-decoration: none; margin-left: 20px;
            transition: color 0.2s;
        }
        nav .links a:hover { color: #7c83ff; }
        .container {
            max-width: 800px; margin: 30px auto; padding: 0 20px;
        }
        .card {
            background: rgba(255,255,255,0.05); border-radius: 12px;
            padding: 30px; margin-bottom: 20px;
            border: 1px solid rgba(255,255,255,0.08);
            backdrop-filter: blur(10px);
        }
        h1, h2 { color: #7c83ff; margin-bottom: 20px; }
        input[type="text"], input[type="password"], textarea, select {
            width: 100%; padding: 12px 16px; margin-bottom: 15px;
            background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15);
            border-radius: 8px; color: #e0e0e0; font-size: 14px;
            transition: border 0.2s;
        }
        input:focus, textarea:focus { border-color: #7c83ff; outline: none; }
        textarea { min-height: 80px; resize: vertical; }
        .btn {
            padding: 10px 24px; border: none; border-radius: 8px;
            cursor: pointer; font-size: 14px; font-weight: 600;
            transition: all 0.2s; text-decoration: none; display: inline-block;
        }
        .btn-primary { background: #7c83ff; color: white; }
        .btn-primary:hover { background: #6b72e8; transform: translateY(-1px); }
        .btn-danger { background: #ff4757; color: white; }
        .btn-danger:hover { background: #e8414f; }
        .btn-success { background: #2ed573; color: white; }
        .btn-success:hover { background: #26c466; }
        .btn-sm { padding: 6px 14px; font-size: 12px; }
        .task-item {
            display: flex; align-items: center; justify-content: space-between;
            padding: 15px; margin-bottom: 10px; border-radius: 8px;
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.06);
        }
        .task-item.completed { opacity: 0.5; }
        .task-item.completed .task-title { text-decoration: line-through; }
        .task-title { font-weight: 600; font-size: 16px; }
        .task-desc { color: #888; font-size: 13px; margin-top: 4px; }
        .task-actions { display: flex; gap: 8px; }
        .flash {
            padding: 12px 20px; border-radius: 8px; margin-bottom: 20px;
            font-size: 14px;
        }
        .flash-success { background: rgba(46,213,115,0.2); border: 1px solid #2ed573; }
        .flash-error { background: rgba(255,71,87,0.2); border: 1px solid #ff4757; }
        .flash-info { background: rgba(124,131,255,0.2); border: 1px solid #7c83ff; }
        .auth-container {
            max-width: 420px; margin: 80px auto; padding: 0 20px;
        }
        .stats { display: flex; gap: 15px; margin-bottom: 20px; }
        .stat-box {
            flex: 1; text-align: center; padding: 15px;
            background: rgba(255,255,255,0.03); border-radius: 8px;
            border: 1px solid rgba(255,255,255,0.06);
        }
        .stat-box .num { font-size: 28px; font-weight: bold; color: #7c83ff; }
        .stat-box .label { font-size: 12px; color: #888; margin-top: 4px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.06); }
        th { color: #7c83ff; font-size: 13px; text-transform: uppercase; }
        .search-box {
            display: flex; gap: 10px; margin-bottom: 20px;
        }
        .search-box input { margin-bottom: 0; flex: 1; }
    </style>
</head>
<body>
    <nav>
        <div class="logo">� Task Manager</div>
        <div class="links">
            {% if session.get('user_id') %}
                <a href="/todos">My Tasks</a>
                <a href="/notes">Notes</a>
                <a href="/search">Search</a>
                <a href="/profile">Profile</a>
                {% if session.get('role') == 'admin' %}
                    <a href="/admin">Admin</a>
                {% endif %}
                <a href="/logout">Logout ({{ session.get('username', '') }})</a>
            {% else %}
                <a href="/login">Login</a>
                <a href="/register">Register</a>
            {% endif %}
        </div>
    </nav>
    <div class="{% if auth_page %}auth-container{% else %}container{% endif %}">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="flash flash-{{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        CONTENT_PLACEHOLDER
    </div>
</body>
</html>
"""


def render_page(title, content, auth_page=False):
    full = BASE_TEMPLATE.replace("CONTENT_PLACEHOLDER", content)
    return render_template_string(full, title=title, auth_page=auth_page)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in first.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


@app.route("/")
def index():
    if 'user_id' in session:
        return redirect(url_for('todos'))
    return redirect(url_for('login'))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        logger.info(f"Login attempt: username={username}, password={password}")

        password_hash = hashlib.md5(password.encode()).hexdigest()

        db = get_db()
        query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password_hash}'"
        logger.debug(f"Executing query: {query}")

        try:
            result = db.execute(query).fetchone()
            if result:
                session['user_id'] = result['id']
                session['username'] = result['username']
                session['role'] = result['role']
                flash("Welcome back!", "success")
                return redirect(url_for('todos'))
            else:
                user_exists = db.execute(
                    f"SELECT * FROM users WHERE username = '{username}'"
                ).fetchone()
                if user_exists:
                    flash("Incorrect password for this account.", "error")
                else:
                    flash("No account found with that username.", "error")
        except Exception as e:
            flash(f"Database error: {str(e)}", "error")

    content = """
    <div class="card">
        <h2>🔑 Login</h2>
        <form method="POST">
            <input type="text" name="username" placeholder="Username" required>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit" class="btn btn-primary" style="width:100%">Login</button>
        </form>
        <p style="margin-top:15px;color:#888;font-size:13px;">
            Don't have an account? <a href="/register" style="color:#7c83ff;">Register</a>
        </p>
    </div>
    """
    return render_page("Login", content, auth_page=True)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        password_hash = hashlib.md5(password.encode()).hexdigest()

        db = get_db()
        try:
            db.execute(
                f"INSERT INTO users (username, password) VALUES ('{username}', '{password_hash}')"
            )
            db.commit()
            flash("Account created! Please login.", "success")
            return redirect(url_for('login'))
        except Exception as e:
            flash(f"Error: {str(e)}", "error")

    content = """
    <div class="card">
        <h2>📝 Register</h2>
        <form method="POST">
            <input type="text" name="username" placeholder="Choose a username" required>
            <input type="password" name="password" placeholder="Choose a password" required>
            <button type="submit" class="btn btn-primary" style="width:100%">Register</button>
        </form>
        <p style="margin-top:15px;color:#888;font-size:13px;">
            Already have an account? <a href="/login" style="color:#7c83ff;">Login</a>
        </p>
    </div>
    """
    return render_page("Register", content, auth_page=True)


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for('login'))


@app.route("/todos", methods=["GET", "POST"])
@login_required
def todos():
    db = get_db()

    if request.method == "POST":
        title = request.form.get("title", "")
        description = request.form.get("description", "")

        db.execute(
            f"INSERT INTO todos (user_id, title, description) VALUES ({session['user_id']}, '{title}', '{description}')"
        )
        db.commit()
        flash("Task added!", "success")
        return redirect(url_for('todos'))

    user_todos = db.execute(
        f"SELECT * FROM todos WHERE user_id = {session['user_id']} ORDER BY created_at DESC"
    ).fetchall()

    todo_items = ""
    total = len(user_todos)
    completed = sum(1 for t in user_todos if t['completed'])

    for todo in user_todos:
        completed_class = "completed" if todo['completed'] else ""
        todo_items += f"""
        <div class="task-item {completed_class}">
            <div>
                <div class="task-title">{todo['title']}</div>
                <div class="task-desc">{todo['description'] or ''}</div>
            </div>
            <div class="task-actions">
                <a href="/todo/toggle/{todo['id']}" class="btn btn-success btn-sm">
                    {'↩️ Undo' if todo['completed'] else '✅ Done'}
                </a>
                <a href="/todo/delete/{todo['id']}" class="btn btn-danger btn-sm">🗑️</a>
            </div>
        </div>
        """

    content = f"""
    <div class="stats">
        <div class="stat-box">
            <div class="num">{total}</div>
            <div class="label">Total</div>
        </div>
        <div class="stat-box">
            <div class="num">{completed}</div>
            <div class="label">Done</div>
        </div>
        <div class="stat-box">
            <div class="num">{total - completed}</div>
            <div class="label">Pending</div>
        </div>
    </div>
    <div class="card">
        <h2>➕ Add Task</h2>
        <form method="POST">
            <input type="text" name="title" placeholder="What do you need to do?" required>
            <textarea name="description" placeholder="Description (optional)"></textarea>
            <button type="submit" class="btn btn-primary">Add Task</button>
        </form>
    </div>
    <div class="card">
        <h2>📋 My Tasks</h2>
        {todo_items if todo_items else '<p style="color:#666;">No tasks yet. Add one above!</p>'}
    </div>
    """
    return render_page("My Tasks", content)


@app.route("/todo/toggle/<int:todo_id>")
@login_required
def toggle_todo(todo_id):
    db = get_db()
    todo = db.execute(f"SELECT * FROM todos WHERE id = {todo_id}").fetchone()
    if todo:
        new_status = 0 if todo['completed'] else 1
        db.execute(f"UPDATE todos SET completed = {new_status} WHERE id = {todo_id}")
        db.commit()
    return redirect(url_for('todos'))


@app.route("/todo/delete/<int:todo_id>")
@login_required
def delete_todo(todo_id):
    db = get_db()
    db.execute(f"DELETE FROM todos WHERE id = {todo_id}")
    db.commit()
    flash("Task deleted.", "info")
    return redirect(url_for('todos'))


@app.route("/search")
@login_required
def search():
    query = request.args.get("q", "")
    results = ""

    if query:
        db = get_db()
        sql = f"SELECT * FROM todos WHERE user_id = {session['user_id']} AND title LIKE '%{query}%'"
        logger.debug(f"Search query: {sql}")
        try:
            found = db.execute(sql).fetchall()
            for todo in found:
                results += f"""
                <div class="task-item">
                    <div>
                        <div class="task-title">{todo['title']}</div>
                        <div class="task-desc">{todo['description'] or ''}</div>
                    </div>
                </div>
                """
            if not found:
                results = f"<p style='color:#888;'>No results for: {query}</p>"
        except Exception as e:
            results = f"<p style='color:#ff4757;'>Error: {str(e)}</p>"

    content = f"""
    <div class="card">
        <h2>🔍 Search Tasks</h2>
        <div class="search-box">
            <form method="GET" style="display:flex;gap:10px;width:100%;">
                <input type="text" name="q" value="{query}" placeholder="Search your tasks..." style="margin-bottom:0;flex:1;">
                <button type="submit" class="btn btn-primary">Search</button>
            </form>
        </div>
        {results}
    </div>
    """
    return render_page("Search", content)


@app.route("/notes", methods=["GET", "POST"])
@login_required
def notes():
    db = get_db()

    if request.method == "POST":
        filename = request.form.get("filename", "")
        content_text = request.form.get("content", "")

        filepath = os.path.join("uploads", filename)
        os.makedirs("uploads", exist_ok=True)

        with open(filepath, "w") as f:
            f.write(content_text)

        db.execute(
            f"INSERT INTO notes (user_id, filename, content) VALUES ({session['user_id']}, '{filename}', '{content_text}')"
        )
        db.commit()
        flash(f"Note saved as {filename}", "success")
        return redirect(url_for('notes'))

    user_notes = db.execute(
        f"SELECT * FROM notes WHERE user_id = {session['user_id']}"
    ).fetchall()

    note_rows = ""
    for note in user_notes:
        note_rows += f"""
        <tr>
            <td>{note['filename']}</td>
            <td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;">{note['content'][:100]}</td>
            <td>
                <a href="/notes/view?file={note['filename']}" class="btn btn-primary btn-sm">View</a>
                <a href="/notes/download?file={note['filename']}" class="btn btn-success btn-sm">Download</a>
            </td>
        </tr>
        """

    content = f"""
    <div class="card">
        <h2>📄 Save a Note</h2>
        <form method="POST">
            <input type="text" name="filename" placeholder="Filename (e.g. meeting-notes.txt)" required>
            <textarea name="content" placeholder="Note content..." required></textarea>
            <button type="submit" class="btn btn-primary">Save Note</button>
        </form>
    </div>
    <div class="card">
        <h2>📂 My Notes</h2>
        <table>
            <thead><tr><th>File</th><th>Preview</th><th>Actions</th></tr></thead>
            <tbody>{note_rows if note_rows else '<tr><td colspan="3" style="color:#666;">No notes yet.</td></tr>'}</tbody>
        </table>
    </div>
    """
    return render_page("Notes", content)


@app.route("/notes/view")
@login_required
def view_note():
    filename = request.args.get("file", "")
    filepath = os.path.join("uploads", filename)

    try:
        with open(filepath, "r") as f:
            file_content = f.read()
    except Exception as e:
        file_content = f"Error reading file: {str(e)}"

    content = f"""
    <div class="card">
        <h2>📄 {filename}</h2>
        <pre style="background:rgba(0,0,0,0.3);padding:15px;border-radius:8px;overflow-x:auto;white-space:pre-wrap;">{file_content}</pre>
        <a href="/notes" class="btn btn-primary" style="margin-top:15px;">← Back</a>
    </div>
    """
    return render_page("View Note", content)


@app.route("/notes/download")
@login_required
def download_note():
    filename = request.args.get("file", "")
    cmd = f"cat uploads/{filename}"
    logger.debug(f"Running command: {cmd}")
    try:
        output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
        response = make_response(output)
        response.headers["Content-Disposition"] = f"attachment; filename={filename}"
        response.headers["Content-Type"] = "text/plain"
        return response
    except Exception as e:
        flash(f"Download error: {str(e)}", "error")
        return redirect(url_for('notes'))


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    db = get_db()

    if request.method == "POST":
        prefs_b64 = request.form.get("preferences", "")
        if prefs_b64:
            try:
                prefs_data = base64.b64decode(prefs_b64)
                preferences = pickle.loads(prefs_data)
                flash(f"Preferences loaded: {preferences}", "success")
            except Exception as e:
                flash(f"Error loading preferences: {str(e)}", "error")

        yaml_config = request.form.get("yaml_config", "")
        if yaml_config:
            try:
                config = yaml.load(yaml_config, Loader=yaml.FullLoader)
                flash(f"Config loaded: {config}", "success")
            except Exception as e:
                flash(f"YAML error: {str(e)}", "error")

    user = db.execute(
        f"SELECT * FROM users WHERE id = {session['user_id']}"
    ).fetchone()

    content = f"""
    <div class="card">
        <h2>👤 Profile</h2>
        <table>
            <tr><td style="color:#888;">Username</td><td>{user['username']}</td></tr>
            <tr><td style="color:#888;">Role</td><td>{user['role']}</td></tr>
            <tr><td style="color:#888;">User ID</td><td>{user['id']}</td></tr>
            <tr><td style="color:#888;">Password Hash</td><td style="font-family:monospace;font-size:12px;">{user['password']}</td></tr>
        </table>
    </div>

    <div class="card">
        <h2>⚙️ Preferences</h2>
        <form method="POST">
            <label style="color:#888;font-size:13px;">Import preferences (Base64 encoded):</label>
            <input type="text" name="preferences" placeholder="Paste exported preferences data...">
            <label style="color:#888;font-size:13px;">YAML Configuration:</label>
            <textarea name="yaml_config" placeholder="Enter YAML config..."></textarea>
            <button type="submit" class="btn btn-primary">Load Preferences</button>
        </form>
    </div>

    <div class="card">
        <h2>🔑 API Token</h2>
        <p style="font-family:monospace;background:rgba(0,0,0,0.3);padding:10px;border-radius:6px;word-break:break-all;">
            {base64.b64encode(json.dumps({{"user_id": session['user_id'], "role": session.get('role', 'user'), "secret": app.secret_key}}).encode()).decode()}
        </p>
    </div>
    """
    return render_page("Profile", content)


@app.route("/admin")
@login_required
def admin():
    db = get_db()
    users = db.execute("SELECT * FROM users").fetchall()
    all_todos = db.execute("SELECT * FROM todos").fetchall()

    user_rows = ""
    for user in users:
        user_rows += f"""
        <tr>
            <td>{user['id']}</td>
            <td>{user['username']}</td>
            <td>{user['role']}</td>
            <td style="font-family:monospace;font-size:11px;">{user['password']}</td>
            <td><a href="/admin/delete/{user['id']}" class="btn btn-danger btn-sm">Delete</a></td>
        </tr>
        """

    content = f"""
    <div class="card">
        <h2>🛡️ Admin Panel</h2>
        <h3 style="color:#7c83ff;margin-bottom:10px;">All Users</h3>
        <table>
            <thead>
                <tr><th>ID</th><th>Username</th><th>Role</th><th>Password Hash</th><th>Action</th></tr>
            </thead>
            <tbody>{user_rows}</tbody>
        </table>
    </div>
    <div class="card">
        <h2>📊 System Info</h2>
        <table>
            <tr><td style="color:#888;">Python Version</td><td>{os.sys.version}</td></tr>
            <tr><td style="color:#888;">Working Directory</td><td>{os.getcwd()}</td></tr>
            <tr><td style="color:#888;">Database</td><td>{os.path.abspath(DATABASE)}</td></tr>
            <tr><td style="color:#888;">Secret Key</td><td style="font-family:monospace;">{app.secret_key}</td></tr>
            <tr><td style="color:#888;">Total Users</td><td>{len(users)}</td></tr>
            <tr><td style="color:#888;">Total Tasks</td><td>{len(all_todos)}</td></tr>
        </table>
    </div>
    """
    return render_page("Admin", content)


@app.route("/admin/delete/<int:user_id>")
@login_required
def delete_user(user_id):
    db = get_db()
    db.execute(f"DELETE FROM users WHERE id = {user_id}")
    db.execute(f"DELETE FROM todos WHERE user_id = {user_id}")
    db.commit()
    flash(f"User {user_id} deleted.", "info")
    return redirect(url_for('admin'))


@app.route("/redirect")
def open_redirect():
    url = request.args.get("url", "/")
    return redirect(url)


@app.errorhandler(500)
def internal_error(error):
    import traceback
    return f"""
    <div style="background:#1a1a2e;color:#e0e0e0;padding:30px;font-family:monospace;">
        <h1 style="color:#ff4757;">500 Internal Server Error</h1>
        <pre style="background:rgba(0,0,0,0.3);padding:15px;border-radius:8px;overflow-x:auto;">
{traceback.format_exc()}
        </pre>
    </div>
    """, 500


@app.after_request
def add_headers(response):
    response.headers['Server'] = 'TaskManager/1.0 (Python/Flask)'
    response.headers['X-Powered-By'] = 'Flask'
    return response


if __name__ == "__main__":
    init_db()
    print("\n" + "=" * 40)
    print("  � Task Manager")
    print("=" * 40)
    print("  http://127.0.0.1:5002")
    print("=" * 40 + "\n")

    app.run(host="0.0.0.0", port=5002, debug=True)
