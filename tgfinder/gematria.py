from __future__ import annotations
import re
import time
from typing import Dict
from .logging_config import get_logger
logger = get_logger(__name__)

# Invisible / format characters: nikud+trope (U+0591-U+05C7), CGJ (U+034F),
# zero-width chars (U+200B-U+200F), bidi controls (U+202A-U+202E), word joiner (U+2060),
# BOM/ZWNBSP (U+FEFF). All stripped with no replacement.
_HEBREW_MARKS_RE = re.compile(r"[\u0591-\u05C7\u034F\u200B-\u200F\u202A-\u202E\u2060\uFEFF]")
_NON_HEBREW_LETTERS_RE = re.compile(r"[^ \u05D0-\u05EA\u05DA\u05DD\u05DF\u05E3\u05E5]+")
# Masoretic scribal annotations: [t]aggin, [c]orrection, [d]otted, [m]ajuscule,
# [y]ud variant, [q]ere, [4][5][6][7][8] for letter sizes, [X] etc. \u2014 strip entirely.
_BRACKET_ANNOTATIONS_RE = re.compile(r"\[[a-zA-Z0-9]+\]")

_FINALS_MAP = str.maketrans({
    "ך": "כ",
    "ם": "מ",
    "ן": "נ",
    "ף": "פ",
    "ץ": "צ",
})

_GEMATRIA: Dict[str, int] = {
    "א": 1, "ב": 2, "ג": 3, "ד": 4, "ה": 5, "ו": 6, "ז": 7, "ח": 8, "ט": 9,
    "י": 10, "כ": 20, "ל": 30, "מ": 40, "נ": 50, "ס": 60, "ע": 70, "פ": 80, "צ": 90,
    "ק": 100, "ר": 200, "ש": 300, "ת": 400,
}

def normalize_hebrew(text: str) -> str:
    if not text:
        return ""
    # Replace separators BEFORE removing marks (maqaf is in marks range!)
    t = text.replace("־", " ")  # Hebrew maqaf (U+05BE)
    t = t.replace("-", " ")  # ASCII hyphen
    t = t.replace("׃", " ")  # Hebrew sof pasuq
    t = t.replace(" ", " ")  # NBSP -> regular space
    # Kethib (*word) is the actual written text — keep it. Qere (**word) is the read
    # variant — drop. ORDER: drop qere first (it has 2 stars), then strip * from kethib.
    t = re.sub(r"\*\*\S*", "", t)         # **qere -> (drop)
    t = re.sub(r"\*(\S+)", r"\1", t)      # *kethib -> kethib (strip leading *)
    t = _BRACKET_ANNOTATIONS_RE.sub("", t)  # Strip [c],[t],[d] scribal annotations
    t = _HEBREW_MARKS_RE.sub("", t)  # Remove nikud, CGJ, ZWJ, bidi etc.
    t = _NON_HEBREW_LETTERS_RE.sub(" ", t)
    t = t.translate(_FINALS_MAP)
    t = " ".join(t.split())
    return t

def letters_only(text: str) -> str:
    return normalize_hebrew(text).replace(" ", "")

def gematria(text: str) -> int:
    t = normalize_hebrew(text)
    total = 0
    start = time.perf_counter()
    for ch in t:
        if ch == " ":
            continue
        total += _GEMATRIA.get(ch, 0)
    elapsed = time.perf_counter() - start
    logger.debug("GEMATRIA_CALC text=%r letters=%d elapsed=%.3fs gematria=%d", text[:80], len(text), elapsed, total)
    return total

_ATBASH_MAP = str.maketrans(
    'אבגדהוזחטיכלמנסעפצקרשת',
    'תשרקצפעסנמלכיטחזוהדגבא',
)

def atbash(text: str) -> str:
    """Convert text using Atbash cipher (א↔ת, ב↔ש, ...)."""
    t = normalize_hebrew(text)
    return t.translate(_ATBASH_MAP)

def atbash_gematria(text: str) -> int:
    """Calculate gematria of Atbash-transformed text."""
    return gematria(atbash(text))
