from typing import Optional

from fastapi import APIRouter, Header

from post.common import as_dict, db_get, db_put, num, sign_in
from shorts.common import PAGE_MAX, load_short, view_short

router = APIRouter()


@router.get("")
async def feed(
    limit: int = 10,
    before: Optional[int] = None,
    x_email: str = Header(None),
    x_password: str = Header(None),
):
    uid, token, user = await sign_in(x_email, x_password)
    limit = max(1, min(limit, PAGE_MAX))

    raw = as_dict(await db_get("shorts", token))
    shorts = [(k, v) for k, v in raw.items() if isinstance(v, dict)]
    shorts.sort(key=lambda kv: num(kv[1].get("uploadedDate")), reverse=True)

    if before:
        shorts = [kv for kv in shorts if num(kv[1].get("uploadedDate")) < before]

    page = shorts[:limit]
    next_before = num(page[-1][1].get("uploadedDate")) if len(shorts) > limit else None

    return {"shorts": [view_short(k, v, uid) for k, v in page], "nextBefore": next_before}


@router.get("/{short_id}")
async def get_short(short_id: str, x_email: str = Header(None), x_password: str = Header(None)):
    uid, token, user = await sign_in(x_email, x_password)
    short = await load_short(short_id, token)
    return view_short(short_id, short, uid)


@router.post("/{short_id}/view")
async def add_view(short_id: str, x_email: str = Header(None), x_password: str = Header(None)):
    uid, token, user = await sign_in(x_email, x_password)
    short = await load_short(short_id, token)
    views = num(short.get("views")) + 1
    await db_put(f"shorts/{short_id}/views", token, views)
    return {"shortId": short_id, "views": views}