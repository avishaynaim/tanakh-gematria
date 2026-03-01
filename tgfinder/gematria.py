from __future__ import annotations
import re
from typing import Dict

_HEBREW_MARKS_RE = re.compile(r"[\u0591-\u05C7]")
_NON_HEBREW_LETTERS_RE = re.compile(r"[^ \u05D0-\u05EA\u05DA\u05DD\u05DF\u05E3\u05E5]+")

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
    t = _HEBREW_MARKS_RE.sub("", t)  # Remove nikud and other marks
    t = _NON_HEBREW_LETTERS_RE.sub(" ", t)
    t = t.translate(_FINALS_MAP)
    t = " ".join(t.split())
    return t

def letters_only(text: str) -> str:
    return normalize_hebrew(text).replace(" ", "")

def gematria(text: str) -> int:
    t = normalize_hebrew(text)
    total = 0
    for ch in t:
        if ch == " ":
            continue
        total += _GEMATRIA.get(ch, 0)
    return total

_ATBASH_MAP = str.maketrans(
    'אבגדהוזחטיכלמנסעפצקרשת',
    'תשרקצפעסנמלכיטחזופהדגבא'
)

def atbash(text: str) -> str:
    """Convert text using Atbash cipher (א↔ת, ב↔ש, ...)."""
    t = normalize_hebrew(text)
    return t.translate(_ATBASH_MAP)

def atbash_gematria(text: str) -> int:
    """Calculate gematria of Atbash-transformed text."""
    return gematria(atbash(text))
