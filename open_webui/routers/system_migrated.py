import time
from fastapi import APIRouter, Depends
from open_webui.utils.auth import get_verified_user
from open_webui.internal.db import get_db
from open_webui.models.cases import Case, CaseNode, CaseEdge
from open_webui.models.files import File
from open_webui.models.knowledge import Knowledge
from open_webui.env import VERSION


router = APIRouter()


@router.get("/health")
async def health(user=Depends(get_verified_user)):
    return {"status": "ok", "version": VERSION, "time": int(time.time())}


@router.get("/statistics")
async def statistics(user=Depends(get_verified_user)):
    with get_db() as db:
        cases = db.query(Case).count()
        nodes = db.query(CaseNode).count()
        edges = db.query(CaseEdge).count()
        files = db.query(File).count()
        knowledge = db.query(Knowledge).count()
    return {
        "cases": {"total": cases},
        "nodes": {"total": nodes},
        "edges": {"total": edges},
        "files": {"total": files},
        "knowledge": {"total": knowledge},
    }
