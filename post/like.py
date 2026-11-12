from fastapi import APIRouter, Header

from post.common import as_dict, db_delete, db_get, db_put, load_post, sign_in

router = APIRouter()


async def like_count(post_id, token):
    likes = as_dict(await db_get(f"posts/{post_id}/likes", token))
    return sum(1 for v in likes.values() if v)


@router.put("/{post_id}/like")
async def like(post_id: str, x_email: str = Header(None), x_password: str = Header(None)):
    uid, token, user = await sign_in(x_email, x_password)
    await load_post(post_id, token, user)
    await db_put(f"posts/{post_id}/likes/{uid}", token, True)
    return {"postId": post_id, "liked": True, "likeCount": await like_count(post_id, token)}


@router.delete("/{post_id}/like")
async def unlike(post_id: str, x_email: str = Header(None), x_password: str = Header(None)):
    uid, token, user = await sign_in(x_email, x_password)
    await load_post(post_id, token, user)
    await db_delete(f"posts/{post_id}/likes/{uid}", token)
    return {"postId": post_id, "liked": False, "likeCount": await like_count(post_id, token)}