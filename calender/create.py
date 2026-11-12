import secrets
import time
from typing import Any, List, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from auth.common import DB_URL, bad, db_read, fb_call
from calender.common import (
    TYPES,
    YEAR_MAX,
    YEAR_MIN,
    can_edit,
    check_photo,
    clean_text,
    clean_time,
    to_int,
)

router = APIRouter()


class CreateBody(BaseModel):
    email: str
    password: str
    type: str
    year: Optional[Any] = None
    month: Optional[Any] = None
    day: Optional[Any] = None
    title: Optional[str] = None
    description: Optional[str] = ""
    photoUrl: Optional[str] = ""
    subjects: Optional[List[str]] = None
    subject: Optional[str] = None
    startTime: Optional[str] = None
    endTime: Optional[str] = None
    startMonth: Optional[Any] = None
    startDay: Optional[Any] = None
    endMonth: Optional[Any] = None
    endDay: Optional[Any] = None


def new_event_id():
    return f"e{int(time.time() * 1000)}{secrets.token_hex(2)}"


def build_event(body: CreateBody):
    kind = str(body.type or "").strip().lower()
    if kind != "national_day" and kind not in TYPES:
        bad("type must be one of: " + ", ".join(TYPES) + ", national_day")

    if kind == "national_day":
        event = {
            "month": to_int(body.month, "month", 1, 12),
            "day": to_int(body.day, "day", 1, 32),
            "title": clean_text(body.title, "title", 1, 100),
            "description": clean_text(body.description, "description", 0, 1000, True),
            "photoUrl": check_photo(body.photoUrl),
        }
        return kind, None, None, event

    year = to_int(body.year, "year", YEAR_MIN, YEAR_MAX)

    if kind == "vacation":
        start_month = to_int(body.startMonth, "startMonth", 1, 12)
        start_day = to_int(body.startDay, "startDay", 1, 32)
        end_month = to_int(body.endMonth, "endMonth", 1, 12)
        end_day = to_int(body.endDay, "endDay", 1, 32)
        if (end_month, end_day) < (start_month, start_day):
            bad("Vacation end must not be before its start")
        event = {
            "startMonth": start_month,
            "startDay": start_day,
            "endMonth": end_month,
            "endDay": end_day,
            "title": clean_text(body.title, "title", 1, 100),
            "description": clean_text(body.description, "description", 0, 1000, True),
        }
        return kind, year, start_month, event

    month = to_int(body.month, "month", 1, 12)
    day = to_int(body.day, "day", 1, 32)

    if kind == "test":
        raw = body.subjects or []
        subjects = list(dict.fromkeys(clean_text(s, "subject", 1, 60) for s in raw))
        if not 1 <= len(subjects) <= 20:
            bad("subjects must have 1-20 items")
        event = {"day": day, "subjects": subjects}
    elif kind == "exam":
        start = clean_time(body.startTime, "startTime")
        end = clean_time(body.endTime, "endTime")
        if end <= start:
            bad("endTime must be after startTime")
        event = {
            "day": day,
            "subject": clean_text(body.subject, "subject", 1, 60),
            "startTime": start,
            "endTime": end,
        }
    else:
        event = {
            "day": day,
            "title": clean_text(body.title, "title", 1, 100),
            "description": clean_text(body.description, "description", 0, 1000, True),
            "photoUrl": check_photo(body.photoUrl),
        }

    return kind, year, month, event


@router.post("/create")
async def create(body: CreateBody):
    kind, year, month, event = build_event(body)

    email = str(body.email or "").strip().lower()
    if not email or not body.password:
        bad("Email and password are required")

    signed = await fb_call(
        "signInWithPassword",
        {"email": email, "password": body.password, "returnSecureToken": True},
    )
    uid = signed["localId"]
    token = signed["idToken"]

    user = await db_read(uid, token)
    if user is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    if not can_edit(user):
        raise HTTPException(status_code=403, detail="Only professors and captains can add calendar events")

    event_id = new_event_id()
    if kind == "national_day":
        event = {"id": event_id, **event}
        path = f"calendar/national_day/{event_id}"
    else:
        path = f"calendar/{year}/{month}/{kind}/{event_id}"
    event["createdBy"] = uid
    event["createdAt"] = int(time.time() * 1000)

    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.put(f"{DB_URL}/{path}.json", params={"auth": token}, json=event)
    if r.status_code in (401, 403):
        raise HTTPException(status_code=403, detail="Database rules do not allow this user to write the calendar")
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Could not save event")

    result = {"id": event_id, "type": kind}
    if year is not None:
        result["year"] = year
        result["month"] = month
    result.update(event)
    return result