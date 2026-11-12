from typing import Optional

from fastapi import APIRouter, Header

from post.common import (
    PAGE_MAX,
    as_dict,
    can_see,
    comment_list,
    db_get,
    load_post,
    num,
    sign_in,
    view_post,
)

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

    raw = as_dict(await db_get("posts", token))
    posts = [(k, v) for k, v in raw.items() if isinstance(v, dict) and can_see(user, v)]
    posts.sort(key=lambda kv: num(kv[1].get("createdAt")), reverse=True)

    if before:
        posts = [kv for kv in posts if num(kv[1].get("createdAt")) < before]

    page = posts[:limit]
    next_before = num(page[-1][1].get("createdAt")) if len(posts) > limit else None

    return {"posts": [view_post(k, v, uid) for k, v in page], "nextBefore": next_before}


@router.get("/{post_id}")
async def get_post(post_id: str, x_email: str = Header(None), x_password: str = Header(None)):
    uid, token, user = await sign_in(x_email, x_password)
    post = await load_post(post_id, token, user)
    result = view_post(post_id, post, uid)
    result["comments"] = comment_list(post.get("comments"), uid)
    return result


@router.get("/{post_id}/comments")
async def get_comments(post_id: str, x_email: str = Header(None), x_password: str = Header(None)):
    uid, token, user = await sign_in(x_email, x_password)
    post = await load_post(post_id, token, user)
    return {"postId": post_id, "comments": comment_list(post.get("comments"), uid)}