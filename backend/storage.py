"""Tiny SQLite project store for creator workflows."""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent / "data" / "projects.db"
DB.parent.mkdir(parents=True, exist_ok=True)

def connect():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE IF NOT EXISTS projects (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, payload TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)")
    db.commit()
    return db

def list_projects():
    with connect() as db:
        return [dict(r) | {"payload": json.loads(r["payload"])} for r in db.execute("SELECT * FROM projects ORDER BY updated_at DESC")]

def save_project(name: str, payload: dict, project_id: int | None = None):
    with connect() as db:
        if project_id:
            db.execute("UPDATE projects SET name=?, payload=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (name, json.dumps(payload), project_id))
            pid = project_id
        else:
            cur = db.execute("INSERT INTO projects(name,payload) VALUES(?,?)", (name, json.dumps(payload)))
            pid = cur.lastrowid
        db.commit()
        return pid

def delete_project(project_id: int):
    with connect() as db:
        db.execute("DELETE FROM projects WHERE id=?", (project_id,))
        db.commit()
