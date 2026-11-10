import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request

from ..deploy import deploy_portfolio
from ..deps import current_user, get_db
from ..render import TEMPLATES, render_portfolio
from ..schemas import PortfolioData, PortfolioIn, PreviewIn

router = APIRouter(prefix="/api", tags=["portfolio"])


@router.get("/templates")
def list_templates():
    return TEMPLATES


@router.get("/portfolio")
def get_portfolio(user: sqlite3.Row = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    row = db.execute("SELECT * FROM portfolios WHERE user_id = ?", (user["id"],)).fetchone()
    if not row:
        return {"template": "minimal", "data": {}}
    return {"template": row["template"], "data": json.loads(row["data"])}


@router.put("/portfolio")
def save_portfolio(body: PortfolioIn, user: sqlite3.Row = Depends(current_user),
                   db: sqlite3.Connection = Depends(get_db)):
    render_portfolio(body.template, body.data)  # validates the template name too
    db.execute(
        "INSERT INTO portfolios (user_id, template, data, updated_at) VALUES (?, ?, ?, datetime('now')) "
        "ON CONFLICT(user_id) DO UPDATE SET template = excluded.template, data = excluded.data, "
        "updated_at = excluded.updated_at",
        (user["id"], body.template, body.data.cleaned().model_dump_json()),
    )
    db.commit()
    return {"saved": True}


@router.post("/preview")
def preview(body: PreviewIn, _user: sqlite3.Row = Depends(current_user)):
    return {"html": render_portfolio(body.template, body.data)}


# Sync `def` on purpose: boto3 is blocking, so FastAPI runs this in its threadpool
# instead of stalling the event loop.
@router.post("/publish")
def publish(request: Request, user: sqlite3.Row = Depends(current_user),
            db: sqlite3.Connection = Depends(get_db)):
    row = db.execute("SELECT * FROM portfolios WHERE user_id = ?", (user["id"],)).fetchone()
    if not row:
        raise HTTPException(400, "Save your portfolio before publishing")
    data = PortfolioData(**json.loads(row["data"]))
    return deploy_portfolio(db, request.app.state.storage, user, row["template"], data)


@router.get("/deployments")
def deployments(user: sqlite3.Row = Depends(current_user), db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute("SELECT * FROM deployments WHERE user_id = ? ORDER BY id DESC LIMIT 50", (user["id"],))
    return [dict(r) for r in rows]
