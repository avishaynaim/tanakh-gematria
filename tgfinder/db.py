from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Iterable, Tuple

SCHEMA = r'''
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS verses (
  id INTEGER PRIMARY KEY,
  book TEXT NOT NULL,
  chapter INTEGER NOT NULL,
  verse INTEGER NOT NULL,
  text TEXT NOT NULL,
  clean_text TEXT NOT NULL,
  letters TEXT NOT NULL,
  gematria INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_verses_ref ON verses(book, chapter, verse);
CREATE INDEX IF NOT EXISTS idx_verses_gem ON verses(gematria);

CREATE TABLE IF NOT EXISTS grams (
  id INTEGER PRIMARY KEY,
  n INTEGER NOT NULL,
  book TEXT NOT NULL,
  chapter INTEGER NOT NULL,
  verse INTEGER NOT NULL,
  start_word INTEGER NOT NULL,
  end_word INTEGER NOT NULL,
  text TEXT NOT NULL,
  clean_text TEXT NOT NULL,
  letters TEXT NOT NULL,
  gematria INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_grams_gem ON grams(gematria);
CREATE INDEX IF NOT EXISTS idx_grams_n_gem ON grams(n, gematria);
CREATE INDEX IF NOT EXISTS idx_grams_ref ON grams(book, chapter, verse, start_word, end_word);
'''

def connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn

def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()

def insert_verses(conn: sqlite3.Connection, rows: Iterable[Tuple[str,int,int,str,str,str,int]]) -> None:
    conn.executemany(
        "INSERT INTO verses(book,chapter,verse,text,clean_text,letters,gematria) VALUES (?,?,?,?,?,?,?)",
        rows
    )

def insert_grams(conn: sqlite3.Connection, rows: Iterable[Tuple[int,str,int,int,int,int,str,str,str,int]]) -> None:
    conn.executemany(
        "INSERT INTO grams(n,book,chapter,verse,start_word,end_word,text,clean_text,letters,gematria) VALUES (?,?,?,?,?,?,?,?,?,?)",
        rows
    )
