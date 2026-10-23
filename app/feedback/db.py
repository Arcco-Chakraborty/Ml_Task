"""SQLite storage for feedback, the suggestions board and known issues.

The suggestions and issues tables are seeded from data/*.json the first time
the database is created. `flask --app run reset-db` wipes and re-seeds.
"""
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import click
from flask import current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    text           TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    label          TEXT,               -- query | suggestion | bug | junk | NULL (pipeline unavailable)
    label_source   TEXT,               -- model | admin
    confidence     REAL,               -- probability of the chosen label (from predict_proba)
    probabilities  TEXT,               -- JSON {label: probability} for every label (from predict_proba)
    match_kind     TEXT,               -- suggestion | issue
    match_id       TEXT,
    created_new    INTEGER NOT NULL DEFAULT 0,  -- 1 if this message created a new suggestion
    reply          TEXT NOT NULL,
    pipeline_error TEXT
);
CREATE TABLE IF NOT EXISTS suggestions (
    id         TEXT PRIMARY KEY,
    text       TEXT NOT NULL,
    count      INTEGER NOT NULL DEFAULT 1,
    source     TEXT NOT NULL,          -- seed | user
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS issues (
    id         TEXT PRIMARY KEY,
    title      TEXT NOT NULL,
    status     TEXT NOT NULL,          -- open | fixed
    fixed_in   TEXT,
    component  TEXT,
    source     TEXT NOT NULL,          -- seed | admin
    created_at TEXT NOT NULL
);
"""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(reset=False):
    db = get_db()
    if reset:
        db.executescript("DROP TABLE IF EXISTS feedback; DROP TABLE IF EXISTS suggestions; DROP TABLE IF EXISTS issues;")
    db.executescript(SCHEMA)
    # databases created before a column existed get it added
    columns = {r["name"] for r in db.execute("PRAGMA table_info(feedback)")}
    if "probabilities" not in columns:
        db.execute("ALTER TABLE feedback ADD COLUMN probabilities TEXT")
    data_dir = Path(current_app.config["DATA_DIR"])
    if db.execute("SELECT COUNT(*) FROM suggestions").fetchone()[0] == 0:
        for s in json.loads((data_dir / "suggestions.json").read_text(encoding="utf-8")):
            db.execute("INSERT INTO suggestions VALUES (?, ?, ?, 'seed', ?)", (s["id"], s["text"], s["count"], now()))
    if db.execute("SELECT COUNT(*) FROM issues").fetchone()[0] == 0:
        for i in json.loads((data_dir / "known_issues.json").read_text(encoding="utf-8")):
            db.execute("INSERT INTO issues VALUES (?, ?, ?, ?, ?, 'seed', ?)",
                       (i["id"], i["title"], i["status"], i.get("fixed_in"), i.get("component"), now()))
    db.commit()


def next_id(table, prefix):
    ids = [r[0] for r in get_db().execute(f"SELECT id FROM {table}")]
    nums = [int(m.group(1)) for i in ids if (m := re.fullmatch(prefix + r"(\d+)", i))]
    return f"{prefix}{(max(nums) + 1 if nums else 1):02d}"


def list_suggestions():
    rows = get_db().execute("SELECT id, text, count FROM suggestions ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def list_issues():
    rows = get_db().execute("SELECT id, title, status, fixed_in, component FROM issues ORDER BY id").fetchall()
    return [dict(r) for r in rows]


@click.command("reset-db")
def reset_db_command():
    """Delete all feedback and re-seed suggestions / known issues from data/."""
    init_db(reset=True)
    click.echo("database reset and re-seeded")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(reset_db_command)
    with app.app_context():
        init_db()
