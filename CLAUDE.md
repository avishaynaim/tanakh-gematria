# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run web server (extracts tanakh.sqlite from zip on first run)
python -m tgfinder serve --host 127.0.0.1 --port 8000
python -m tgfinder serve --reload  # dev mode with auto-reload

# CLI search
python -m tgfinder search --value 358 --kind verse --limit 50 --json

# Ingest new data (rarely needed - database is pre-built)
python -m tgfinder ingest --input data.tsv --format tsv --db tanakh.sqlite
```

## Architecture

**FastAPI + SQLite single-page app** for searching Hebrew Bible (Tanakh) by gematria values.

### Core Flow
1. `api.py` serves `ui.html` at `/` and provides REST endpoints
2. On startup, `bootstrap_db.py` extracts `tanakh.sqlite` from the zip if missing
3. Search queries go through `search.py` which queries SQLite with canonical Tanakh book ordering
4. `gematria.py` handles Hebrew text normalization and numeric calculation

### Database Schema (tanakh.sqlite)
- **verses**: Full verses with pre-computed gematria values
  - `book, chapter, verse, text, clean_text, letters, gematria`
- **grams**: Word n-grams (1-10 words) with gematria for phrase searches
  - `n, book, chapter, verse, start_word, end_word, text, clean_text, letters, gematria`

### Search Types (kind parameter)
- `verse`: Match entire verse gematria
- `word`: Match single word (n=1 gram)
- `gram`: Match multi-word phrases (n-grams)

### Key Implementation Details
- Hebrew final letters (sofit) normalized: ך→כ, ם→מ, ן→נ, ף→פ, ץ→צ
- Maqaf (־) and sof pasuq (׃) replaced with spaces before calculation
- Results sorted by canonical Jewish Tanakh order (Torah → Nevi'im → Ketuvim)
- Book names stored in English, converted to Hebrew for display via `_BOOK_MAP`

## Environment Variables
- `DB_PATH`: SQLite database path (default: `tanakh.sqlite`)

## Termux Notes
Cannot use `/tmp` folder due to Android permission issues. Use local directories for temp files.
