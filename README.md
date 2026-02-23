# 📋 Task Manager

A simple and clean task management application built with Python and Flask.

## Features

- User registration and login
- Create, complete, and delete tasks
- Search tasks
- Save and manage notes with file attachments
- User profiles with preferences import (Base64 / YAML)
- Admin panel for user management
- API token generation

## Quick Start

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5002

## Default Admin Account

- **Username:** admin
- **Password:** admin123

## Tech Stack

- **Backend:** Python / Flask
- **Database:** SQLite
- **Frontend:** Inline HTML/CSS templates

## Project Structure

```
python-todo-app/
├── app.py              # Main application
├── requirements.txt    # Python dependencies
├── todo.db             # SQLite database (auto-created)
├── uploads/            # Note file storage (auto-created)
└── app.log             # Application logs (auto-created)
```
