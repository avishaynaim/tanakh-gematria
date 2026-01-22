import gdown
import os

from pathlib import Path

MIN_BYTES = 50_000_000  # 50MB

def _is_sqlite(p: Path) -> bool:
    if not p.exists() or p.stat().st_size < 16:
        return False
    with open(p, "rb") as f:
        return f.read(16) == b"SQLite format 3\x00"

def ensure_db() -> Path:
    """
    Ensures local SQLite DB exists and is valid.
    Downloads from Google Drive (via gdown) if missing/invalid/small.
    """
    db_path = Path(os.environ.get("DB_PATH", "tanakh.sqlite"))
    gdrive_id = os.environ.get("GDRIVE_ID", "1N7OSbfhYcAW97nhhxbLjlmn_oUOmpfcP")

    def ok() -> bool:
        return db_path.exists() and db_path.stat().st_size >= MIN_BYTES and _is_sqlite(db_path)

    if ok():
        print(f"[bootstrap_db] DB OK: {db_path} ({db_path.stat().st_size} bytes)", flush=True)
        return db_path

    if db_path.exists():
        print(f"[bootstrap_db] DB invalid/small -> deleting: {db_path} ({db_path.stat().st_size} bytes)", flush=True)
        try:
            db_path.unlink()
        except Exception:
            pass

    print(f"[bootstrap_db] Downloading DB from Google Drive id={gdrive_id} ...", flush=True)


    tmp = db_path.with_suffix(db_path.suffix + ".tmp")
    if tmp.exists():
        tmp.unlink()

    url = f"https://drive.google.com/uc?id={gdrive_id}"
    gdown.download(url, str(tmp), quiet=False, fuzzy=True)
    tmp.replace(db_path)

    print(f"[bootstrap_db] Downloaded: {db_path} ({db_path.stat().st_size} bytes)", flush=True)

    if not ok():
        raise RuntimeError(
            "Downloaded file is not a valid SQLite DB. "
            "Check Google Drive sharing: Anyone with the link."
        )

    return db_path
