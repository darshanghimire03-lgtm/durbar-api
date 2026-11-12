import secrets
import time
from typing import Optional

from fastapi import APIRouter, Header
from pydantic import BaseModel

from auth.common import bad
from post.common import MAX_COMMENT, check_image, db_put, load_post, sign_in, view_comment

router = APIRouter()


class CommentBody(BaseModel):
    text: Optional[str] = ""
    imageUrl: Optional[str] = ""


@router.post("/{post_id}/comments")
async def create_comment(
    post_id: str,
    body: CommentBody,
    x_email: str = Header(None),
    x_password: str = Header(None),
):
    uid, token, user = await sign_in(x_email, x_password)
    await load_post(post_id, token, user)

    text = str(body.text or "").strip()
    if len(text) > MAX_COMMENT:
        bad(f"text must be at most {MAX_COMMENT} characters")
    image = check_image(body.imageUrl)
    if not text and not image:
        bad("A comment needs text or an image")

    comment_id = f"c{int(time.time() * 1000)}{secrets.token_hex(2)}"
    comment = {
        "uid": uid,
        "text": text,
        "createdAt": int(time.time() * 1000),
        "imageUrl": image,
    }
    await db_put(f"posts/{post_id}/comments/{comment_id}", token, comment)
    return view_comment(comment_id, comment)