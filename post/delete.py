from fastapi import APIRouter, Header, HTTPException

from post.common import check_id, db_delete, db_get, load_post, sign_in

router = APIRouter()


@router.delete("/{post_id}")
async def delete_post(post_id: str, x_email: str = Header(None), x_password: str = Header(None)):
    uid, token, user = await sign_in(x_email, x_password)
    post = await load_post(post_id, token, user)
    if post.get("authorUid") != uid:
        raise HTTPException(status_code=403, detail="Only the author can delete this post")
    await db_delete(f"posts/{post_id}", token)
    return {"postId": post_id, "deleted": True}


@router.delete("/{post_id}/comments/{comment_id}")
async def delete_comment(
    post_id: str,
    comment_id: str,
    x_email: str = Header(None),
    x_password: str = Header(None),
):
    uid, token, user = await sign_in(x_email, x_password)
    post = await load_post(post_id, token, user)
    check_id(comment_id)

    comment = await db_get(f"posts/{post_id}/comments/{comment_id}", token)
    if not isinstance(comment, dict):
        raise HTTPException(status_code=404, detail="Comment not found")

    if comment.get("uid") != uid and post.get("authorUid") != uid:
        raise HTTPException(
            status_code=403,
            detail="Only the comment author or the post author can delete this comment",
        )

    await db_delete(f"posts/{post_id}/comments/{comment_id}", token)
    return {"postId": post_id, "commentId": comment_id, "deleted": True}