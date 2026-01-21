from __future__ import annotations
import argparse
import json

from .ingest import ingest
from .search import search

def cmd_ingest(args: argparse.Namespace) -> int:
    ingest(
        input_path=args.input,
        fmt=args.format,
        db_path=args.db,
        max_ngram=args.max_ngram,
        books=args.books,
        commit_every=args.commit_every,
    )
    return 0

def cmd_search(args: argparse.Namespace) -> int:
    hits = search(
        db_path=args.db,
        value=args.value,
        kind=args.kind,
        n=args.n,
        limit=args.limit,
        offset=args.offset,
    )
    if args.json:
        print(json.dumps([h.__dict__ for h in hits], ensure_ascii=False, indent=2))
        return 0

    if not hits:
        print("No matches.")
        return 0

    for h in hits:
        n_part = f" n={h.n}" if h.n else ""
        print(f"[{h.kind}{n_part}] {h.ref}  =>  {h.gematria}")
        print(f"  {h.text}")
    return 0

def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn
    uvicorn.run(
        "tgfinder.api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )
    return 0

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tgfinder", description="Tanakh Gematria Finder (Python + SQLite)")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_ing = sub.add_parser("ingest", help="Ingest Tanakh into SQLite with gematria index")
    p_ing.add_argument("--input", required=True, help="Input file path (TSV or JSON)")
    p_ing.add_argument("--format", required=True, choices=["tsv", "sefaria_json"], help="Input format")
    p_ing.add_argument("--db", default="tanakh.sqlite", help="SQLite DB path")
    p_ing.add_argument("--max-ngram", type=int, default=10, dest="max_ngram", help="Max word n-gram length (1..10)")
    p_ing.add_argument("--books", nargs="*", default=None, help="Optional list of book names to ingest (exact match)")
    p_ing.add_argument("--commit-every", type=int, default=2000, dest="commit_every", help="Commit batch size")
    p_ing.set_defaults(func=cmd_ingest)

    p_s = sub.add_parser("search", help="Search by gematria value")
    p_s.add_argument("--db", default="tanakh.sqlite", help="SQLite DB path")
    p_s.add_argument("--value", type=int, required=True, help="Gematria value to search")
    p_s.add_argument("--kind", choices=["verse", "word", "gram"], default=None, help="Filter kind")
    p_s.add_argument("--n", type=int, default=None, help="For kind=gram: choose n (1..10)")
    p_s.add_argument("--limit", type=int, default=50)
    p_s.add_argument("--offset", type=int, default=0)
    p_s.add_argument("--json", action="store_true", help="Output JSON")
    p_s.set_defaults(func=cmd_search)

    p_srv = sub.add_parser("serve", help="Run FastAPI server")
    p_srv.add_argument("--host", default="127.0.0.1")
    p_srv.add_argument("--port", type=int, default=8000)
    p_srv.add_argument("--reload", action="store_true")
    p_srv.set_defaults(func=cmd_serve)

    return p

def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)

if __name__ == "__main__":
    raise SystemExit(main())
