from fastapi import APIRouter, Header

from post.common import as_dict, db_delete, db_get, db_put, sign_in
from shorts.common import load_short

router = APIRouter()


async def like_count(short_id, token):
    likes = as_dict(await db_get(f"shorts/{short_id}/likes", token))
    return sum(1 for v in likes.values() if v)


@router.put("/{short_id}/like")
async def like(short_id: str, x_email: str = Header(None), x_password: str = Header(None)):
    uid, token, user = await sign_in(x_email, x_password)
    await load_short(short_id, token)
    await db_put(f"shorts/{short_id}/likes/{uid}", token, True)
    return {"shortId": short_id, "liked": True, "likeCount": await like_count(short_id, token)}


@router.delete("/{short_id}/like")
async def unlike(short_id: str, x_email: str = Header(None), x_password: str = Header(None)):
    uid, token, user = await sign_in(x_email, x_password)
    await load_short(short_id, token)
    await db_delete(f"shorts/{short_id}/likes/{uid}", token)
    return {"shortId": short_id, "liked": False, "likeCount": await like_count(short_id, token)}