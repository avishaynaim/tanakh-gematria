# Claude Code Notes - Tanakh Gematria

## Termux Build Limitations

**Cannot use /tmp folder in Android Termux** due to permission issues.

Commands that try to create files/directories in /tmp will fail with:
```
EACCES: permission denied, mkdir '/tmp/claude/...'
```

### Workarounds
- Avoid commands that use /tmp internally
- Use `git -C /full/path/` instead of `cd dir && git command`
- For Python projects, ensure temp files go to local directories

## Project Info

- FastAPI backend for Hebrew Bible (Tanakh) gematria search
- SQLite database with Hebrew text
- Frontend: Single-page HTML with vanilla JavaScript

## Key Features

- Gematria calculations and verse search
- Letter start/end search (אות פותחת/סוגרת)
- Kabbalah terms search (מושגי קבלה)
- Book selector for filtering results

## Hebrew Text Notes

- Final letters (sofit) are normalized to regular letters for searching:
  - ך → כ, ם → מ, ן → נ, ף → פ, ץ → צ

## Running the Server

```bash
cd /data/data/com.termux/files/home/workspace/tanakh-gematria/tgfinder
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```
