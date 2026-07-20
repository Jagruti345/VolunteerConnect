"""
VolunteerConnect - Flask application.

Real, working backend:
- Anyone can browse events and register as a volunteer.
- NGOs log in to post new events and see exactly who registered
  for each one (with CSV export).
- Data is stored in SQLite at data/volunteerconnect.db, which lives
  outside the deployed code path so redeployments never wipe it.
"""

import csv
import io
import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, g, Response
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "volunteerconnect.db")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme123")

CATEGORIES = [
    "Food Distribution", "Teaching", "Medical Camps", "Tree Plantation",
    "Animal Rescue", "Blood Donation", "Disaster Relief",
    "Women Empowerment", "Old Age Home",
]


# ---------------------------------------------------------------- database
def get_db():
    if "db" not in g:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            location TEXT NOT NULL,
            event_date TEXT NOT NULL,
            seats INTEGER NOT NULL DEFAULT 0,
            organizer TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            age INTEGER,
            skills TEXT,
            location TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (event_id) REFERENCES events (id)
        )
    """)
    conn.commit()
    conn.close()


# ------------------------------------------------------------------ auth
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Please log in to access the NGO dashboard.", "error")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return wrapper


# --------------------------------------------------------------- public
@app.route("/")
def home():
    db = get_db()
    upcoming = db.execute(
        "SELECT e.*, "
        "(SELECT COUNT(*) FROM registrations r WHERE r.event_id = e.id) AS registered "
        "FROM events e ORDER BY e.event_date ASC LIMIT 3"
    ).fetchall()
    stats = {
        "events": db.execute("SELECT COUNT(*) c FROM events").fetchone()["c"],
        "volunteers": db.execute(
            "SELECT COUNT(DISTINCT email) c FROM registrations"
        ).fetchone()["c"],
        "registrations": db.execute("SELECT COUNT(*) c FROM registrations").fetchone()["c"],
        "ngos": 1,
    }
    return render_template("index.html", events=upcoming, stats=stats)


@app.route("/events")
def events():
    db = get_db()
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "all")

    sql = (
        "SELECT e.*, "
        "(SELECT COUNT(*) FROM registrations r WHERE r.event_id = e.id) AS registered "
        "FROM events e WHERE 1=1"
    )
    params = []
    if q:
        sql += " AND (e.title LIKE ? OR e.description LIKE ? OR e.location LIKE ?)"
        like = f"%{q}%"
        params += [like, like, like]
    if category != "all":
        sql += " AND e.category = ?"
        params.append(category)
    sql += " ORDER BY e.event_date ASC"

    rows = db.execute(sql, params).fetchall()
    return render_template(
        "events.html", events=rows, categories=CATEGORIES, q=q, category=category
    )


@app.route("/events/<int:event_id>", methods=["GET", "POST"])
def event_detail(event_id):
    db = get_db()
    event = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event:
        flash("That event doesn't exist (it may have been removed).", "error")
        return redirect(url_for("events"))

    registered_count = db.execute(
        "SELECT COUNT(*) c FROM registrations WHERE event_id = ?", (event_id,)
    ).fetchone()["c"]
    seats_left = max(event["seats"] - registered_count, 0)

    if request.method == "POST":
        if seats_left <= 0:
            flash("Sorry, this event is fully booked.", "error")
            return redirect(url_for("event_detail", event_id=event_id))

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        age = request.form.get("age", "").strip()
        skills = request.form.get("skills", "").strip()
        location = request.form.get("location", "").strip()

        if not name or not email or not phone:
            flash("Name, email, and phone are required.", "error")
            return redirect(url_for("event_detail", event_id=event_id))

        already = db.execute(
            "SELECT id FROM registrations WHERE event_id = ? AND email = ?",
            (event_id, email),
        ).fetchone()
        if already:
            flash("You're already registered for this event.", "error")
            return redirect(url_for("event_detail", event_id=event_id))

        db.execute(
            "INSERT INTO registrations "
            "(event_id, name, email, phone, age, skills, location, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (event_id, name, email, phone, age or None, skills, location,
             datetime.now().isoformat()),
        )
        db.commit()
        flash("You're registered! The organizer will contact you with details.", "success")
        return redirect(url_for("event_detail", event_id=event_id))

    return render_template("event_detail.html", event=event, seats_left=seats_left,
                            registered_count=registered_count)


# --------------------------------------------------------------- admin
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == ADMIN_PASSWORD:
            session["is_admin"] = True
            flash("Welcome back.", "success")
            return redirect(url_for("admin_dashboard"))
        flash("Incorrect password.", "error")
    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    flash("Logged out.", "success")
    return redirect(url_for("home"))


@app.route("/admin")
@login_required
def admin_dashboard():
    db = get_db()
    rows = db.execute(
        "SELECT e.*, "
        "(SELECT COUNT(*) FROM registrations r WHERE r.event_id = e.id) AS registered "
        "FROM events e ORDER BY e.event_date ASC"
    ).fetchall()
    totals = {
        "events": len(rows),
        "registrations": db.execute("SELECT COUNT(*) c FROM registrations").fetchone()["c"],
    }
    return render_template("admin_dashboard.html", events=rows, totals=totals)


@app.route("/admin/events/new", methods=["GET", "POST"])
@login_required
def admin_new_event():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        location = request.form.get("location", "").strip()
        event_date = request.form.get("event_date", "").strip()
        seats = request.form.get("seats", "0").strip()
        organizer = request.form.get("organizer", "").strip()

        if not all([title, category, description, location, event_date, organizer]):
            flash("Please fill in all required fields.", "error")
            return render_template("admin_new_event.html", categories=CATEGORIES,
                                    form=request.form)

        db = get_db()
        db.execute(
            "INSERT INTO events "
            "(title, category, description, location, event_date, seats, organizer, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (title, category, description, location, event_date,
             int(seats or 0), organizer, datetime.now().isoformat()),
        )
        db.commit()
        flash(f"Event '{title}' is live.", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("admin_new_event.html", categories=CATEGORIES, form={})


@app.route("/admin/events/<int:event_id>/edit", methods=["GET", "POST"])
@login_required
def admin_edit_event(event_id):
    db = get_db()
    event = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event:
        flash("Event not found.", "error")
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        location = request.form.get("location", "").strip()
        event_date = request.form.get("event_date", "").strip()
        seats = request.form.get("seats", "0").strip()
        organizer = request.form.get("organizer", "").strip()

        if not all([title, category, description, location, event_date, organizer]):
            flash("Please fill in all required fields.", "error")
            return render_template("admin_new_event.html", categories=CATEGORIES,
                                    form=request.form, editing=event_id)

        db.execute(
            "UPDATE events SET title=?, category=?, description=?, location=?, "
            "event_date=?, seats=?, organizer=? WHERE id=?",
            (title, category, description, location, event_date,
             int(seats or 0), organizer, event_id),
        )
        db.commit()
        flash(f"Event '{title}' updated.", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("admin_new_event.html", categories=CATEGORIES,
                            form=event, editing=event_id)


@app.route("/admin/events/<int:event_id>/volunteers")
@login_required
def admin_event_volunteers(event_id):
    db = get_db()
    event = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event:
        flash("Event not found.", "error")
        return redirect(url_for("admin_dashboard"))
    volunteers = db.execute(
        "SELECT * FROM registrations WHERE event_id = ? ORDER BY created_at DESC",
        (event_id,),
    ).fetchall()
    return render_template("admin_event_volunteers.html", event=event, volunteers=volunteers)


@app.route("/admin/events/<int:event_id>/volunteers/export")
@login_required
def admin_export_volunteers(event_id):
    db = get_db()
    event = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event:
        flash("Event not found.", "error")
        return redirect(url_for("admin_dashboard"))

    volunteers = db.execute(
        "SELECT * FROM registrations WHERE event_id = ? ORDER BY created_at", (event_id,)
    ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Email", "Phone", "Age", "Skills", "Location", "Registered At"])
    for v in volunteers:
        writer.writerow([v["name"], v["email"], v["phone"], v["age"],
                          v["skills"], v["location"], v["created_at"]])

    filename = f"volunteers_{event['title'].replace(' ', '_')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"},
    )


@app.route("/admin/events/<int:event_id>/delete", methods=["POST"])
@login_required
def admin_delete_event(event_id):
    db = get_db()
    db.execute("DELETE FROM registrations WHERE event_id = ?", (event_id,))
    db.execute("DELETE FROM events WHERE id = ?", (event_id,))
    db.commit()
    flash("Event and its registrations were deleted.", "success")
    return redirect(url_for("admin_dashboard"))


init_db()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
