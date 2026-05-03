"""Shared pytest fixtures."""

import pytest
from flask import Flask

from app.floor_plan import floor_plan_bp, init_floor_plan


@pytest.fixture
def app():
    """A fresh Flask app with the blueprint mounted, in-memory SQLite."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.register_blueprint(floor_plan_bp, url_prefix="/floor-plan")
    init_floor_plan(app)
    yield app


@pytest.fixture
def client(app):
    return app.test_client()
