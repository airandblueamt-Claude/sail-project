"""SAIL Incubation Floor Plan — Flask blueprint.

Drop this package into your existing SAIL Flask project and register it:

    from app.floor_plan import floor_plan_bp, init_floor_plan
    app.register_blueprint(floor_plan_bp, url_prefix="/floor-plan")
    init_floor_plan(app)

The blueprint provides:
    GET  /floor-plan/             -> the interactive floor plan page
    GET  /floor-plan/api/pins     -> list all pins
    PUT  /floor-plan/api/pins     -> replace all pins (bulk save)
    POST /floor-plan/api/pins     -> create one pin
    PATCH /floor-plan/api/pins/<id> -> update one pin
    DELETE /floor-plan/api/pins/<id> -> delete one pin

Database: works with whatever SQLAlchemy URL you pass to init_floor_plan.
By default, uses the existing app.db if configured, otherwise creates floor_plan.db.

See docs/INTEGRATION.md for full integration recipes.
"""

from .blueprint import floor_plan_bp
from .db import init_floor_plan, db

__all__ = ["floor_plan_bp", "init_floor_plan", "db"]
