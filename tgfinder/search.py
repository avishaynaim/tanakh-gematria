from __future__ import annotations
from dataclasses import dataclass
from typing import List, Literal, Optional, Dict, Any, Tuple

from .db import connect

Kind = Literal["verse", "word", "gram"]

_BOOK_MAP: Dict[str, str] = {'Genesis': 'בראשית', 'Exodus': 'שמות', 'Leviticus': 'ויקרא', 'Numbers': 'במדבר', 'Deuteronomy': 'דברים', 'Joshua': 'יהושע', 'Judges': 'שופטים', 'Ruth': 'רות', '1 Samuel': 'שמואל א', '2 Samuel': 'שמואל ב', '1 Kings': 'מלכים א', '2 Kings': 'מלכים ב', '1 Chronicles': 'דברי הימים א', '2 Chronicles': 'דברי הימים ב', 'Ezra': 'עזרא', 'Nehemiah': 'נחמיה', 'Esther': 'אסתר', 'Job': 'איוב', 'Psalms': 'תהילים', 'Proverbs': 'משלי', 'Ecclesiastes': 'קהלת', 'Song of Songs': 'שיר השירים', 'Isaiah': 'ישעיהו', 'Jeremiah': 'ירמיהו', 'Lamentations': 'איכה', 'Ezekiel': 'יחזקאל', 'Daniel': 'דניאל', 'Hosea': 'הושע', 'Joel': 'יואל', 'Amos': 'עמוס', 'Obadiah': 'עובדיה', 'Jonah': 'יונה', 'Micah': 'מיכה', 'Nahum': 'נחום', 'Habakkuk': 'חבקוק', 'Zephaniah': 'צפניה', 'Haggai': 'חגי', 'Zechariah': 'זכריה', 'Malachi': 'מלאכי', 'Chronicles_1': 'דברי הימים א', 'Chronicles_2': 'דברי הימים ב', 'Samuel_1': 'שמואל א', 'Samuel_2': 'שמואל ב', 'Kings_1': 'מלכים א', 'Kings_2': 'מלכים ב'}

def book_to_hebrew(book: str) -> str:
    return _BOOK_MAP.get(book, book)

@dataclass
class Hit:
    kind: str
    ref: str
    n: Optional[int]
    text: str
    clean_text: str
    gematria: int
    match_text: Optional[str] = None
    match_range: Optional[str] = None

def _ref(book: str, chapter: int, verse: int) -> str:
    b = book_to_hebrew(book)
    return f"{b} {chapter}:{verse}"

def _limit_clause(limit: Optional[int], offset: int) -> Tuple[str, Tuple[Any, ...]]:
    if limit is None:
        return "", tuple()
    return " LIMIT ? OFFSET ? ", (limit, offset)

# Canonical Tanakh order (Jewish order) via CASE expression (SQLite)
_BOOK_ORDER_CASE = """CASE WHEN book='Genesis' THEN 1 WHEN book='Exodus' THEN 2 WHEN book='Leviticus' THEN 3 WHEN book='Numbers' THEN 4 WHEN book='Deuteronomy' THEN 5 WHEN book='Joshua' THEN 6 WHEN book='Judges' THEN 7 WHEN book='1 Samuel' THEN 8 WHEN book='2 Samuel' THEN 9 WHEN book='1 Kings' THEN 10 WHEN book='2 Kings' THEN 11 WHEN book='Isaiah' THEN 12 WHEN book='Jeremiah' THEN 13 WHEN book='Ezekiel' THEN 14 WHEN book='Hosea' THEN 15 WHEN book='Joel' THEN 16 WHEN book='Amos' THEN 17 WHEN book='Obadiah' THEN 18 WHEN book='Jonah' THEN 19 WHEN book='Micah' THEN 20 WHEN book='Nahum' THEN 21 WHEN book='Habakkuk' THEN 22 WHEN book='Zephaniah' THEN 23 WHEN book='Haggai' THEN 24 WHEN book='Zechariah' THEN 25 WHEN book='Malachi' THEN 26 WHEN book='Psalms' THEN 27 WHEN book='Proverbs' THEN 28 WHEN book='Job' THEN 29 WHEN book='Song of Songs' THEN 30 WHEN book='Ruth' THEN 31 WHEN book='Lamentations' THEN 32 WHEN book='Ecclesiastes' THEN 33 WHEN book='Esther' THEN 34 WHEN book='Daniel' THEN 35 WHEN book='Ezra' THEN 36 WHEN book='Nehemiah' THEN 37 WHEN book='1 Chronicles' THEN 38 WHEN book='2 Chronicles' THEN 39 WHEN book='Samuel_1' THEN 8 WHEN book='Samuel_2' THEN 9 WHEN book='Kings_1' THEN 10 WHEN book='Kings_2' THEN 11 WHEN book='Chronicles_1' THEN 38 WHEN book='Chronicles_2' THEN 39 ELSE 999 END"""
_GBOOK_ORDER_CASE = """CASE WHEN g.book='Genesis' THEN 1 WHEN g.book='Exodus' THEN 2 WHEN g.book='Leviticus' THEN 3 WHEN g.book='Numbers' THEN 4 WHEN g.book='Deuteronomy' THEN 5 WHEN g.book='Joshua' THEN 6 WHEN g.book='Judges' THEN 7 WHEN g.book='1 Samuel' THEN 8 WHEN g.book='2 Samuel' THEN 9 WHEN g.book='1 Kings' THEN 10 WHEN g.book='2 Kings' THEN 11 WHEN g.book='Isaiah' THEN 12 WHEN g.book='Jeremiah' THEN 13 WHEN g.book='Ezekiel' THEN 14 WHEN g.book='Hosea' THEN 15 WHEN g.book='Joel' THEN 16 WHEN g.book='Amos' THEN 17 WHEN g.book='Obadiah' THEN 18 WHEN g.book='Jonah' THEN 19 WHEN g.book='Micah' THEN 20 WHEN g.book='Nahum' THEN 21 WHEN g.book='Habakkuk' THEN 22 WHEN g.book='Zephaniah' THEN 23 WHEN g.book='Haggai' THEN 24 WHEN g.book='Zechariah' THEN 25 WHEN g.book='Malachi' THEN 26 WHEN g.book='Psalms' THEN 27 WHEN g.book='Proverbs' THEN 28 WHEN g.book='Job' THEN 29 WHEN g.book='Song of Songs' THEN 30 WHEN g.book='Ruth' THEN 31 WHEN g.book='Lamentations' THEN 32 WHEN g.book='Ecclesiastes' THEN 33 WHEN g.book='Esther' THEN 34 WHEN g.book='Daniel' THEN 35 WHEN g.book='Ezra' THEN 36 WHEN g.book='Nehemiah' THEN 37 WHEN g.book='1 Chronicles' THEN 38 WHEN g.book='2 Chronicles' THEN 39 WHEN g.book='Samuel_1' THEN 8 WHEN g.book='Samuel_2' THEN 9 WHEN g.book='Kings_1' THEN 10 WHEN g.book='Kings_2' THEN 11 WHEN g.book='Chronicles_1' THEN 38 WHEN g.book='Chronicles_2' THEN 39 ELSE 999 END"""

def search(
    db_path: str,
    value: int,
    kind: Optional[Kind] = None,
    n: Optional[int] = None,
    limit: Optional[int] = None,   # None = return all
    offset: int = 0,
    book: Optional[str] = None,  # Filter by book
) -> List[Hit]:
    conn = connect(db_path)
    hits: List[Hit] = []

    if kind in (None, "verse"):
        lim_sql, lim_params = _limit_clause(limit, offset)
        where_clauses = ["gematria=?"]
        params_list = [value]
        if book:
            where_clauses.append("book=?")
            params_list.append(book)
        where_sql = " AND ".join(where_clauses)
        sql = (
            "SELECT book,chapter,verse,text,clean_text,gematria FROM verses "
            f"WHERE {where_sql} "
            f"ORDER BY {_BOOK_ORDER_CASE}, chapter, verse" + lim_sql
        )
        cur = conn.execute(sql, (*params_list, *lim_params))
        for r in cur.fetchall():
            hits.append(Hit(
                kind="verse",
                ref=_ref(r["book"], r["chapter"], r["verse"]),
                n=None,
                text=r["text"],
                clean_text=r["clean_text"],
                gematria=r["gematria"],
            ))

    if kind in (None, "word", "gram"):
        base_sql = (
            "SELECT g.n,g.book,g.chapter,g.verse,g.start_word,g.end_word,g.text AS match_text,"
            " v.text AS verse_text, v.clean_text AS verse_clean, g.gematria "
            "FROM grams g JOIN verses v "
            "ON v.book=g.book AND v.chapter=g.chapter AND v.verse=g.verse "
        )

        where_clauses = []
        order = ""
        params_list = []

        if kind == "word":
            where_clauses.append("g.n=1")
            where_clauses.append("g.gematria=?")
            params_list.append(value)
            order = f"ORDER BY {_GBOOK_ORDER_CASE}, g.chapter, g.verse, g.start_word "
        elif kind == "gram":
            if n is None:
                where_clauses.append("g.gematria=?")
                params_list.append(value)
                order = f"ORDER BY {_GBOOK_ORDER_CASE}, g.chapter, g.verse, g.start_word, g.n "
            else:
                where_clauses.append("g.n=?")
                where_clauses.append("g.gematria=?")
                params_list.extend([n, value])
                order = f"ORDER BY {_GBOOK_ORDER_CASE}, g.chapter, g.verse, g.start_word "
        else:
            where_clauses.append("g.gematria=?")
            params_list.append(value)
            order = f"ORDER BY {_GBOOK_ORDER_CASE}, g.chapter, g.verse, g.start_word, g.n "

        if book:
            where_clauses.append("g.book=?")
            params_list.append(book)

        where = "WHERE " + " AND ".join(where_clauses) + " "
        params: Tuple[Any, ...] = tuple(params_list)

        lim_sql, lim_params = _limit_clause(limit, offset)
        sql = base_sql + where + order + lim_sql
        cur = conn.execute(sql, (*params, *lim_params))

        for r in cur.fetchall():
            k = "word" if int(r["n"]) == 1 else "gram"
            rng = f"מילים {r['start_word']}–{r['end_word']}"
            hits.append(Hit(
                kind=k,
                ref=_ref(r["book"], r["chapter"], r["verse"]),
                n=int(r["n"]),
                text=r["verse_text"],
                clean_text=r["verse_clean"],
                gematria=int(r["gematria"]),
                match_text=r["match_text"],
                match_range=rng,
            ))

    conn.close()
    return hits
