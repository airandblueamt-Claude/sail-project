"""SQLAlchemy setup for the floor plan blueprint.

Designed to be flexible — works whether your SAIL app already uses Flask-SQLAlchemy
or not. The init_floor_plan() helper figures it out.
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Module-level db instance. Reused if the host app already has one bound.
db = SQLAlchemy()


def init_floor_plan(app: Flask, *, existing_db: SQLAlchemy | None = None):
    """Wire the floor plan blueprint into a Flask app.

    Args:
        app: your Flask application
        existing_db: if your app already has a Flask-SQLAlchemy db instance,
                     pass it here so the floor plan tables join your schema.
                     If None, this module will initialize its own.

    The blueprint itself must already be registered before calling this:

        from app.floor_plan import floor_plan_bp, init_floor_plan
        app.register_blueprint(floor_plan_bp, url_prefix="/floor-plan")
        init_floor_plan(app)               # standalone db
        # or
        init_floor_plan(app, existing_db=db)  # join your app's db
    """
    global db

    if existing_db is not None:
        # Reuse the host app's db. Models import from .db, so swap the binding.
        db = existing_db
        # Re-register models against the host db
        from . import models  # noqa: F401 — triggers model registration
    else:
        # Standalone init. Configure a default sqlite file if app didn't already.
        if "SQLALCHEMY_DATABASE_URI" not in app.config:
            app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///floor_plan.db"
        app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
        db.init_app(app)
        from . import models  # noqa: F401

    # Auto-create tables on first run. For production with migrations, remove this
    # and use Flask-Migrate / Alembic instead — see migrations/README.md.
    with app.app_context():
        db.create_all()
