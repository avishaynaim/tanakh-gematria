import os
import sys
from pathlib import Path

DB_PATH = Path(os.environ.get("DB_PATH", "tanakh.sqlite"))
GDRIVE_ID = os.environ.get("GDRIVE_ID", "1N7OSbfhYcAW97nhhxbLjlmn_oUOmpfcP")
MIN_BYTES = 50_000_000  # 50MB

def size_ok(p: Path) -> bool:
    return p.exists() and p.stat().st_size >= MIN_BYTES

def is_sqlite(p: Path) -> bool:
    if not p.exists() or p.stat().st_size < 16:
        return False
    with open(p, "rb") as f:
        return f.read(16) == b"SQLite format 3\x00"

def download_with_gdown(file_id: str, dest: Path) -> None:
    import gdown
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    if tmp.exists():
        tmp.unlink()
    url = f"https://drive.google.com/uc?id={file_id}"
    print(f"[bootstrap] Downloading from Google Drive id={file_id}", flush=True)
    gdown.download(url, str(tmp), quiet=False, fuzzy=True)
    tmp.replace(dest)
    print(f"[bootstrap] Downloaded: {dest} ({dest.stat().st_size} bytes)", flush=True)

def main() -> int:
    if size_ok(DB_PATH) and is_sqlite(DB_PATH):
        print(f"[bootstrap] DB OK: {DB_PATH} ({DB_PATH.stat().st_size} bytes)", flush=True)
        return 0

    if DB_PATH.exists():
        print(f"[bootstrap] DB invalid/small: {DB_PATH} ({DB_PATH.stat().st_size} bytes). Re-downloading...", flush=True)
        try:
            DB_PATH.unlink()
        except Exception:
            pass

    download_with_gdown(GDRIVE_ID, DB_PATH)

    if not (size_ok(DB_PATH) and is_sqlite(DB_PATH)):
        print("[bootstrap] ERROR: downloaded file is not a valid SQLite DB. Check Drive sharing (Anyone with link).", flush=True)
        return 2

    return 0

if __name__ == "__main__":
    sys.exit(main())
