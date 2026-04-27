"""WSGI entrypoint for production servers (gunicorn, etc.).

`python app.py` is fine for local dev. In production, point gunicorn at
`wsgi:app` so it can manage workers and lifecycle properly.
"""
from app import create_app

app = create_app()
