import os
import sys
import urllib.request
from pathlib import Path

DB_PATH = Path(os.environ.get("DB_PATH", "tanakh.sqlite"))
DB_URL = os.environ.get(
    "DB_URL",
    "https://drive.google.com/uc?export=download&id=1N7OSbfhYcAW97nhhxbLjlmn_oUOmpfcP",
)

# אם הקובץ לא קיים / קטן מדי (LFS pointer) -> להוריד מחדש
MIN_BYTES = 50_000_000  # 50MB

def size_ok(p: Path) -> bool:
    return p.exists() and p.stat().st_size >= MIN_BYTES

def download(url: str, dest: Path):
    print(f"[bootstrap] Downloading DB from: {url}", flush=True)
    dest_tmp = dest.with_suffix(dest.suffix + ".tmp")
    if dest_tmp.exists():
        dest_tmp.unlink()

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest_tmp, "wb") as f:
        while True:
            chunk = r.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)

    dest_tmp.replace(dest)
    print(f"[bootstrap] DB saved: {dest} ({dest.stat().st_size} bytes)", flush=True)

def main():
    if size_ok(DB_PATH):
        print(f"[bootstrap] DB exists and size ok: {DB_PATH} ({DB_PATH.stat().st_size} bytes)", flush=True)
        return 0

    print(f"[bootstrap] DB missing/small -> will download. Current: "
          f"{DB_PATH.stat().st_size if DB_PATH.exists() else 0} bytes", flush=True)

    download(DB_URL, DB_PATH)

    # sanity: ensure it's big enough
    if not size_ok(DB_PATH):
        print("[bootstrap] ERROR: DB downloaded but still too small. "
              "Check Google Drive sharing permissions (Anyone with link).", flush=True)
        return 2

    return 0

if __name__ == "__main__":
    sys.exit(main())
