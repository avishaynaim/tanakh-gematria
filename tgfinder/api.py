from __future__ import annotations
import re
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
_histogram_words_cache: Optional[List[Dict[str, Any]]] = None

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


class WordInfo(BaseModel):
    ref: str
    word: str
    verse_text: str
    word_index: int

class WordHistogramBucket(BaseModel):
    gematria: int
    count: int
    words: List[WordInfo]

class WordLocation(BaseModel):
    ref: str
    book: str
    chapter: int
    verse: int
    word_index: int
    verse_text: str

class WordSearchResult(BaseModel):
    word: str
    count: int
    locations: List[WordLocation]

@app.get("/histogram/words", response_model=List[WordHistogramBucket])
def api_histogram_words(
    db: str = Query(default=None),
):
    """
    Returns histogram data: words (n=1 grams) grouped by gematria value.
    Sorted by gematria ascending. Cached in memory for performance.
    """
    global _histogram_words_cache

    db_path = db or environ.get("DB_PATH", "tanakh.sqlite")

    # Return cached data if available
    if _histogram_words_cache is not None:
        return _histogram_words_cache

    conn = connect(db_path)

    # Query words (n=1) with their verse text
    sql = """
        SELECT g.gematria, g.text as word, g.book, g.chapter, g.verse,
               g.start_word, v.text as verse_text
        FROM grams g
        JOIN verses v ON v.book=g.book AND v.chapter=g.chapter AND v.verse=g.verse
        WHERE g.n = 1
        ORDER BY g.gematria ASC,
            CASE
                WHEN g.book='Genesis' THEN 1 WHEN g.book='Exodus' THEN 2
                WHEN g.book='Leviticus' THEN 3 WHEN g.book='Numbers' THEN 4
                WHEN g.book='Deuteronomy' THEN 5 WHEN g.book='Joshua' THEN 6
                WHEN g.book='Judges' THEN 7 WHEN g.book='1 Samuel' THEN 8
                WHEN g.book='2 Samuel' THEN 9 WHEN g.book='1 Kings' THEN 10
                WHEN g.book='2 Kings' THEN 11 WHEN g.book='Isaiah' THEN 12
                WHEN g.book='Jeremiah' THEN 13 WHEN g.book='Ezekiel' THEN 14
                WHEN g.book='Hosea' THEN 15 WHEN g.book='Joel' THEN 16
                WHEN g.book='Amos' THEN 17 WHEN g.book='Obadiah' THEN 18
                WHEN g.book='Jonah' THEN 19 WHEN g.book='Micah' THEN 20
                WHEN g.book='Nahum' THEN 21 WHEN g.book='Habakkuk' THEN 22
                WHEN g.book='Zephaniah' THEN 23 WHEN g.book='Haggai' THEN 24
                WHEN g.book='Zechariah' THEN 25 WHEN g.book='Malachi' THEN 26
                WHEN g.book='Psalms' THEN 27 WHEN g.book='Proverbs' THEN 28
                WHEN g.book='Job' THEN 29 WHEN g.book='Song of Songs' THEN 30
                WHEN g.book='Ruth' THEN 31 WHEN g.book='Lamentations' THEN 32
                WHEN g.book='Ecclesiastes' THEN 33 WHEN g.book='Esther' THEN 34
                WHEN g.book='Daniel' THEN 35 WHEN g.book='Ezra' THEN 36
                WHEN g.book='Nehemiah' THEN 37 WHEN g.book='1 Chronicles' THEN 38
                WHEN g.book='2 Chronicles' THEN 39
                ELSE 999
            END,
            g.chapter, g.verse, g.start_word
    """

    cur = conn.execute(sql)
    rows = cur.fetchall()
    conn.close()

    # Group by gematria value
    buckets: Dict[int, List[WordInfo]] = {}
    for r in rows:
        gem = r["gematria"]
        hebrew_book = book_to_hebrew(r["book"])
        ref = f"{hebrew_book} {r['chapter']}:{r['verse']}"
        word_info = WordInfo(
            ref=ref,
            word=r["word"],
            verse_text=r["verse_text"],
            word_index=r["start_word"]
        )
        if gem not in buckets:
            buckets[gem] = []
        buckets[gem].append(word_info)

    # Build sorted result
    result = [
        WordHistogramBucket(gematria=gem, count=len(words), words=words)
        for gem, words in sorted(buckets.items())
    ]

    # Cache the result
    _histogram_words_cache = result

    return result


@app.get("/word-search", response_model=WordSearchResult)
def api_word_search(
    word: str = Query(..., min_length=1, description="מילה לחיפוש"),
    limit: int = Query(500, ge=1, le=10000, description="מספר תוצאות מקסימלי"),
    db: str = Query(default=None),
):
    """
    Search for a word in the Tanakh and return count + locations.
    Searches in clean_text (without nikud/teamim) for better matching.
    """
    db_path = db or environ.get("DB_PATH", "tanakh.sqlite")
    conn = connect(db_path)

    # Clean the search word (remove non-Hebrew chars for matching)
    clean_word = re.sub(r'[^\u05d0-\u05ea]', '', word)

    if not clean_word:
        raise HTTPException(status_code=400, detail="נא להזין מילה בעברית")

    # Search in grams where n=1 (single words)
    sql = f"""
        SELECT g.text, g.clean_text, g.book, g.chapter, g.verse, g.start_word, v.text as verse_text
        FROM grams g
        JOIN verses v ON v.book=g.book AND v.chapter=g.chapter AND v.verse=g.verse
        WHERE g.n = 1 AND g.clean_text = ?
        ORDER BY {_BOOK_ORDER_CASE.replace('book', 'g.book')}, g.chapter, g.verse, g.start_word
        LIMIT ?
    """

    # Need the book order case for grams table
    _GBOOK_ORDER = """CASE WHEN g.book='Genesis' THEN 1 WHEN g.book='Exodus' THEN 2 WHEN g.book='Leviticus' THEN 3 WHEN g.book='Numbers' THEN 4 WHEN g.book='Deuteronomy' THEN 5 WHEN g.book='Joshua' THEN 6 WHEN g.book='Judges' THEN 7 WHEN g.book='1 Samuel' THEN 8 WHEN g.book='2 Samuel' THEN 9 WHEN g.book='1 Kings' THEN 10 WHEN g.book='2 Kings' THEN 11 WHEN g.book='Isaiah' THEN 12 WHEN g.book='Jeremiah' THEN 13 WHEN g.book='Ezekiel' THEN 14 WHEN g.book='Hosea' THEN 15 WHEN g.book='Joel' THEN 16 WHEN g.book='Amos' THEN 17 WHEN g.book='Obadiah' THEN 18 WHEN g.book='Jonah' THEN 19 WHEN g.book='Micah' THEN 20 WHEN g.book='Nahum' THEN 21 WHEN g.book='Habakkuk' THEN 22 WHEN g.book='Zephaniah' THEN 23 WHEN g.book='Haggai' THEN 24 WHEN g.book='Zechariah' THEN 25 WHEN g.book='Malachi' THEN 26 WHEN g.book='Psalms' THEN 27 WHEN g.book='Proverbs' THEN 28 WHEN g.book='Job' THEN 29 WHEN g.book='Song of Songs' THEN 30 WHEN g.book='Ruth' THEN 31 WHEN g.book='Lamentations' THEN 32 WHEN g.book='Ecclesiastes' THEN 33 WHEN g.book='Esther' THEN 34 WHEN g.book='Daniel' THEN 35 WHEN g.book='Ezra' THEN 36 WHEN g.book='Nehemiah' THEN 37 WHEN g.book='1 Chronicles' THEN 38 WHEN g.book='2 Chronicles' THEN 39 ELSE 999 END"""

    sql = f"""
        SELECT g.text, g.clean_text, g.book, g.chapter, g.verse, g.start_word, v.text as verse_text
        FROM grams g
        JOIN verses v ON v.book=g.book AND v.chapter=g.chapter AND v.verse=g.verse
        WHERE g.n = 1 AND g.clean_text = ?
        ORDER BY {_GBOOK_ORDER}, g.chapter, g.verse, g.start_word
        LIMIT ?
    """

    cur = conn.execute(sql, (clean_word, limit))
    rows = cur.fetchall()

    # Get total count (without limit)
    count_sql = "SELECT COUNT(*) as cnt FROM grams WHERE n = 1 AND clean_text = ?"
    total = conn.execute(count_sql, (clean_word,)).fetchone()["cnt"]

    conn.close()

    locations = []
    for r in rows:
        hebrew_book = book_to_hebrew(r["book"])
        ref = f"{hebrew_book} {r['chapter']}:{r['verse']}"
        locations.append(WordLocation(
            ref=ref,
            book=r["book"],
            chapter=r["chapter"],
            verse=r["verse"],
            word_index=r["start_word"],
            verse_text=r["verse_text"]
        ))

    return WordSearchResult(word=clean_word, count=total, locations=locations)
