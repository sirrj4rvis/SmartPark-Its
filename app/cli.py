"""
cli.py — Flask CLI commands.

  flask seed            -> create tables + demo admin + demo slots
  flask create-admin    -> create/update an admin account
"""
import click
from flask import current_app

from .extensions import db
from .models import ParkingSlot, Role, User, VehicleType

DEMO_SLOTS = [
    ("A1", "Block A - Ground Floor", "car", 30.0),
    ("A2", "Block A - Ground Floor", "car", 30.0),
    ("A3", "Block A - Ground Floor", "car", 30.0),
    ("A4", "Block A - Ground Floor", "bike", 15.0),
    ("A5", "Block A - Ground Floor", "bike", 15.0),
    ("B1", "Block B - Level 1", "car", 40.0),
    ("B2", "Block B - Level 1", "car", 40.0),
    ("B3", "Block B - Level 1", "car", 40.0),
    ("B4", "Block B - Level 1", "truck", 60.0),
    ("B5", "Block B - Level 1", "truck", 60.0),
    ("C1", "Block C - Level 2", "car", 35.0),
    ("C2", "Block C - Level 2", "car", 35.0),
    ("C3", "Block C - Level 2", "bike", 15.0),
    ("C4", "Block C - Level 2", "bike", 15.0),
    ("C5", "Block C - Level 2", "car", 35.0),
]


def seed_data():
    db.create_all()
    if not db.session.query(User).filter_by(role=Role.admin).first():
        admin = User(name="Admin User", email="admin@parking.com", role=Role.admin)
        admin.set_password("admin123")
        db.session.add(admin)
    if db.session.query(ParkingSlot).count() == 0:
        for number, location, vt, rate in DEMO_SLOTS:
            db.session.add(
                ParkingSlot(slot_number=number, location=location,
                            vehicle_type=VehicleType(vt), base_rate=rate)
            )
    db.session.commit()


def register_cli(app):
    @app.cli.command("seed")
    def seed():
        """Create tables and seed demo admin + slots."""
        seed_data()
        click.echo("Seeded database with demo admin and slots.")

    @app.cli.command("create-admin")
    @click.option("--email", required=True)
    @click.option("--password", required=True)
    @click.option("--name", default="Administrator")
    def create_admin(email, password, name):
        """Create or promote an admin user."""
        user = db.session.query(User).filter_by(email=email.lower()).first()
        if not user:
            user = User(name=name, email=email.lower(), role=Role.admin)
        user.role = Role.admin
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Admin ready: {email}")
