import secrets
import time
from typing import Optional

from fastapi import APIRouter, Header
from pydantic import BaseModel

from auth.common import bad
from post.common import db_put, sign_in
from shorts.common import MAX_TITLE, check_video, view_short

router = APIRouter()


class ShortBody(BaseModel):
    title: Optional[str] = ""
    videoUrl: Optional[str] = ""


@router.post("")
async def create_short(body: ShortBody, x_email: str = Header(None), x_password: str = Header(None)):
    uid, token, user = await sign_in(x_email, x_password)

    title = str(body.title or "").strip()
    if not title:
        bad("title is required")
    if len(title) > MAX_TITLE:
        bad(f"title must be at most {MAX_TITLE} characters")
    video = check_video(body.videoUrl)

    short_id = f"s{int(time.time() * 1000)}{secrets.token_hex(2)}"
    short = {
        "shortId": short_id,
        "title": title,
        "uploaderUid": uid,
        "uploadedDate": int(time.time() * 1000),
        "videoUrl": video,
        "views": 0,
    }

    await db_put(f"shorts/{short_id}", token, short)
    return view_short(short_id, short, uid)