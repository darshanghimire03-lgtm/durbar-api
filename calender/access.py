from typing import Optional

from fastapi import APIRouter

from auth.common import bad
from calender.common import TYPES, YEAR_MAX, YEAR_MIN, as_dict, db_get, event_list, num, to_int

router = APIRouter()


def build_month(node):
    node = as_dict(node)
    return {kind: event_list(node.get(kind)) for kind in TYPES}


@router.get("/national_day")
async def national_days(month: Optional[int] = None):
    items = event_list(await db_get("national_day"))
    if month is not None:
        if not 1 <= month <= 12:
            bad("month must be between 1 and 12")
        items = [e for e in items if num(e.get("month")) == month]
    return items


@router.get("/{year}")
async def get_year(year: int):
    to_int(year, "year", YEAR_MIN, YEAR_MAX)
    data = as_dict(await db_get(str(year)))
    return {
        "year": year,
        "months": {str(m): build_month(data.get(str(m))) for m in range(1, 13)},
    }


@router.get("/{year}/{month}")
async def get_month(year: int, month: int):
    to_int(year, "year", YEAR_MIN, YEAR_MAX)
    to_int(month, "month", 1, 12)
    return {"year": year, "month": month, "events": build_month(await db_get(f"{year}/{month}"))}


@router.get("/{year}/{month}/{kind}")
async def get_type(year: int, month: int, kind: str):
    to_int(year, "year", YEAR_MIN, YEAR_MAX)
    to_int(month, "month", 1, 12)
    if kind not in TYPES:
        bad("type must be one of: " + ", ".join(TYPES))
    return {
        "year": year,
        "month": month,
        "type": kind,
        "events": event_list(await db_get(f"{year}/{month}/{kind}")),
    }