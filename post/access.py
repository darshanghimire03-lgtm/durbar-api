from typing import Optional

from fastapi import APIRouter, Header

from post.common import (
    BATCH,
    MAX_BATCHES,
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
    end = before - 1 if before else None

    items = []
    next_before = None
    for _ in range(MAX_BATCHES):
        params = {"orderBy": '"createdAt"', "limitToLast": BATCH}
        if end is not None:
            params["endAt"] = end
        raw = as_dict(await db_get("posts", token, params))
        batch = [(k, v) for k, v in raw.items() if isinstance(v, dict)]
        batch.sort(key=lambda kv: num(kv[1].get("createdAt")), reverse=True)
        if not batch:
            next_before = None
            break

        done = False
        for post_id, post in batch:
            if can_see(user, post):
                items.append(view_post(post_id, post, uid))
            next_before = num(post.get("createdAt"))
            if len(items) >= limit:
                done = True
                break
        if done:
            break
        if len(raw) < BATCH:
            next_before = None
            break
        end = next_before - 1

    return {"posts": items, "nextBefore": next_before}


@router.get("/{post_id}")
async def get_post(post_id: str, x_email: str = Header(None), x_password: str = Header(None)):
    uid, token, user = await sign_in(x_email, x_password)
    post = await load_post(post_id, token, user)
    result = view_post(post_id, post, uid)
    result["comments"] = comment_list(post.get("comments"))
    return result


@router.get("/{post_id}/comments")
async def get_comments(post_id: str, x_email: str = Header(None), x_password: str = Header(None)):
    uid, token, user = await sign_in(x_email, x_password)
    post = await load_post(post_id, token, user)
    return {"postId": post_id, "comments": comment_list(post.get("comments"))}