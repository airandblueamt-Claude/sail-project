"""Pytest fixtures for the floor_plan booking tests.

Spins up a Flask app with a temporary floor_plan.db (SQLAlchemy) and a
temporary sail.db (raw sqlite3, schema applied from schema.sql).
"""
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest
from flask import Flask
from werkzeug.security import generate_password_hash

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def temp_sail_db(monkeypatch):
    """A temp sail.db with schema applied + a couple of seed rows."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    schema = (PROJECT_ROOT / "schema.sql").read_text()
    conn = sqlite3.connect(path)
    conn.executescript(schema)
    conn.executescript(
        """
        INSERT INTO categories (name) VALUES ('Furniture');
        INSERT INTO locations (id, code, label) VALUES
          (11, 'DIGITAL-THEATER', 'Digital Theater'),
          (38, 'WORKSHOP-1', 'Workshop -1'),
          (39, 'WORKSHOP-2', 'Workshop -2'),
          (40, 'WORKSHOP-3', 'Workshop -3');
        INSERT INTO equipment_models (id, category_id, name) VALUES (1, 1, 'Display');
        INSERT INTO assets (id, asset_tag, equipment_model_id, location_id, status, condition)
          VALUES (1, 'SAIL-0001', 1, 38, 'available', 'good'),
                 (2, 'SAIL-0002', 1, 38, 'available', 'good'),
                 (3, 'SAIL-0003', 1, 11, 'available', 'good');
        """
    )
    conn.execute(
        "INSERT INTO employees (id, name, email, password_hash, role, is_active) "
        "VALUES (1, 'Test User', 'test@example.com', ?, 'admin', 1)",
        (generate_password_hash("Password1!"),),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr("config.DB_PATH", path)
    monkeypatch.setattr("database.DB_PATH", path)
    yield path
    os.unlink(path)


@pytest.fixture
def app(temp_sail_db, tmp_path):
    """Flask app with floor_plan registered and a temp floor_plan.db."""
    from app.floor_plan import floor_plan_bp, init_floor_plan
    from app.floor_plan.db import db as fp_db

    fp_path = tmp_path / "floor_plan.db"

    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test"
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{fp_path}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    app.register_blueprint(floor_plan_bp, url_prefix="/floor-plan")
    init_floor_plan(app)

    yield app

    with app.app_context():
        fp_db.session.remove()
        fp_db.engine.dispose()


@pytest.fixture
def client(app):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["user_id"] = 1
    return c
