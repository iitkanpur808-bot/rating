"""Ideation Scoring - minimal Flask app.

Users sign in with Google, submit an ideation project rated 5-1 on basic
parameters with comments. Admins open /admin to see every submission and
average scores on a dashboard.
"""
import os
import sqlite3
from functools import wraps

from authlib.integrations.flask_client import OAuth
from flask import (Flask, abort, redirect, render_template, request, session,
                   url_for)

app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]

DB_PATH = os.environ.get("DB_PATH", "ideation.db")
ADMIN_EMAILS = {
    e.strip().lower()
    for e in os.environ.get("ADMIN_EMAILS", "").split(",")
    if e.strip()
}

PARAMETERS = [
    ("innovation", "Innovation"),
    ("feasibility", "Feasibility"),
    ("impact", "Impact"),
]

oauth = OAuth(app)
google = oauth.register(
    name="google",
    client_id=os.environ.get("GOOGLE_CLIENT_ID", ""),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET", ""),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                user_name TEXT,
                project_title TEXT NOT NULL,
                project_idea TEXT,
                innovation INTEGER NOT NULL,
                feasibility INTEGER NOT NULL,
                impact INTEGER NOT NULL,
                comments TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )


init_db()


def current_user():
    return session.get("user")


@app.context_processor
def inject_globals():
    return {"admin_emails": ADMIN_EMAILS}


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login"))
        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            return redirect(url_for("login"))
        if user["email"].lower() not in ADMIN_EMAILS:
            abort(403)
        return fn(*args, **kwargs)

    return wrapper


@app.route("/")
def index():
    user = current_user()
    return render_template("index.html", user=user, parameters=PARAMETERS)


@app.route("/login")
def login():
    return google.authorize_redirect(url_for("callback", _external=True))


@app.route("/callback")
def callback():
    token = google.authorize_access_token()
    info = token.get("userinfo") or google.parse_id_token(token)
    session["user"] = {
        "email": info["email"],
        "name": info.get("name", info["email"]),
    }
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/submit", methods=["POST"])
@login_required
def submit():
    user = current_user()
    title = request.form.get("project_title", "").strip()
    idea = request.form.get("project_idea", "").strip()
    comments = request.form.get("comments", "").strip()
    scores = {}
    for key, _ in PARAMETERS:
        try:
            value = int(request.form.get(key, ""))
        except ValueError:
            value = 0
        if not 1 <= value <= 5:
            return render_template(
                "index.html",
                user=user,
                parameters=PARAMETERS,
                error="Please pick a score between 5 and 1 for every parameter.",
            ), 400
        scores[key] = value
    if not title:
        return render_template(
            "index.html",
            user=user,
            parameters=PARAMETERS,
            error="Project title is required.",
        ), 400
    with db() as conn:
        conn.execute(
            """INSERT INTO submissions
               (user_email, user_name, project_title, project_idea,
                innovation, feasibility, impact, comments)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user["email"], user["name"], title, idea,
                scores["innovation"], scores["feasibility"], scores["impact"],
                comments,
            ),
        )
    return redirect(url_for("thanks"))


@app.route("/thanks")
@login_required
def thanks():
    return render_template("thanks.html", user=current_user())


@app.route("/my")
@login_required
def my_submissions():
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM submissions WHERE user_email = ? ORDER BY id DESC",
            (current_user()["email"],),
        ).fetchall()
    return render_template(
        "my.html", user=current_user(), rows=rows, parameters=PARAMETERS
    )


@app.route("/admin")
@admin_required
def admin():
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM submissions ORDER BY id DESC"
        ).fetchall()
        stats = conn.execute(
            """SELECT COUNT(*) AS n,
                      ROUND(AVG(innovation), 2) AS innovation,
                      ROUND(AVG(feasibility), 2) AS feasibility,
                      ROUND(AVG(impact), 2) AS impact,
                      ROUND(AVG((innovation + feasibility + impact) / 3.0), 2) AS overall
               FROM submissions"""
        ).fetchone()
    return render_template(
        "admin.html",
        user=current_user(),
        rows=rows,
        stats=stats,
        parameters=PARAMETERS,
    )


@app.route("/healthz")
def healthz():
    return {"status": "ok"}


@app.errorhandler(403)
def forbidden(_):
    return render_template("forbidden.html", user=current_user()), 403


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
