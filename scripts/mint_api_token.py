"""
Mint an API token for an employee. Prints the plaintext token ONCE —
only its sha256 hash is stored in api_tokens.token_hash.

Usage:
    python3 scripts/mint_api_token.py --name "ollama-agent" --email agent@sail.local
    python3 scripts/mint_api_token.py --name "claude-gpu" --email airandblueamt@gmail.com --scopes read

List existing tokens (names + last used):
    python3 scripts/mint_api_token.py --list

Revoke a token by id:
    python3 scripts/mint_api_token.py --revoke 3
"""
import argparse
import hashlib
import os
import secrets
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, os.pardir))
sys.path.insert(0, ROOT)

from database import get_db


def _hash(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode('utf-8')).hexdigest()


def _list_tokens():
    with get_db() as conn:
        rows = conn.execute(
            """SELECT t.id, t.name, t.scopes, t.created_at, t.last_used_at,
                      t.revoked_at, e.name AS employee_name, e.email
               FROM api_tokens t
               JOIN employees  e ON e.id = t.employee_id
               ORDER BY t.id"""
        ).fetchall()
    if not rows:
        print("(no tokens)")
        return
    for r in rows:
        state = 'REVOKED' if r['revoked_at'] else 'active'
        last = r['last_used_at'] or 'never'
        print(f"#{r['id']:<3} [{state:<7}] {r['name']:<24} "
              f"scopes={r['scopes']:<10} owner={r['employee_name']} ({r['email']}) "
              f"created={r['created_at']} last_used={last}")


def _revoke(token_id: int):
    with get_db() as conn:
        row = conn.execute("SELECT name, revoked_at FROM api_tokens WHERE id = ?",
                           (token_id,)).fetchone()
        if not row:
            print(f"No token with id {token_id}.")
            return
        if row['revoked_at']:
            print(f"Token #{token_id} ({row['name']}) was already revoked at {row['revoked_at']}.")
            return
        conn.execute("UPDATE api_tokens SET revoked_at = datetime('now') WHERE id = ?",
                     (token_id,))
        print(f"Revoked token #{token_id} ({row['name']}).")


def _mint(name: str, email: str, scopes: str):
    with get_db() as conn:
        emp = conn.execute(
            "SELECT id, name, role FROM employees WHERE LOWER(email) = LOWER(?) AND is_active = 1",
            (email,)
        ).fetchone()
        if not emp:
            print(f"No active employee with email {email}.")
            sys.exit(1)

        plaintext = 'sail_' + secrets.token_hex(32)   # 64 hex chars after prefix
        th = _hash(plaintext)

        conn.execute(
            """INSERT INTO api_tokens (name, token_hash, employee_id, scopes)
               VALUES (?, ?, ?, ?)""",
            (name, th, emp['id'], scopes)
        )
        token_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    print("─" * 72)
    print(f"Token minted (#{token_id}) for {emp['name']} <{email}>, scopes={scopes}")
    print()
    print(f"  {plaintext}")
    print()
    print("Store it now — it is NOT recoverable. Only its sha256 hash is in the DB.")
    print()
    print("Usage from the agent:")
    print(f"  curl -H 'Authorization: Bearer {plaintext}' http://<sail-host>:5555/api/v1/health")
    print("─" * 72)


def main():
    ap = argparse.ArgumentParser(description='Mint / list / revoke SAIL API tokens.')
    ap.add_argument('--list', action='store_true', help='list existing tokens')
    ap.add_argument('--revoke', type=int, metavar='ID', help='revoke token by id')
    ap.add_argument('--name', help='human label for the token, e.g. "ollama-agent"')
    ap.add_argument('--email', help='owner employee email (must already exist and be active)')
    ap.add_argument('--scopes', default='read', help='comma-separated, default: read')
    args = ap.parse_args()

    if args.list:
        _list_tokens(); return
    if args.revoke is not None:
        _revoke(args.revoke); return
    if not args.name or not args.email:
        ap.error('--name and --email are required to mint a token')
    _mint(args.name, args.email, args.scopes)


if __name__ == '__main__':
    main()
