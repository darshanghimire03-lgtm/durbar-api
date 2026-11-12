from fastapi import HTTPException

from auth.common import PUBLIC_BASE, bad
from post.common import as_dict, check_id, db_get, num

MAX_TITLE = 150
PAGE_MAX = 30


def check_video(raw):
    url = str(raw or "").strip()
    if not url:
        bad("videoUrl is required")
    if len(url) > 500 or not url.startswith(f"{PUBLIC_BASE}/vid/"):
        bad("Video URLs must come from this server's video upload")
    return url


def view_short(short_id, s, uid):
    likes = as_dict(s.get("likes"))
    return {
        "shortId": short_id,
        "title": s.get("title", ""),
        "uploaderUid": s.get("uploaderUid", ""),
        "uploadedDate": num(s.get("uploadedDate")),
        "videoUrl": s.get("videoUrl", ""),
        "views": num(s.get("views")),
        "likeCount": sum(1 for v in likes.values() if v),
        "likedByMe": bool(likes.get(uid)),
    }


async def load_short(short_id, token):
    check_id(short_id)
    short = await db_get(f"shorts/{short_id}", token)
    if not isinstance(short, dict):
        raise HTTPException(status_code=404, detail="Short not found")
    return short