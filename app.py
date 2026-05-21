# ============================================================
# app.py — Smart Parking System (ITS Project)
# Main Flask application: all routes, database logic, auth
# ============================================================

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import math
from datetime import datetime

# ------------------------------------
# App Configuration
# ------------------------------------
app = Flask(__name__)
app.secret_key = 'its_parking_secret_2024'   # secret key for sessions

DATABASE = 'database.db'   # SQLite database file name


# ------------------------------------
# Database Helper Functions
# ------------------------------------

def get_db():
    """Open a database connection."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row   # lets us access columns by name
    return conn


def init_db():
    """Initialize the database using schema.sql, then seed demo data."""
    with app.app_context():
        conn = get_db()
        # Read and run the schema
        with open('schema.sql', 'r') as f:
            conn.executescript(f.read())

        # Seed an admin account if none exists
        admin = conn.execute("SELECT * FROM users WHERE role='admin'").fetchone()
        if not admin:
            hashed = generate_password_hash('admin123')
            conn.execute(
                "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
                ('Admin User', 'admin@parking.com', hashed, 'admin')
            )

        # Seed parking slots if none exist
        count = conn.execute("SELECT COUNT(*) FROM parking_slots").fetchone()[0]
        if count == 0:
            slots = [
                ('A1', 'Block A - Ground Floor', 'car',   30.0),
                ('A2', 'Block A - Ground Floor', 'car',   30.0),
                ('A3', 'Block A - Ground Floor', 'car',   30.0),
                ('A4', 'Block A - Ground Floor', 'bike',  15.0),
                ('A5', 'Block A - Ground Floor', 'bike',  15.0),
                ('B1', 'Block B - Level 1',      'car',   40.0),
                ('B2', 'Block B - Level 1',      'car',   40.0),
                ('B3', 'Block B - Level 1',      'car',   40.0),
                ('B4', 'Block B - Level 1',      'truck', 60.0),
                ('B5', 'Block B - Level 1',      'truck', 60.0),
                ('C1', 'Block C - Level 2',      'car',   35.0),
                ('C2', 'Block C - Level 2',      'car',   35.0),
                ('C3', 'Block C - Level 2',      'bike',  15.0),
                ('C4', 'Block C - Level 2',      'bike',  15.0),
                ('C5', 'Block C - Level 2',      'car',   35.0),
            ]
            conn.executemany(
                "INSERT INTO parking_slots (slot_number, location, vehicle_type, rate_per_hour) VALUES (?, ?, ?, ?)",
                slots
            )

        conn.commit()
        conn.close()
        print("Database initialized with demo data.")


# ------------------------------------
# Authentication Helpers
# ------------------------------------

def login_required(f):
    """Decorator: redirect to login if user not in session."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Decorator: redirect if user is not admin."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


# ------------------------------------
# Public Routes
# ------------------------------------

@app.route('/')
def index():
    """Landing page with system overview."""
    conn = get_db()
    total   = conn.execute("SELECT COUNT(*) FROM parking_slots").fetchone()[0]
    avail   = conn.execute("SELECT COUNT(*) FROM parking_slots WHERE status='available'").fetchone()[0]
    occupied = total - avail
    conn.close()
    return render_template('index.html', total=total, avail=avail, occupied=occupied)


@app.route('/register', methods=['GET', 'POST'])
def register():
    """User signup page."""
    if request.method == 'POST':
        name     = request.form['name'].strip()
        email    = request.form['email'].strip().lower()
        password = request.form['password']

        if not name or not email or not password:
            flash('All fields are required.', 'danger')
            return redirect(url_for('register'))

        hashed = generate_password_hash(password)
        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                (name, email, hashed)
            )
            conn.commit()
            flash('Account created! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email already registered.', 'danger')
        finally:
            conn.close()

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """User & admin login page."""
    if request.method == 'POST':
        email    = request.form['email'].strip().lower()
        password = request.form['password']

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['name']    = user['name']
            session['role']    = user['role']
            flash(f'Welcome back, {user["name"]}!', 'success')
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'danger')

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Clear session and redirect to home."""
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('index'))


# ------------------------------------
# User Routes
# ------------------------------------

@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard — shows all parking slots with status."""
    conn = get_db()
    slots = conn.execute("SELECT * FROM parking_slots ORDER BY slot_number").fetchall()

    # Get user's currently active booking (if any)
    active_booking = conn.execute(
        """SELECT b.*, s.slot_number FROM bookings b
           JOIN parking_slots s ON b.slot_id = s.id
           WHERE b.user_id=? AND b.status='active'""",
        (session['user_id'],)
    ).fetchone()

    conn.close()
    return render_template('dashboard.html', slots=slots, active_booking=active_booking)


@app.route('/book/<int:slot_id>', methods=['GET', 'POST'])
@login_required
def book_slot(slot_id):
    """Book a specific parking slot."""
    conn = get_db()

    # Prevent double booking
    existing = conn.execute(
        "SELECT * FROM bookings WHERE user_id=? AND status='active'",
        (session['user_id'],)
    ).fetchone()
    if existing:
        flash('You already have an active booking. Please exit first.', 'warning')
        conn.close()
        return redirect(url_for('dashboard'))

    slot = conn.execute("SELECT * FROM parking_slots WHERE id=?", (slot_id,)).fetchone()

    if not slot:
        flash('Slot not found.', 'danger')
        conn.close()
        return redirect(url_for('dashboard'))

    if slot['status'] == 'occupied':
        flash('This slot is already occupied. Please choose another.', 'warning')
        conn.close()
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        vehicle_number = request.form['vehicle_number'].strip().upper()
        if not vehicle_number:
            flash('Please enter your vehicle number.', 'danger')
            conn.close()
            return render_template('booking.html', slot=slot)

        # Create booking record
        start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute(
            """INSERT INTO bookings (user_id, slot_id, vehicle_number, start_time)
               VALUES (?, ?, ?, ?)""",
            (session['user_id'], slot_id, vehicle_number, start_time)
        )
        # Mark slot as occupied
        conn.execute("UPDATE parking_slots SET status='occupied' WHERE id=?", (slot_id,))
        conn.commit()
        flash(f'Slot {slot["slot_number"]} booked successfully! 🎉', 'success')
        conn.close()
        return redirect(url_for('dashboard'))

    conn.close()
    return render_template('booking.html', slot=slot)


@app.route('/exit/<int:booking_id>', methods=['POST'])
@login_required
def exit_slot(booking_id):
    """User exits parking: calculate cost and free the slot."""
    conn = get_db()
    booking = conn.execute(
        "SELECT * FROM bookings WHERE id=? AND user_id=? AND status='active'",
        (booking_id, session['user_id'])
    ).fetchone()

    if not booking:
        flash('Booking not found.', 'danger')
        conn.close()
        return redirect(url_for('dashboard'))

    # Calculate duration and cost
    start = datetime.strptime(booking['start_time'], '%Y-%m-%d %H:%M:%S')
    end   = datetime.now()
    duration_minutes = int((end - start).total_seconds() / 60)
    if duration_minutes < 1:
        duration_minutes = 1   # minimum 1 minute

    slot = conn.execute("SELECT * FROM parking_slots WHERE id=?", (booking['slot_id'],)).fetchone()
    # Cost = ceil(hours) × rate (minimum 1 hour billed)
    hours_billed = max(math.ceil(duration_minutes / 60), 1)
    total_cost   = hours_billed * slot['rate_per_hour']

    # Update booking record
    conn.execute(
        """UPDATE bookings
           SET end_time=?, duration_minutes=?, total_cost=?, status='completed'
           WHERE id=?""",
        (end.strftime('%Y-%m-%d %H:%M:%S'), duration_minutes, total_cost, booking_id)
    )
    # Free the slot
    conn.execute("UPDATE parking_slots SET status='available' WHERE id=?", (booking['slot_id'],))
    conn.commit()
    conn.close()

    flash('You have exited successfully. Here is your receipt.', 'success')
    return redirect(url_for('receipt', booking_id=booking_id))


@app.route('/receipt/<int:booking_id>')
@login_required
def receipt(booking_id):
    """Show parking receipt after exit."""
    conn = get_db()
    booking = conn.execute(
        """SELECT b.*, s.slot_number, s.location, s.rate_per_hour, s.vehicle_type,
                  u.name as user_name, u.email as user_email
           FROM bookings b
           JOIN parking_slots s ON b.slot_id = s.id
           JOIN users u ON b.user_id = u.id
           WHERE b.id=? AND b.user_id=?""",
        (booking_id, session['user_id'])
    ).fetchone()
    conn.close()

    if not booking:
        flash('Receipt not found.', 'danger')
        return redirect(url_for('dashboard'))

    return render_template('receipt.html', booking=booking)


@app.route('/my_bookings')
@login_required
def my_bookings():
    """Show user's booking history."""
    conn = get_db()
    bookings = conn.execute(
        """SELECT b.*, s.slot_number, s.location, s.vehicle_type
           FROM bookings b
           JOIN parking_slots s ON b.slot_id = s.id
           WHERE b.user_id=?
           ORDER BY b.start_time DESC""",
        (session['user_id'],)
    ).fetchall()
    conn.close()
    return render_template('my_bookings.html', bookings=bookings)


# ------------------------------------
# Admin Routes
# ------------------------------------

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    """Admin overview dashboard with statistics."""
    conn = get_db()
    total_slots  = conn.execute("SELECT COUNT(*) FROM parking_slots").fetchone()[0]
    avail_slots  = conn.execute("SELECT COUNT(*) FROM parking_slots WHERE status='available'").fetchone()[0]
    total_users  = conn.execute("SELECT COUNT(*) FROM users WHERE role='user'").fetchone()[0]
    total_books  = conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
    active_books = conn.execute("SELECT COUNT(*) FROM bookings WHERE status='active'").fetchone()[0]
    revenue      = conn.execute("SELECT SUM(total_cost) FROM bookings WHERE status='completed'").fetchone()[0] or 0.0
    recent_books = conn.execute(
        """SELECT b.*, s.slot_number, u.name as user_name
           FROM bookings b
           JOIN parking_slots s ON b.slot_id = s.id
           JOIN users u ON b.user_id = u.id
           ORDER BY b.start_time DESC LIMIT 5"""
    ).fetchall()
    conn.close()
    return render_template('admin/admin_dashboard.html',
        total_slots=total_slots, avail_slots=avail_slots,
        total_users=total_users, total_books=total_books,
        active_books=active_books, revenue=revenue,
        recent_books=recent_books
    )


@app.route('/admin/slots')
@login_required
@admin_required
def manage_slots():
    """Admin: view and manage parking slots."""
    conn = get_db()
    slots = conn.execute("SELECT * FROM parking_slots ORDER BY slot_number").fetchall()
    conn.close()
    return render_template('admin/manage_slots.html', slots=slots)


@app.route('/admin/slots/add', methods=['POST'])
@login_required
@admin_required
def add_slot():
    """Admin: add a new parking slot."""
    slot_number  = request.form['slot_number'].strip().upper()
    location     = request.form['location'].strip()
    vehicle_type = request.form['vehicle_type']
    rate         = float(request.form['rate_per_hour'])

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO parking_slots (slot_number, location, vehicle_type, rate_per_hour) VALUES (?, ?, ?, ?)",
            (slot_number, location, vehicle_type, rate)
        )
        conn.commit()
        flash(f'Slot {slot_number} added successfully.', 'success')
    except sqlite3.IntegrityError:
        flash(f'Slot number {slot_number} already exists.', 'danger')
    finally:
        conn.close()
    return redirect(url_for('manage_slots'))


@app.route('/admin/slots/delete/<int:slot_id>', methods=['POST'])
@login_required
@admin_required
def delete_slot(slot_id):
    """Admin: delete a parking slot (only if not occupied)."""
    conn = get_db()
    slot = conn.execute("SELECT * FROM parking_slots WHERE id=?", (slot_id,)).fetchone()
    if slot and slot['status'] == 'occupied':
        flash('Cannot delete an occupied slot.', 'danger')
    else:
        conn.execute("DELETE FROM parking_slots WHERE id=?", (slot_id,))
        conn.commit()
        flash('Slot deleted.', 'success')
    conn.close()
    return redirect(url_for('manage_slots'))


@app.route('/admin/slots/toggle/<int:slot_id>', methods=['POST'])
@login_required
@admin_required
def toggle_slot(slot_id):
    """Admin: manually toggle slot status."""
    conn = get_db()
    slot = conn.execute("SELECT * FROM parking_slots WHERE id=?", (slot_id,)).fetchone()
    if slot:
        new_status = 'available' if slot['status'] == 'occupied' else 'occupied'
        conn.execute("UPDATE parking_slots SET status=? WHERE id=?", (new_status, slot_id))
        conn.commit()
        flash(f'Slot {slot["slot_number"]} status changed to {new_status}.', 'info')
    conn.close()
    return redirect(url_for('manage_slots'))


@app.route('/admin/bookings')
@login_required
@admin_required
def all_bookings():
    """Admin: view all bookings in the system."""
    conn = get_db()
    bookings = conn.execute(
        """SELECT b.*, s.slot_number, s.location, u.name as user_name, u.email as user_email
           FROM bookings b
           JOIN parking_slots s ON b.slot_id = s.id
           JOIN users u ON b.user_id = u.id
           ORDER BY b.start_time DESC"""
    ).fetchall()
    conn.close()
    return render_template('admin/all_bookings.html', bookings=bookings)


# ------------------------------------
# API Endpoint (for live status refresh)
# ------------------------------------

@app.route('/api/slots')
def api_slots():
    """Return slot statuses as JSON — used by JS auto-refresh."""
    conn = get_db()
    slots = conn.execute("SELECT id, slot_number, status FROM parking_slots").fetchall()
    conn.close()
    return jsonify([dict(s) for s in slots])


# ------------------------------------
# Run the App
# ------------------------------------


if __name__ == '__main__':
    init_db()      # create tables + seed data on first run

    import os
    port = int(os.environ.get("PORT", 5000))

    app.run(host="0.0.0.0", port=port, debug=True)