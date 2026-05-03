# Deploying SAIL

The live demo runs the **`pre-demo-review`** branch. Master is older / stable.
Pushes intended for the demo go to `pre-demo-review`.

GitHub: https://github.com/airandblueamt-Claude/sail-project

## Push from your dev machine

```bash
git checkout pre-demo-review
git merge --no-ff <feature-branch>
git push origin pre-demo-review
```

## Pull + deploy on the server

```bash
cd <sail-project>
git checkout pre-demo-review
git pull origin pre-demo-review

# 1. Pick up new tables added in schema.sql.
#    CREATE TABLE IF NOT EXISTS — idempotent, never drops data.
python3 -c "import sqlite3; conn = sqlite3.connect('sail.db'); conn.executescript(open('schema.sql').read()); conn.commit(); conn.close()"

# 2. Apply additive ALTER TABLE migrations. Idempotent.
python3 migrate_db.py

# 3. Only if requirements.txt changed.
pip install -r requirements.txt

# 4. Restart — pick the one that matches your setup
sudo systemctl restart sail        # systemd
sudo supervisorctl restart sail    # supervisor
docker compose up -d --build       # docker (entrypoint.sh runs steps 1+2 automatically)
fly deploy                         # fly.io
```

If `SAIL_DB_PATH` points the DB elsewhere (e.g. `/data/sail.db` in Docker), step 1's
inline script picks it up automatically because both go through `config.DB_PATH`.

## Both DB scripts are additive

`schema.sql` uses `CREATE TABLE IF NOT EXISTS` and `migrate_db.py` only adds new
columns when missing. **Neither drops or deletes data.** Safe to re-run on every
deploy. Existing tickets, employees, assets, audit_log are preserved.

`instance/floor_plan.db` (the SQLAlchemy DB used by the floor-plan blueprint) is
auto-created on first request and seeded with the four bookable rooms
(Workshop 1/2/3, Theater). Never tracked in git — survives across restarts in
its own file.

## Verify after deploy

Visit each of these and confirm 200:

- `/inventory/assets` — asset list loads
- `/inventory/asset/<id>` — asset detail (uses the new `model_number` column)
- `/floor-plan/` — schematic with red outlines on the four bookable rooms
- `/floor-plan/calendar` — weekly grid loads
- `/floor-plan/bookings` — bookings page (admin sees all, employee sees own)
- `/tickets/` — booking tickets are filtered out, only real tickets show

## Rollback

```bash
git log --oneline -10        # find the previous tip
git checkout <previous SHA>
# restart the app
```

The DB stays forward-compatible — older code reads new columns/tables fine.
You can roll back the code without rolling back the DB. **Do not** run
newer code against an older DB without re-running the two migration steps.

## When something 500s after a deploy

Most likely cause: schema.sql / migrate_db.py weren't run. The symptom is
`sqlite3.OperationalError: no such column ...` or `no such table ...` in the
log. Re-run steps 1 and 2, restart.
