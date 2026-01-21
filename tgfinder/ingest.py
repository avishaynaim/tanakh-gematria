from __future__ import annotations
import json
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

from .gematria import normalize_hebrew, letters_only, gematria
from .db import connect, init_db, insert_verses, insert_grams

VerseRow = Tuple[str,int,int,str]  # (book, chapter, verse, text)

def iter_tsv(path: Path) -> Iterator[VerseRow]:
    with path.open("r", encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            line = line.rstrip("\n")
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 4:
                raise ValueError(f"Bad TSV line {ln}: expected 4 columns, got {len(parts)}")
            book = parts[0].strip()
            chapter = int(parts[1])
            verse = int(parts[2])
            text = "\t".join(parts[3:]).strip()
            yield (book, chapter, verse, text)

def iter_sefaria_json(path: Path) -> Iterator[VerseRow]:
    data = json.loads(path.read_text(encoding="utf-8"))

    def emit(book: str, chapters: List[List[str]]):
        for c_idx, verses in enumerate(chapters, 1):
            if verses is None:
                continue
            for v_idx, vtext in enumerate(verses, 1):
                if vtext is None:
                    continue
                yield (book, c_idx, v_idx, str(vtext))

    if isinstance(data, dict) and "books" in data and isinstance(data["books"], list):
        for b in data["books"]:
            title = b.get("title") or b.get("book") or b.get("name")
            chapters = b.get("chapters") or b.get("text")
            if not title or not isinstance(chapters, list):
                continue
            yield from emit(str(title), chapters)

    elif isinstance(data, dict):
        for book, chapters in data.items():
            if isinstance(chapters, list):
                yield from emit(str(book), chapters)

    elif isinstance(data, list):
        for b in data:
            if not isinstance(b, dict):
                continue
            title = b.get("title") or b.get("book") or b.get("name")
            chapters = b.get("chapters") or b.get("text")
            if not title or not isinstance(chapters, list):
                continue
            yield from emit(str(title), chapters)
    else:
        raise ValueError("Unsupported JSON shape")

def build_ngrams(words: List[str], max_n: int):
    L = len(words)
    for i in range(L):
        for n in range(1, max_n + 1):
            j = i + n - 1
            if j >= L:
                break
            yield (n, i, j, " ".join(words[i:j+1]))

def ingest(
    input_path: str,
    fmt: str,
    db_path: str,
    max_ngram: int = 10,
    books: Optional[List[str]] = None,
    commit_every: int = 2000,
) -> None:
    in_path = Path(input_path)
    if not in_path.exists():
        raise FileNotFoundError(str(in_path))

    if fmt == "tsv":
        verse_iter = iter_tsv(in_path)
    elif fmt == "sefaria_json":
        verse_iter = iter_sefaria_json(in_path)
    else:
        raise ValueError("format must be: tsv | sefaria_json")

    books_set = set([b.strip() for b in books]) if books else None

    conn = connect(db_path)
    init_db(conn)

    v_rows = []
    g_rows = []
    total_v = 0
    total_g = 0

    for (book, chapter, verse, text) in verse_iter:
        if books_set and book not in books_set:
            continue

        clean = normalize_hebrew(text)
        lett = letters_only(text)
        vgem = gematria(text)

        v_rows.append((book, chapter, verse, text, clean, lett, vgem))
        total_v += 1

        words = clean.split() if clean else []
        if words:
            for (n, i, j, gram_text) in build_ngrams(words, max_ngram):
                gram_clean = gram_text
                gram_letters = gram_clean.replace(" ", "")
                ggem = gematria(gram_clean)
                g_rows.append((n, book, chapter, verse, i+1, j+1, gram_text, gram_clean, gram_letters, ggem))
                total_g += 1

        if len(v_rows) >= commit_every:
            insert_verses(conn, v_rows)
            v_rows.clear()
            conn.commit()

        if len(g_rows) >= commit_every:
            insert_grams(conn, g_rows)
            g_rows.clear()
            conn.commit()

    if v_rows:
        insert_verses(conn, v_rows)
    if g_rows:
        insert_grams(conn, g_rows)
    conn.commit()
    conn.close()

    print(f"Done. Verses indexed: {total_v:,}. Word-grams indexed: {total_g:,}. DB: {db_path}")
