import re

import httpx
from fastapi import HTTPException

from auth.common import DB_URL, PUBLIC_BASE, bad, db_read, fb_call

MAX_TEXT = 2000
MAX_COMMENT = 1000
MAX_IMAGES = 10
MAX_COMMENTS_LIST = 200
PRIVACY = ("everyone", "section")
SECTIONS = ("A", "B")
BATCH = 50
MAX_BATCHES = 6
PAGE_MAX = 30
ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


def num(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def as_dict(value):
    if isinstance(value, list):
        return {str(i): v for i, v in enumerate(value) if v is not None}
    return value if isinstance(value, dict) else {}


def as_list(value):
    if isinstance(value, list):
        return [v for v in value if v is not None]
    if isinstance(value, dict):
        return [v for _, v in sorted(value.items(), key=lambda kv: num(kv[0]))]
    return []


def check_id(value):
    if not ID_PATTERN.fullmatch(str(value or "")):
        raise HTTPException(status_code=404, detail="Not found")
    return value


def check_image(raw):
    url = str(raw or "").strip()
    if not url:
        return ""
    if len(url) > 500 or not url.startswith(f"{PUBLIC_BASE}/img/"):
        bad("Image URLs must come from this server's image upload")
    return url


async def sign_in(email, password):
    email = str(email or "").strip().lower()
    if not email or not password:
        raise HTTPException(status_code=401, detail="Send X-Email and X-Password headers")
    signed = await fb_call(
        "signInWithPassword",
        {"email": email, "password": password, "returnSecureToken": True},
    )
    uid = signed["localId"]
    token = signed["idToken"]
    user = await db_read(uid, token)
    if user is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return uid, token, user


def guard(r):
    if r.status_code in (401, 403):
        raise HTTPException(status_code=403, detail="Database rules do not allow this action")
    if r.status_code != 200:
        if "Index not defined" in r.text:
            raise HTTPException(status_code=502, detail="Add .indexOn createdAt to the posts database rules")
        raise HTTPException(status_code=502, detail="Database request failed")


async def db_get(path, token, params=None):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{DB_URL}/{path}.json", params={"auth": token, **(params or {})})
    guard(r)
    return r.json()


async def db_put(path, token, body):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.put(f"{DB_URL}/{path}.json", params={"auth": token}, json=body)
    guard(r)


async def db_delete(path, token):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.delete(f"{DB_URL}/{path}.json", params={"auth": token})
    guard(r)


def can_see(user, post):
    if post.get("privacy") != "section":
        return True
    if str(user.get("role", "")).lower() == "professor":
        return True
    if post.get("authorUid") == user.get("uid"):
        return True
    section = str(user.get("section", ""))
    return section != "" and section == str(post.get("section", ""))


def view_comment(comment_id, c, uid=""):
    likes = as_dict(c.get("likes"))
    return {
        "commentId": comment_id,
        "uid": c.get("uid", ""),
        "text": c.get("text", ""),
        "imageUrl": c.get("imageUrl", ""),
        "createdAt": num(c.get("createdAt")),
        "likeCount": sum(1 for v in likes.values() if v),
        "likedByMe": bool(likes.get(uid)),
    }


def comment_list(node, uid=""):
    items = [view_comment(k, v, uid) for k, v in as_dict(node).items() if isinstance(v, dict)]
    items.sort(key=lambda c: c["createdAt"])
    return items[:MAX_COMMENTS_LIST]


def view_post(post_id, p, uid):
    images = as_list(p.get("imageUrls"))
    if not images and p.get("imageUrl"):
        images = [p["imageUrl"]]
    likes = as_dict(p.get("likes"))
    return {
        "postId": post_id,
        "authorUid": p.get("authorUid", ""),
        "authorEmail": p.get("authorEmail", ""),
        "text": p.get("text", ""),
        "imageUrl": images[0] if images else "",
        "imageUrls": images,
        "createdAt": num(p.get("createdAt")),
        "privacy": p.get("privacy", "everyone"),
        "section": p.get("section", ""),
        "likeCount": sum(1 for v in likes.values() if v),
        "likedByMe": bool(likes.get(uid)),
        "commentCount": len(as_dict(p.get("comments"))),
    }


async def load_post(post_id, token, user):
    check_id(post_id)
    post = await db_get(f"posts/{post_id}", token)
    if not isinstance(post, dict) or not can_see(user, post):
        raise HTTPException(status_code=404, detail="Post not found")
    return post