# Task Manager

## Vision

The Task Manager is a lightweight, self‑contained web application that enables individuals and small teams to create, track, and organize personal or shared to‑do items. Built with Python and Flask, it provides a straightforward user experience while exposing essential features such as user authentication, task CRUD operations, note attachments, and an administrative panel for user management.

Designed for rapid onboarding and easy local deployment, the application serves both as a practical productivity tool and as a reference implementation for Flask‑based CRUD systems that rely on SQLite for persistence and inline HTML templates for the front‑end.

---

## Architecture

The system follows a classic three‑tier architecture implemented entirely within a single Python process:

1. **Presentation Layer** – Inline HTML/CSS templates rendered by Flask’s `render_template_string` function. All UI interactions occur through standard HTTP requests.
2. **Application Layer** – Flask routes handle request validation, session management, and business logic. Core utilities such as authentication, file handling (Base64/YAML import), and token generation are implemented directly in `app.py`.
3. **Data Layer** – A SQLite database (`todo.db`) stores user accounts and task records. The `sqlite3` module is wrapped by a lightweight helper (`get_db`) that provides a per‑request connection via Flask’s `g` context.

The code imports a handful of standard‑library modules (`os`, `hashlib`, `pickle`, `base64`, `subprocess`, `json`, `yaml`, `logging`) and third‑party libraries listed in `requirements.txt`. No external services (e.g., Redis, message queues) are required; the entire stack runs in‑process.

---

## Key Components

| Component | Location | Responsibility |
|-----------|----------|----------------|
| **Flask Application** | `app.py` | Defines routes, session handling, authentication, and the main request/response cycle. |
| **Database Layer** | `todo.db` (auto‑created) | Persists users and tasks; schema is created by `init_db()` on first run. |
| **Static/Upload Storage** | `uploads/` (auto‑created at runtime) | Holds optional file attachments for notes; managed via Flask’s `send_file` and `make_response`. |
| **Configuration & Secrets** | `app.py` (hard‑coded `app.secret_key`) | Provides Flask session signing; in production this should be externalised. |
| **Logging** | `app.log` (auto‑created) | Captures debug and info messages using Python’s `logging` module. |
| **Development Helpers** | `.vscode/` (settings, tasks) | VS Code workspace configuration; not required for runtime. |

---

## Tech Stack

| Category | Technology | Version (as pinned in `requirements.txt`) |
|----------|------------|--------------------------------------------|
| Language | Python | 3.11 (runtime) |
| Web Framework | Flask | 3.0.0 |
| Template Engine | Jinja2 (bundled with Flask) | 3.1.2 |
| WSGI Server | Werkzeug | 3.0.0 |
| Database | SQLite (standard library) | – |
| Configuration / Serialization | PyYAML | 6.0.1 |
| HTTP Client (used by scripts) | requests | 2.31.0 |
| Security / Signing | itsdangerous | 2.1.2 |
| Markup Safety | MarkupSafe | 2.1.3 |
| Networking utilities | urllib3 | 2.0.4 |
| Certificate bundle | certifi | 2023.7.22 |
| SSH / SFTP support (optional) | paramiko | 2.12.0 |
| Standard Library | `os`, `sqlite3`, `subprocess`, `pickle`, `base64`, `hashlib`, `json`, `logging`, `functools.wraps` | – |

---

## Flow of Operation

1. **Client Request** – A browser or API client issues an HTTP request (e.g., `GET /login`, `POST /login`, `GET /todos`).
2. **Flask Routing** – Flask matches the URL to a view function defined in `app.py`. The view may render an HTML template or return JSON.
3. **Session / Authentication** – If the endpoint requires authentication, the view checks `session` for a logged‑in user. Login attempts are logged (`logger.info`) and validated against the `users` table.
4. **Database Interaction** – The helper `get_db()` provides a connection bound to the request context. CRUD operations are executed via `sqlite3.Cursor` objects.
5. **Business Logic** – Tasks are created, marked complete, or deleted; notes may be stored as Base64/YAML payloads; admin users can manage other accounts.
6. **Response Generation** – Results are either rendered with `render_template_string` (HTML) or returned as JSON. Files are served with `send_file` when needed.
7. **Teardown** – After the response, Flask’s `@app.teardown_appcontext` hook closes the SQLite connection.

---

## Interaction

The primary user‑facing endpoints (as observed in the logs and typical implementation) are:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Root endpoint; redirects to `/login` or `/todos` based on authentication state. |
| `GET` | `/login` | Renders the login page. |
| `POST` | `/login` | Processes credentials; on success creates a session and redirects to `/todos`. |
| `GET` | `/todos` | Displays the authenticated user’s task list. |
| `POST` | `/todos/add` | Creates a new task (title, description). |
| `POST` | `/todos/<id>/complete` | Marks a task as completed. |
| `POST` | `/todos/<id>/delete` | Removes a task from the database. |
| `GET` | `/profile` | Shows user profile and preferences import/export (Base64/YAML). |
| `GET` | `/admin/users` | Admin‑only view for managing user accounts. |
| `GET` | `/api/token` | Generates a short‑lived API token for programmatic access. |

All endpoints respect Flask’s session cookie; CSRF protection is provided by Flask’s built‑in mechanisms when `app.secret_key` is set.

---

## Deployment

### Local Development (the quickest way)

```bash
# 1. Clone the repository
git clone https://github.com/your-org/devops-by-examples/python-task-manager.git
cd python-task-manager

# 2. Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Initialise the database (first run only)
python -c "import app; app.init_db()"

# 5. Run the application
python app.py
```

The server will start on **http://127.0.0.1:5002** (as configured in the log output). Use the default admin credentials (`admin` / `admin123`) to explore the admin panel.

### Dockerised Production‑Ready Deployment

A minimal Dockerfile can be used to package the app:

```Dockerfile
# Use official Python slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy only the necessary files
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY todo.db .   # optional: copy a pre‑seeded DB; otherwise it will be created at runtime

# Expose the Flask port (default 5002)
EXPOSE 5002

# Environment variables
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5002
ENV FLASK_ENV=production

# Run the application
CMD ["flask", "run"]
```

Build and run the container:

```bash
docker build -t task-manager:2.0 .
docker run -d -p 5002:5002 --name task-manager task-manager:2.0
```

The container will start the Flask development server in production mode. For a true production environment replace the built‑in server with a WSGI server such as **gunicorn**:

```Dockerfile
# ... previous steps unchanged ...
RUN pip install gunicorn
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5002", "app:app"]
```

### Persistence Considerations

* **Database** – Mount a host directory or Docker volume to `/app/todo.db` so that task data survives container restarts.
* **Uploads** – If the application is extended to accept file attachments, mount a volume to `/app/uploads`.
* **Secrets** – Replace the hard‑coded `app.secret_key` with an environment variable (`FLASK_SECRET_KEY`) and reference it in `app.py` for production security.

---

## License & Contributions

This project is provided under the MIT License. Contributions are welcome via pull requests; please ensure that any new public API (routes, database schema changes, or configuration options) is accompanied by corresponding updates to this README.
