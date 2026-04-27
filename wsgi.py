"""WSGI entrypoint for production servers (gunicorn, uWSGI, etc.).

`python app.py` is fine for local dev. In production:
- gunicorn / Fly.io: `gunicorn wsgi:app`
- PythonAnywhere / uWSGI: looks for `application` by convention — aliased below.
"""
from app import create_app

app = create_app()
application = app  # PythonAnywhere / uWSGI convention
