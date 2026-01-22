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
    word_text: str  # The actual word from the text

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


def normalize_sofit(text: str) -> str:
    """Normalize final letters (sofit) to regular letters for matching."""
    return text.translate(str.maketrans('ךםןףץ', 'כמנפצ'))

@app.get("/word-search", response_model=WordSearchResult)
def api_word_search(
    word: str = Query(..., min_length=1, description="מילה לחיפוש"),
    db: str = Query(default=None),
):
    """
    Search for a word in the Tanakh and return count + locations.
    Searches in clean_text (without nikud/teamim) for better matching.
    Also normalizes final letters (sofit) for matching.
    """
    db_path = db or environ.get("DB_PATH", "tanakh.sqlite")
    conn = connect(db_path)

    # Clean the search word (remove non-Hebrew chars for matching)
    clean_word = re.sub(r'[^\u05d0-\u05ea]', '', word)

    if not clean_word:
        raise HTTPException(status_code=400, detail="נא להזין מילה בעברית")

    # Normalize final letters (sofit) to regular letters
    normalized_word = normalize_sofit(clean_word)

    # Book order case for grams table
    _GBOOK_ORDER = """CASE WHEN g.book='Genesis' THEN 1 WHEN g.book='Exodus' THEN 2 WHEN g.book='Leviticus' THEN 3 WHEN g.book='Numbers' THEN 4 WHEN g.book='Deuteronomy' THEN 5 WHEN g.book='Joshua' THEN 6 WHEN g.book='Judges' THEN 7 WHEN g.book='1 Samuel' THEN 8 WHEN g.book='2 Samuel' THEN 9 WHEN g.book='1 Kings' THEN 10 WHEN g.book='2 Kings' THEN 11 WHEN g.book='Isaiah' THEN 12 WHEN g.book='Jeremiah' THEN 13 WHEN g.book='Ezekiel' THEN 14 WHEN g.book='Hosea' THEN 15 WHEN g.book='Joel' THEN 16 WHEN g.book='Amos' THEN 17 WHEN g.book='Obadiah' THEN 18 WHEN g.book='Jonah' THEN 19 WHEN g.book='Micah' THEN 20 WHEN g.book='Nahum' THEN 21 WHEN g.book='Habakkuk' THEN 22 WHEN g.book='Zephaniah' THEN 23 WHEN g.book='Haggai' THEN 24 WHEN g.book='Zechariah' THEN 25 WHEN g.book='Malachi' THEN 26 WHEN g.book='Psalms' THEN 27 WHEN g.book='Proverbs' THEN 28 WHEN g.book='Job' THEN 29 WHEN g.book='Song of Songs' THEN 30 WHEN g.book='Ruth' THEN 31 WHEN g.book='Lamentations' THEN 32 WHEN g.book='Ecclesiastes' THEN 33 WHEN g.book='Esther' THEN 34 WHEN g.book='Daniel' THEN 35 WHEN g.book='Ezra' THEN 36 WHEN g.book='Nehemiah' THEN 37 WHEN g.book='1 Chronicles' THEN 38 WHEN g.book='2 Chronicles' THEN 39 ELSE 999 END"""

    # Search using normalized comparison (handles sofit letters)
    # Use SQLite REPLACE to normalize sofit letters in the query
    sql = f"""
        SELECT g.text, g.clean_text, g.book, g.chapter, g.verse, g.start_word, v.text as verse_text
        FROM grams g
        JOIN verses v ON v.book=g.book AND v.chapter=g.chapter AND v.verse=g.verse
        WHERE g.n = 1 AND
            REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(g.clean_text, 'ך', 'כ'), 'ם', 'מ'), 'ן', 'נ'), 'ף', 'פ'), 'ץ', 'צ') = ?
        ORDER BY {_GBOOK_ORDER}, g.chapter, g.verse, g.start_word
    """

    cur = conn.execute(sql, (normalized_word,))
    rows = cur.fetchall()
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
            verse_text=r["verse_text"],
            word_text=r["text"]  # The actual word with nikud
        ))

    return WordSearchResult(word=clean_word, count=len(locations), locations=locations)


# ============ Roshei/Sofei Tevot ============

class RosheiTevotMatch(BaseModel):
    ref: str
    verse_text: str
    words: List[str]  # The words that form the match
    letters: str  # The letters extracted
    start_word_idx: int

class RosheiTevotResult(BaseModel):
    search_word: str
    mode: str  # 'first', 'last', or offset number
    count: int
    matches: List[RosheiTevotMatch]

@app.get("/roshei-tevot", response_model=RosheiTevotResult)
def api_roshei_tevot(
    word: str = Query(..., min_length=1, description="מילה לחיפוש"),
    mode: str = Query("first", description="first=ראשי תיבות, last=סופי תיבות, או מספר לאופסט"),
    db: str = Query(default=None),
):
    """
    Search for words formed by taking specific letters from consecutive words.
    mode: 'first' (first letter), 'last' (last letter), or a number for offset
    """
    db_path = db or environ.get("DB_PATH", "tanakh.sqlite")
    conn = connect(db_path)

    # Clean search word
    clean_word = re.sub(r'[^\u05d0-\u05ea]', '', word)
    if not clean_word:
        raise HTTPException(status_code=400, detail="נא להזין מילה בעברית")

    normalized_search = normalize_sofit(clean_word)
    word_len = len(normalized_search)

    # Parse mode
    if mode == 'first':
        offset = 0
    elif mode == 'last':
        offset = -1
    else:
        try:
            offset = int(mode)
        except ValueError:
            offset = 0

    # Get all verses ordered by book
    sql = """
        SELECT book, chapter, verse, text, clean_text
        FROM verses
        ORDER BY
            CASE WHEN book='Genesis' THEN 1 WHEN book='Exodus' THEN 2 WHEN book='Leviticus' THEN 3
            WHEN book='Numbers' THEN 4 WHEN book='Deuteronomy' THEN 5 WHEN book='Joshua' THEN 6
            WHEN book='Judges' THEN 7 WHEN book='1 Samuel' THEN 8 WHEN book='2 Samuel' THEN 9
            WHEN book='1 Kings' THEN 10 WHEN book='2 Kings' THEN 11 WHEN book='Isaiah' THEN 12
            WHEN book='Jeremiah' THEN 13 WHEN book='Ezekiel' THEN 14 WHEN book='Hosea' THEN 15
            WHEN book='Joel' THEN 16 WHEN book='Amos' THEN 17 WHEN book='Obadiah' THEN 18
            WHEN book='Jonah' THEN 19 WHEN book='Micah' THEN 20 WHEN book='Nahum' THEN 21
            WHEN book='Habakkuk' THEN 22 WHEN book='Zephaniah' THEN 23 WHEN book='Haggai' THEN 24
            WHEN book='Zechariah' THEN 25 WHEN book='Malachi' THEN 26 WHEN book='Psalms' THEN 27
            WHEN book='Proverbs' THEN 28 WHEN book='Job' THEN 29 WHEN book='Song of Songs' THEN 30
            WHEN book='Ruth' THEN 31 WHEN book='Lamentations' THEN 32 WHEN book='Ecclesiastes' THEN 33
            WHEN book='Esther' THEN 34 WHEN book='Daniel' THEN 35 WHEN book='Ezra' THEN 36
            WHEN book='Nehemiah' THEN 37 WHEN book='1 Chronicles' THEN 38 WHEN book='2 Chronicles' THEN 39
            ELSE 999 END, chapter, verse
    """

    cur = conn.execute(sql)
    matches = []

    for row in cur:
        verse_text = row["text"]
        clean_text = row["clean_text"]
        words = clean_text.split()

        if len(words) < word_len:
            continue

        # Slide window of word_len words
        for i in range(len(words) - word_len + 1):
            window_words = words[i:i + word_len]
            letters = ""
            valid = True

            for w in window_words:
                if not w:
                    valid = False
                    break
                try:
                    if offset == -1:
                        letters += w[-1]
                    elif offset >= 0 and offset < len(w):
                        letters += w[offset]
                    else:
                        valid = False
                        break
                except IndexError:
                    valid = False
                    break

            if valid and normalize_sofit(letters) == normalized_search:
                hebrew_book = book_to_hebrew(row["book"])
                ref = f"{hebrew_book} {row['chapter']}:{row['verse']}"
                # Get original words with nikud
                orig_words = verse_text.split()
                match_words = orig_words[i:i + word_len] if i + word_len <= len(orig_words) else window_words
                matches.append(RosheiTevotMatch(
                    ref=ref,
                    verse_text=verse_text,
                    words=match_words,
                    letters=letters,
                    start_word_idx=i
                ))

    conn.close()

    mode_display = "ראשי תיבות" if mode == "first" else ("סופי תיבות" if mode == "last" else f"אופסט {mode}")
    return RosheiTevotResult(
        search_word=clean_word,
        mode=mode_display,
        count=len(matches),
        matches=matches[:1000]  # Limit results
    )


# ============ ELS (Equidistant Letter Sequences) ============

_els_clean_cache: Optional[str] = None
_els_full_cache: Optional[str] = None
_els_positions_cache: Optional[List[Dict[str, Any]]] = None
_els_clean_to_full_map: Optional[List[int]] = None  # Maps clean text index to full text index

class ELSMatch(BaseModel):
    skip: int
    start_pos: int
    ref_start: str
    ref_end: str
    matched_letters: str  # The actual letters found
    letter_positions: List[int]  # Positions in full text for highlighting
    full_text: str  # Full text with nikud for display
    full_text_start: int  # Start position in full text

class ELSResult(BaseModel):
    search_word: str
    count: int
    matches: List[ELSMatch]

@app.get("/els", response_model=ELSResult)
def api_els(
    word: str = Query(..., min_length=2, max_length=10, description="מילה לחיפוש (2-10 אותיות)"),
    max_skip: int = Query(1000, ge=1, description="דילוג מקסימלי"),
    db: str = Query(default=None),
):
    """
    Search for equidistant letter sequences (ELS / דילוג אותיות).
    Finds the search word appearing at regular intervals in the text.
    """
    global _els_clean_cache, _els_full_cache, _els_positions_cache, _els_clean_to_full_map

    db_path = db or environ.get("DB_PATH", "tanakh.sqlite")

    # Clean search word
    clean_word = re.sub(r'[^\u05d0-\u05ea]', '', word)
    if len(clean_word) < 2:
        raise HTTPException(status_code=400, detail="נא להזין לפחות 2 אותיות")

    normalized_search = normalize_sofit(clean_word)

    # Build continuous text if not cached
    if _els_clean_cache is None:
        conn = connect(db_path)
        sql = """
            SELECT book, chapter, verse, text, clean_text
            FROM verses
            ORDER BY
                CASE WHEN book='Genesis' THEN 1 WHEN book='Exodus' THEN 2 WHEN book='Leviticus' THEN 3
                WHEN book='Numbers' THEN 4 WHEN book='Deuteronomy' THEN 5 WHEN book='Joshua' THEN 6
                WHEN book='Judges' THEN 7 WHEN book='1 Samuel' THEN 8 WHEN book='2 Samuel' THEN 9
                WHEN book='1 Kings' THEN 10 WHEN book='2 Kings' THEN 11 WHEN book='Isaiah' THEN 12
                WHEN book='Jeremiah' THEN 13 WHEN book='Ezekiel' THEN 14 WHEN book='Hosea' THEN 15
                WHEN book='Joel' THEN 16 WHEN book='Amos' THEN 17 WHEN book='Obadiah' THEN 18
                WHEN book='Jonah' THEN 19 WHEN book='Micah' THEN 20 WHEN book='Nahum' THEN 21
                WHEN book='Habakkuk' THEN 22 WHEN book='Zephaniah' THEN 23 WHEN book='Haggai' THEN 24
                WHEN book='Zechariah' THEN 25 WHEN book='Malachi' THEN 26 WHEN book='Psalms' THEN 27
                WHEN book='Proverbs' THEN 28 WHEN book='Job' THEN 29 WHEN book='Song of Songs' THEN 30
                WHEN book='Ruth' THEN 31 WHEN book='Lamentations' THEN 32 WHEN book='Ecclesiastes' THEN 33
                WHEN book='Esther' THEN 34 WHEN book='Daniel' THEN 35 WHEN book='Ezra' THEN 36
                WHEN book='Nehemiah' THEN 37 WHEN book='1 Chronicles' THEN 38 WHEN book='2 Chronicles' THEN 39
                ELSE 999 END, chapter, verse
        """
        cur = conn.execute(sql)

        clean_chars = []
        full_chars = []
        positions = []
        clean_to_full = []  # Maps each clean char index to its full text index

        for row in cur:
            clean_text = row["clean_text"].replace(" ", "")
            full_text = row["text"].replace(" ", "")  # Full text with nikud, no spaces
            hebrew_book = book_to_hebrew(row["book"])
            ref = f"{hebrew_book} {row['chapter']}:{row['verse']}"

            # Add full text
            full_start = len(full_chars)
            for char in full_text:
                full_chars.append(char)

            # Map clean chars to full text positions
            # Clean text only has base Hebrew letters, full has nikud
            full_idx = full_start
            for clean_char in clean_text:
                # Find this letter in full text (skip nikud)
                while full_idx < len(full_chars):
                    full_char = full_chars[full_idx]
                    # Check if it's a Hebrew letter (not nikud)
                    if '\u05d0' <= full_char <= '\u05ea':
                        break
                    full_idx += 1

                clean_to_full.append(full_idx)
                positions.append({"ref": ref})
                clean_chars.append(clean_char)
                full_idx += 1

        _els_clean_cache = "".join(clean_chars)
        _els_full_cache = "".join(full_chars)
        _els_positions_cache = positions
        _els_clean_to_full_map = clean_to_full
        conn.close()

    clean_text = _els_clean_cache
    full_text = _els_full_cache
    positions = _els_positions_cache
    clean_to_full = _els_clean_to_full_map
    text_normalized = normalize_sofit(clean_text)
    text_len = len(clean_text)
    word_len = len(normalized_search)

    matches = []

    # Search with different skip values
    for skip in range(1, min(max_skip + 1, text_len)):
        max_start = text_len - (word_len - 1) * skip - 1
        if max_start < 0:
            break

        for start in range(max_start + 1):
            found_word = ""
            for i in range(word_len):
                pos = start + i * skip
                if pos >= text_len:
                    break
                found_word += text_normalized[pos]

            if found_word == normalized_search:
                end_pos = start + (word_len - 1) * skip

                # Get letter positions in full text
                letter_positions = []
                matched_letters = ""
                for i in range(word_len):
                    clean_pos = start + i * skip
                    letter_positions.append(clean_to_full[clean_pos])
                    matched_letters += clean_text[clean_pos]

                # Get context in full text (with nikud)
                full_start = clean_to_full[start]
                full_end = clean_to_full[end_pos]
                ctx_start = max(0, full_start - 50)
                ctx_end = min(len(full_text), full_end + 51)

                # Adjust letter positions relative to context
                relative_positions = [p - ctx_start for p in letter_positions]

                matches.append(ELSMatch(
                    skip=skip,
                    start_pos=start,
                    ref_start=positions[start]["ref"],
                    ref_end=positions[end_pos]["ref"],
                    matched_letters=matched_letters,
                    letter_positions=relative_positions,
                    full_text=full_text[ctx_start:ctx_end],
                    full_text_start=ctx_start
                ))

                if len(matches) >= 500:
                    break

        if len(matches) >= 500:
            break

    return ELSResult(
        search_word=clean_word,
        count=len(matches),
        matches=matches
    )
