"""SQLite scan history (Blueprint section 6 tables, simplified for MVP)."""
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

def _default_db_path() -> str:
    if os.environ.get("SITESH_DB"):
        return os.environ["SITESH_DB"]
    # Serverless filesystems (Vercel sets VERCEL=1) are read-only except /tmp.
    if os.environ.get("VERCEL"):
        return "/tmp/sitesherlock.db"
    return os.path.join(os.path.dirname(__file__), "..", "..", "data", "sitesherlock.db")


DB_PATH = _default_db_path()
_LOCK = threading.Lock()


def _conn():
    try:
        os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
    except (OSError, sqlite3.Error):
        conn = sqlite3.connect("/tmp/sitesherlock.db")  # last-resort writable path
    conn.execute("""CREATE TABLE IF NOT EXISTS scans(
        id TEXT PRIMARY KEY, root_url TEXT, created_at TEXT, pages_checked INTEGER,
        score INTEGER, findings_count INTEGER, result_json TEXT)""")
    return conn


def save_scan(result: dict) -> str:
    scan_id = uuid.uuid4().hex[:12]
    result["scan_id"] = scan_id
    result["created_at"] = datetime.now(timezone.utc).isoformat()
    with _LOCK, _conn() as conn:
        conn.execute("INSERT INTO scans VALUES (?,?,?,?,?,?,?)",
                     (scan_id, result["root_url"], result["created_at"], result["pages_checked"],
                      result["score"]["overall"], len(result["findings"]), json.dumps(result)))
    return scan_id


def list_scans(limit: int = 20) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute("SELECT id, root_url, created_at, pages_checked, score, findings_count "
                            "FROM scans ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [{"scan_id": r[0], "root_url": r[1], "created_at": r[2], "pages_checked": r[3],
             "score": r[4], "findings_count": r[5]} for r in rows]


def get_scan(scan_id: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute("SELECT result_json FROM scans WHERE id=?", (scan_id,)).fetchone()
    return json.loads(row[0]) if row else None


def delete_scan(scan_id: str) -> bool:
    with _LOCK, _conn() as conn:
        cur = conn.execute("DELETE FROM scans WHERE id=?", (scan_id,))
        return cur.rowcount > 0
