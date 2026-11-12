import re

import httpx
from fastapi import HTTPException

from auth.common import DB_URL, PUBLIC_BASE, bad

TYPES = ("test", "exam", "festival", "school_event", "vacation", "emergency")
YEAR_MIN = 2000
YEAR_MAX = 2200
TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def to_int(value, label, low, high):
    if value is None or isinstance(value, bool) or str(value).strip() == "":
        bad(f"{label} is required")
    try:
        number = int(str(value).strip())
    except ValueError:
        bad(f"{label} must be a number")
    if not low <= number <= high:
        bad(f"{label} must be between {low} and {high}")
    return number


def clean_text(value, label, low, high, multiline=False):
    text = str(value or "").strip()
    if not multiline:
        text = re.sub(r"\s+", " ", text)
    if not low <= len(text) <= high:
        bad(f"{label} must be {low}-{high} characters")
    return text


def clean_time(value, label):
    text = str(value or "").strip()
    if not TIME.fullmatch(text):
        bad(f"{label} must be HH:MM (24-hour)")
    return text


def check_photo(raw):
    url = str(raw or "").strip()
    if not url:
        return ""
    if len(url) > 500 or not url.startswith(f"{PUBLIC_BASE}/img/"):
        bad("photoUrl must be an image URL from this server")
    return url


def can_edit(user):
    role = str(user.get("role", "")).lower()
    return role in ("professor", "captain") or user.get("isCaptain") is True


def num(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def as_dict(value):
    if isinstance(value, list):
        return {str(i): v for i, v in enumerate(value) if v is not None}
    return value if isinstance(value, dict) else {}


def sort_key(event):
    month = num(event.get("month") or event.get("startMonth"))
    day = num(event.get("day") or event.get("startDay"))
    return (month, day, str(event.get("startTime") or ""))


def event_list(node):
    items = []
    for key, value in as_dict(node).items():
        if isinstance(value, dict):
            items.append({"id": key, **value})
    items.sort(key=sort_key)
    return items


async def db_get(path):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{DB_URL}/calendar/{path}.json")
    if r.status_code in (401, 403):
        raise HTTPException(status_code=502, detail="Calendar read is not allowed by the database rules")
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Database request failed")
    return r.json()