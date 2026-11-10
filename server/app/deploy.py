"""Deployment orchestrator: render -> upload -> invalidate cache -> record the event."""
import sqlite3
import time

from .metrics import DEPLOY_SECONDS, DEPLOYS
from .render import render_portfolio
from .schemas import PortfolioData
from .storage import SiteStorage


def deploy_portfolio(db: sqlite3.Connection, storage: SiteStorage, user: sqlite3.Row,
                     template: str, data: PortfolioData) -> dict:
    started = time.perf_counter()
    prior = db.execute(
        "SELECT 1 FROM deployments WHERE user_id = ? AND status = 'success' LIMIT 1", (user["id"],)
    ).fetchone()
    action = "update" if prior else "publish"

    def record(status: str, url: str | None, error: str | None) -> int:
        ms = round((time.perf_counter() - started) * 1000)
        db.execute(
            "INSERT INTO deployments (user_id, username, status, action, duration_ms, url, error) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user["id"], user["username"], status, action, ms, url, error),
        )
        db.commit()
        DEPLOYS.labels(status).inc()
        DEPLOY_SECONDS.observe(ms / 1000)
        return ms

    try:
        html = render_portfolio(template, data)
        url = storage.publish(user["username"], html)
        if action == "update":
            storage.invalidate(user["username"])
    except Exception as exc:
        record("failed", None, getattr(exc, "detail", None) or str(exc))
        raise
    ms = record("success", url, None)
    return {"status": "success", "action": action, "url": url, "duration_ms": ms}
