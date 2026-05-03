# Migrations

The blueprint currently uses `db.create_all()` in `init_floor_plan()` for development convenience. This creates tables on first run but is **NOT suitable for production**.

For production, use Flask-Migrate / Alembic.

## Setup (one-time)

```bash
pip install Flask-Migrate
```

In your SAIL app factory:

```python
from flask_migrate import Migrate
from app.floor_plan import floor_plan_bp, init_floor_plan, db

app.register_blueprint(floor_plan_bp, url_prefix="/floor-plan")
init_floor_plan(app, existing_db=db)

migrate = Migrate(app, db)
```

Then:

```bash
flask db init                                      # one-time
flask db migrate -m "Add floor_plan_pins table"
flask db upgrade
```

## Disabling auto-create

Once migrations are in place, remove the auto-create block in `app/floor_plan/db.py`:

```python
# Remove these lines:
with app.app_context():
    db.create_all()
```

Or guard it with a config flag:

```python
if app.config.get("FLOOR_PLAN_AUTO_CREATE_TABLES", False):
    with app.app_context():
        db.create_all()
```

So dev defaults to true, production defaults to false.

## Schema changes

Whenever `models.py` changes:

```bash
flask db migrate -m "Brief description of change"
flask db upgrade
```

Review the generated migration script in `migrations/versions/` before running upgrade — Alembic's autogenerate isn't perfect.
