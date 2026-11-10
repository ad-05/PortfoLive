import sqlite3

from fastapi import APIRouter, Depends

from ..deps import admin_user, get_db

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats")
def stats(_admin: sqlite3.Row = Depends(admin_user), db: sqlite3.Connection = Depends(get_db)):
    totals = dict(db.execute(
        "SELECT COUNT(*) AS total, COALESCE(SUM(status='success'),0) AS success, "
        "COALESCE(SUM(status='failed'),0) AS failed, COALESCE(ROUND(AVG(duration_ms)),0) AS avg_duration_ms "
        "FROM deployments"
    ).fetchone())
    return {
        "users": db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        **totals,
        "recent": [dict(r) for r in db.execute("SELECT * FROM deployments ORDER BY id DESC LIMIT 25")],
    }
