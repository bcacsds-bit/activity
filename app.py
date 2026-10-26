import os
import sqlite3
import secrets
import re
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, abort, flash, Response
import csv
import io
import json

# PostgreSQL support for hosted deployments (e.g. Neon). SQLite remains available locally.
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("QRTRAP_DB_PATH", os.path.join(APP_DIR, "campus_unlocked.db"))
ADMIN_TOKEN = os.environ.get("QRTRAP_ADMIN_TOKEN", "")
SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "")

app = Flask(__name__)
app.secret_key = SECRET_KEY or "dev-only-change-me"
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
    MAX_CONTENT_LENGTH=16 * 1024,
)

class DBConnection:
    """Small compatibility wrapper so existing qmark SQL works with SQLite and PostgreSQL."""
    def __init__(self, raw, postgres=False):
        self.raw = raw
        self.postgres = postgres
    def execute(self, sql, params=()):
        if self.postgres:
            sql = sql.replace("?", "%s")
        return self.raw.execute(sql, params)
    def __enter__(self):
        self.raw.__enter__()
        return self
    def __exit__(self, exc_type, exc, tb):
        return self.raw.__exit__(exc_type, exc, tb)

def connect_db():
    if DATABASE_URL:
        import psycopg
        from psycopg.rows import dict_row
        raw = psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=10)
        return DBConnection(raw, postgres=True)
    raw = sqlite3.connect(DB_PATH)
    raw.row_factory = sqlite3.Row
    return DBConnection(raw, postgres=False)

def init_db():
    with connect_db() as conn:
        if DATABASE_URL:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id BIGSERIAL PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    participant_group TEXT,
                    response TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS registrations (
                    id BIGSERIAL PRIMARY KEY,
                    full_name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    email TEXT NOT NULL,
                    participant_group TEXT NOT NULL,
                    activity_consent INTEGER NOT NULL,
                    updates_consent INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            """)
        else:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    participant_group TEXT,
                    response TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS registrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    full_name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    email TEXT NOT NULL,
                    participant_group TEXT NOT NULL,
                    activity_consent INTEGER NOT NULL,
                    updates_consent INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            """)

def now():
    return datetime.now(timezone.utc).isoformat()

def log_event(event_type, participant_group=None, response=None):
    with connect_db() as conn:
        conn.execute(
            """INSERT INTO events (event_type, participant_group, response, created_at)
               VALUES (?, ?, ?, ?)""",
            (event_type, participant_group, response, now())
        )

def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not ADMIN_TOKEN:
            abort(404)
        supplied = request.headers.get("X-Admin-Token", "")
        if not secrets.compare_digest(supplied, ADMIN_TOKEN):
            abort(403)
        return fn(*args, **kwargs)
    return wrapped

@app.before_request
def ensure_csrf_token():
    session.setdefault("_csrf", secrets.token_urlsafe(24))

@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self'; img-src 'self' data:; "
        "form-action 'self'; frame-ancestors 'none'; base-uri 'self'"
    )
    response.headers["Cache-Control"] = "no-store"
    return response

@app.get("/")
def index():
    log_event("landing_view")
    return render_template("index.html", csrf=session["_csrf"])

@app.post("/submit")
def submit():
    if not secrets.compare_digest(request.form.get("_csrf", ""), session.get("_csrf", "")):
        abort(400)

    name = request.form.get("full_name", "").strip()[:100]
    phone = request.form.get("phone", "").strip()[:25]
    email = request.form.get("email", "").strip().lower()[:254]
    group = request.form.get("participant_group", "")
    activity_consent = request.form.get("activity_consent") == "yes"
    updates_consent = request.form.get("updates_consent") == "yes"

    # Validate before storing anything. Do not collect student IDs, passwords,
    # financial details, or other sensitive information.
    phone_digits = re.sub(r"\D", "", phone)
    if not name or len(name) < 2:
        flash("Please enter your name.")
        return redirect(url_for("index"))
    if len(phone_digits) < 7 or len(phone_digits) > 15:
        flash("Please enter a valid phone number.")
        return redirect(url_for("index"))
    if "@" not in email or "." not in email.split("@")[-1]:
        flash("Please enter a valid email address.")
        return redirect(url_for("index"))
    if group not in {"student", "faculty", "staff", "visitor"}:
        flash("Please select your campus role.")
        return redirect(url_for("index"))
    if not activity_consent:
        flash("Please review the privacy notice and provide consent to register.")
        return redirect(url_for("index"))

    with connect_db() as conn:
        conn.execute(
            """INSERT INTO registrations
               (full_name, phone, email, participant_group, activity_consent,
                updates_consent, created_at)
               VALUES (?, ?, ?, ?, 1, ?, ?)""",
            (name, phone, email, group, int(updates_consent), now())
        )

    log_event("registration_submitted", participant_group=group)
    session["reveal_seen"] = True
    session["participant_group"] = group
    return redirect(url_for("reveal"))

@app.get("/reveal")
def reveal():
    if not session.get("reveal_seen"):
        return redirect(url_for("index"))
    return render_template("reveal.html", csrf=session["_csrf"])


@app.post("/feedback")
def submit_feedback():
    if not secrets.compare_digest(request.form.get("_csrf", ""), session.get("_csrf", "")):
        abort(400)
    qr_intention = request.form.get("qr_intention", "")
    key_takeaway = request.form.get("key_takeaway", "")
    if qr_intention not in {"Yes", "Maybe", "No change"}:
        flash("Please choose a response for the first question.")
        return redirect(url_for("reveal"))
    if key_takeaway not in {
        "Check the destination", "Question the promise",
        "Protect personal data", "Verify the source"
    }:
        flash("Please choose the takeaway that stood out most.")
        return redirect(url_for("reveal"))

    # Deliberately store feedback without name, phone, email, session ID, or registration ID.
    response_value = json.dumps(
        {"qr_intention": qr_intention, "key_takeaway": key_takeaway},
        ensure_ascii=False, separators=(",", ":")
    )
    log_event("anonymous_feedback", response=response_value)
    session["feedback_submitted"] = True
    return render_template("feedback_thanks.html")

@app.post("/awareness-complete")
def awareness_complete():
    if not secrets.compare_digest(request.form.get("_csrf", ""), session.get("_csrf", "")):
        abort(400)
    if not session.get("reveal_seen"):
        abort(400)
    log_event("reveal_acknowledged", participant_group=session.get("participant_group"))
    session.clear()
    return render_template("thanks.html")

@app.get("/admin/summary")
@admin_required
def admin_summary():
    with connect_db() as conn:
        counts = conn.execute(
            "SELECT event_type, COUNT(*) AS total FROM events GROUP BY event_type ORDER BY event_type"
        ).fetchall()
        groups = conn.execute(
            """SELECT participant_group, COUNT(*) AS total FROM events
               WHERE event_type='registration_submitted'
               GROUP BY participant_group ORDER BY participant_group"""
        ).fetchall()
        registrations = conn.execute(
            """SELECT full_name, phone, email, participant_group, updates_consent, created_at
               FROM registrations ORDER BY created_at DESC"""
        ).fetchall()
        feedback_rows = conn.execute(
            """SELECT response FROM events WHERE event_type='anonymous_feedback'
               AND response IS NOT NULL"""
        ).fetchall()

    intention_counts = {"Yes": 0, "Maybe": 0, "No change": 0}
    takeaway_counts = {
        "Check the destination": 0, "Question the promise": 0,
        "Protect personal data": 0, "Verify the source": 0
    }
    for row in feedback_rows:
        try:
            item = json.loads(row["response"])
            if item.get("qr_intention") in intention_counts:
                intention_counts[item["qr_intention"]] += 1
            if item.get("key_takeaway") in takeaway_counts:
                takeaway_counts[item["key_takeaway"]] += 1
        except (ValueError, TypeError):
            continue

    return render_template(
        "admin_summary.html", counts=counts, groups=groups, registrations=registrations,
        intention_counts=intention_counts, takeaway_counts=takeaway_counts,
        feedback_total=sum(intention_counts.values())
    )

@app.get("/admin/feedback.csv")
@admin_required
def export_feedback_csv():
    # Aggregate-only export; never exports names, phone numbers, or email addresses.
    with connect_db() as conn:
        rows = conn.execute(
            """SELECT response FROM events WHERE event_type='anonymous_feedback'
               AND response IS NOT NULL"""
        ).fetchall()
    intention_counts = {"Yes": 0, "Maybe": 0, "No change": 0}
    takeaway_counts = {
        "Check the destination": 0, "Question the promise": 0,
        "Protect personal data": 0, "Verify the source": 0
    }
    for row in rows:
        try:
            item = json.loads(row["response"])
            if item.get("qr_intention") in intention_counts:
                intention_counts[item["qr_intention"]] += 1
            if item.get("key_takeaway") in takeaway_counts:
                takeaway_counts[item["key_takeaway"]] += 1
        except (ValueError, TypeError):
            continue
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["metric", "response", "count"])
    for label, count in intention_counts.items():
        writer.writerow(["qr_scan_caution_intention", label, count])
    for label, count in takeaway_counts.items():
        writer.writerow(["key_takeaway", label, count])
    response = Response(output.getvalue(), mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = 'attachment; filename="campus_unlocked_anonymous_feedback.csv"'
    return response

@app.get("/health")
def health():
    return {"status": "ok"}

# Gunicorn imports this module instead of executing the __main__ block.
# Initialize schema at startup so a fresh hosted database is ready to use.
init_db()

if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=int(os.environ.get("PORT", "5000")))
