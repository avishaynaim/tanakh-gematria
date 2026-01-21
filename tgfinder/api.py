from __future__ import annotations
from os import environ


from pathlib import Path
from typing import List, Optional, Literal, Dict, Any

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .search import search, book_to_hebrew
from .gematria import gematria
from .bootstrap_db import ensure_db
from .db import connect


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


# Cache for histogram data (computed once, reused)
_histogram_cache: Optional[List[Dict[str, Any]]] = None

class VerseInfo(BaseModel):
    ref: str
    text: str
    book: str
    chapter: int
    verse: int

class HistogramBucket(BaseModel):
    gematria: int
    count: int
    verses: List[VerseInfo]

@app.get("/histogram", response_model=List[HistogramBucket])
def api_histogram(
    db: str = Query(default=None),
):
    """
    Returns histogram data: verses grouped by gematria value.
    Sorted by gematria ascending. Cached in memory for performance.
    """
    global _histogram_cache

    db_path = db or environ.get("DB_PATH", "tanakh.sqlite")

    # Return cached data if available
    if _histogram_cache is not None:
        return _histogram_cache

    conn = connect(db_path)

    # Single query to get all verses, ordered by gematria then by canonical order
    sql = """
        SELECT gematria, book, chapter, verse, text
        FROM verses
        ORDER BY gematria ASC,
            CASE
                WHEN book='Genesis' THEN 1 WHEN book='Exodus' THEN 2
                WHEN book='Leviticus' THEN 3 WHEN book='Numbers' THEN 4
                WHEN book='Deuteronomy' THEN 5 WHEN book='Joshua' THEN 6
                WHEN book='Judges' THEN 7 WHEN book='1 Samuel' THEN 8
                WHEN book='2 Samuel' THEN 9 WHEN book='1 Kings' THEN 10
                WHEN book='2 Kings' THEN 11 WHEN book='Isaiah' THEN 12
                WHEN book='Jeremiah' THEN 13 WHEN book='Ezekiel' THEN 14
                WHEN book='Hosea' THEN 15 WHEN book='Joel' THEN 16
                WHEN book='Amos' THEN 17 WHEN book='Obadiah' THEN 18
                WHEN book='Jonah' THEN 19 WHEN book='Micah' THEN 20
                WHEN book='Nahum' THEN 21 WHEN book='Habakkuk' THEN 22
                WHEN book='Zephaniah' THEN 23 WHEN book='Haggai' THEN 24
                WHEN book='Zechariah' THEN 25 WHEN book='Malachi' THEN 26
                WHEN book='Psalms' THEN 27 WHEN book='Proverbs' THEN 28
                WHEN book='Job' THEN 29 WHEN book='Song of Songs' THEN 30
                WHEN book='Ruth' THEN 31 WHEN book='Lamentations' THEN 32
                WHEN book='Ecclesiastes' THEN 33 WHEN book='Esther' THEN 34
                WHEN book='Daniel' THEN 35 WHEN book='Ezra' THEN 36
                WHEN book='Nehemiah' THEN 37 WHEN book='1 Chronicles' THEN 38
                WHEN book='2 Chronicles' THEN 39
                ELSE 999
            END,
            chapter, verse
    """

    cur = conn.execute(sql)
    rows = cur.fetchall()
    conn.close()

    # Group by gematria value
    buckets: Dict[int, List[VerseInfo]] = {}
    for r in rows:
        gem = r["gematria"]
        hebrew_book = book_to_hebrew(r["book"])
        ref = f"{hebrew_book} {r['chapter']}:{r['verse']}"
        verse_info = VerseInfo(
            ref=ref,
            text=r["text"],
            book=r["book"],
            chapter=r["chapter"],
            verse=r["verse"]
        )
        if gem not in buckets:
            buckets[gem] = []
        buckets[gem].append(verse_info)

    # Build sorted result
    result = [
        HistogramBucket(gematria=gem, count=len(verses), verses=verses)
        for gem, verses in sorted(buckets.items())
    ]

    # Cache the result
    _histogram_cache = result

    return result
