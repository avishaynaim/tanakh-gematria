from __future__ import annotations
from os import environ


from pathlib import Path
from typing import List, Optional, Literal

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .search import search
from .gematria import gematria
from .bootstrap_db import ensure_db


from contextlib import asynccontextmanager
from fastapi import FastAPI
from .bootstrap_db import ensure_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # runs on startup
    ensure_db()
    yield
    # runs on shutdown (nothing needed)

app = FastAPI(lifespan=lifespan)

class HitOut(BaseModel):
    kind: str
    ref: str
    n: Optional[int] = None
    text: str
    clean_text: str
    gematria: int
    match_text: Optional[str] = None
    match_range: Optional[str] = None

_UI_PATH = Path(__file__).with_name("ui.html")

# asdffds
@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse(_UI_PATH.read_text(encoding="utf-8"))

@app.get("/gematria")
def api_gematria(
    text: str = Query(..., min_length=1, description="טקסט בעברית לחישוב גימטריה"),
):
    return {"text": text, "gematria": gematria(text)}

@app.get("/search", response_model=List[HitOut])
def api_search(
    value: Optional[int] = Query(None, ge=0, description="מספר גימטריה לחיפוש"),
    text: Optional[str] = Query(None, description="טקסט בעברית: יחושב גימטריה ואז יחפש"),
    kind: Optional[Literal["verse","word","gram"]] = None,
    n: Optional[int] = Query(None, ge=1, le=10),
    # ברירת מחדל: להחזיר הכול (ללא LIMIT). אפשר להעביר limit=50 וכו'
    limit: Optional[int] = Query(None, ge=1, le=200000),
    offset: int = Query(0, ge=0),
    db = environ.get("DB_PATH", "tanakh.sqlite")

    # db = os.environ.get("DB_PATH", "tanakh.sqlite")
    # db: str = Query("tanakh.sqlite"),
):
    if value is None:
        if not text:
            raise HTTPException(status_code=400, detail="נא לספק value או text")
        value = gematria(text)

    hits = search(db_path=db, value=value, kind=kind, n=n, limit=limit, offset=offset)
    return [HitOut(**h.__dict__) for h in hits]
