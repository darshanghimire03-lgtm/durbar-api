from fastapi import APIRouter, Header, HTTPException

from post.common import as_dict, check_id, db_delete, db_get, db_put, load_post, sign_in

router = APIRouter()


async def like_count(path, token):
    likes = as_dict(await db_get(f"{path}/likes", token))
    return sum(1 for v in likes.values() if v)


async def load_comment(post_id, comment_id, token, user):
    await load_post(post_id, token, user)
    check_id(comment_id)
    comment = await db_get(f"posts/{post_id}/comments/{comment_id}", token)
    if not isinstance(comment, dict):
        raise HTTPException(status_code=404, detail="Comment not found")
    return comment


@router.put("/{post_id}/like")
async def like(post_id: str, x_email: str = Header(None), x_password: str = Header(None)):
    uid, token, user = await sign_in(x_email, x_password)
    await load_post(post_id, token, user)
    await db_put(f"posts/{post_id}/likes/{uid}", token, True)
    return {"postId": post_id, "liked": True, "likeCount": await like_count(f"posts/{post_id}", token)}


@router.delete("/{post_id}/like")
async def unlike(post_id: str, x_email: str = Header(None), x_password: str = Header(None)):
    uid, token, user = await sign_in(x_email, x_password)
    await load_post(post_id, token, user)
    await db_delete(f"posts/{post_id}/likes/{uid}", token)
    return {"postId": post_id, "liked": False, "likeCount": await like_count(f"posts/{post_id}", token)}


@router.put("/{post_id}/comments/{comment_id}/like")
async def like_comment(
    post_id: str,
    comment_id: str,
    x_email: str = Header(None),
    x_password: str = Header(None),
):
    uid, token, user = await sign_in(x_email, x_password)
    await load_comment(post_id, comment_id, token, user)
    path = f"posts/{post_id}/comments/{comment_id}"
    await db_put(f"{path}/likes/{uid}", token, True)
    return {
        "postId": post_id,
        "commentId": comment_id,
        "liked": True,
        "likeCount": await like_count(path, token),
    }


@router.delete("/{post_id}/comments/{comment_id}/like")
async def unlike_comment(
    post_id: str,
    comment_id: str,
    x_email: str = Header(None),
    x_password: str = Header(None),
):
    uid, token, user = await sign_in(x_email, x_password)
    await load_comment(post_id, comment_id, token, user)
    path = f"posts/{post_id}/comments/{comment_id}"
    await db_delete(f"{path}/likes/{uid}", token)
    return {
        "postId": post_id,
        "commentId": comment_id,
        "liked": False,
        "likeCount": await like_count(path, token),
    }