# Tanakh Gematria Finder — ברירת מחדל: כל התוצאות

שינוי:
- ברירת המחדל לחיפוש היא **להחזיר את כל התוצאות** (ללא LIMIT).
- אם רוצים להגביל, בוחרים ב־UI מקסימום תוצאות (25/50/100/…),
  או שולחים `limit=50` ל־API.

## הרצה
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m tgfinder serve --host 127.0.0.1 --port 8000
```


## סדר תוצאות
התוצאות ממוינות לפי **סדר ספרי התנ"ך**, ואז לפי פרק ואז פסוק.
