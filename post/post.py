import secrets
import time
from typing import List, Optional

from fastapi import APIRouter, Header
from pydantic import BaseModel

from auth.common import bad
from post.common import (
    MAX_IMAGES,
    MAX_TEXT,
    PRIVACY,
    SECTIONS,
    check_image,
    db_put,
    sign_in,
    view_post,
)

router = APIRouter()


class PostBody(BaseModel):
    text: Optional[str] = ""
    imageUrl: Optional[str] = ""
    imageUrls: Optional[List[str]] = None
    privacy: Optional[str] = "everyone"
    section: Optional[str] = None


def collect_images(single, many):
    urls = []
    for raw in ([single] if single else []) + list(many or []):
        url = check_image(raw)
        if url and url not in urls:
            urls.append(url)
    if len(urls) > MAX_IMAGES:
        bad(f"A post can have at most {MAX_IMAGES} images")
    return urls


@router.post("")
async def create_post(body: PostBody, x_email: str = Header(None), x_password: str = Header(None)):
    uid, token, user = await sign_in(x_email, x_password)

    text = str(body.text or "").strip()
    if len(text) > MAX_TEXT:
        bad(f"text must be at most {MAX_TEXT} characters")
    images = collect_images(body.imageUrl, body.imageUrls)
    if not text and not images:
        bad("A post needs text or at least one image")

    privacy = str(body.privacy or "everyone").strip().lower()
    if privacy not in PRIVACY:
        bad("privacy must be everyone or section")

    section = ""
    if privacy == "section":
        if str(user.get("role", "")).lower() == "student":
            section = str(user.get("section", ""))
        else:
            section = str(body.section or "").strip().upper()
        if section not in SECTIONS:
            bad("section must be A or B")

    post_id = f"p{int(time.time() * 1000)}{secrets.token_hex(2)}"
    post = {
        "postId": post_id,
        "authorUid": uid,
        "authorEmail": user.get("email", ""),
        "text": text,
        "imageUrl": images[0] if images else "",
        "createdAt": int(time.time() * 1000),
        "privacy": privacy,
        "section": section,
    }
    if images:
        post["imageUrls"] = images

    await db_put(f"posts/{post_id}", token, post)
    return view_post(post_id, post, uid)