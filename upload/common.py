import os
import re
import mimetypes
import secrets
from urllib.parse import quote

import httpx
from fastapi import HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse


def need(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


PUBLIC_BASE = os.environ.get("PUBLIC_BASE_URL", "https://durbar-plus2.vercel.app").strip().rstrip("/")
UPLOAD_API_KEY = os.environ.get("UPLOAD_API_KEY", "").strip()

VID = {
    "cloud": need("CLOUDINARY_VIDEO_CLOUD_NAME"),
    "preset": need("CLOUDINARY_VIDEO_PRESET"),
}
FILE = {
    "cloud": need("CLOUDINARY_FILE_CLOUD_NAME"),
    "preset": need("CLOUDINARY_FILE_PRESET"),
}
IMG = {
    "cloud": os.environ.get("CLOUDINARY_IMAGE_CLOUD_NAME", "").strip() or FILE["cloud"],
    "preset": os.environ.get("CLOUDINARY_IMAGE_PRESET", "").strip() or FILE["preset"],
}

KINDS = {
    "img": {"cfg": IMG, "rtype": "image", "limit": 10 * 1024 * 1024},
    "vid": {"cfg": VID, "rtype": "video", "limit": 100 * 1024 * 1024},
    "file": {"cfg": FILE, "rtype": "raw", "limit": 10 * 1024 * 1024},
}

MAX_NAME = 150
MAX_TRIES = 1000
BAD_CHARS = set('?&#\\%<>')
UNSAFE_INLINE = {"text/html", "application/xhtml+xml", "image/svg+xml"}


def check_key(key):
    if UPLOAD_API_KEY and not secrets.compare_digest(key or "", UPLOAD_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")


def valid_name(name):
    if not name or name.startswith(".") or len(name) > MAX_NAME:
        return False
    return not any(ch in BAD_CHARS or not ch.isprintable() for ch in name)


def clean_name(raw):
    name = (raw or "").replace("\\", "/").split("/")[-1].strip()
    if not valid_name(name):
        raise HTTPException(status_code=400, detail="Invalid file name")
    return name


def split_name(name):
    stem, ext = os.path.splitext(name)
    return stem, ext.lstrip(".")


def numbered(name, n):
    if n == 0:
        return name
    stem, ext = os.path.splitext(name)
    suffix = f"-{n}"
    stem = stem[: MAX_NAME - len(ext) - len(suffix)]
    return f"{stem}{suffix}{ext}"


def public_id(kind, name):
    if KINDS[kind]["rtype"] == "raw":
        return name
    return split_name(name)[0]


def upstream_url(kind, name):
    k = KINDS[kind]
    if k["rtype"] == "raw":
        delivered = name
    else:
        stem, ext = split_name(name)
        delivered = f"{stem}.{ext.lower()}"
    return f"https://res.cloudinary.com/{k['cfg']['cloud']}/{k['rtype']}/upload/{quote(delivered, safe='')}"


def make_url(kind, name):
    return f"{PUBLIC_BASE}/{kind}/{quote(name, safe='')}"


async def exists(kind, name):
    async with httpx.AsyncClient(timeout=30, follow_redirects=False) as c:
        r = await c.get(upstream_url(kind, name), headers={"Range": "bytes=0-0", "Accept-Encoding": "identity"})
    return r.status_code in (200, 206)


async def prepare(kind, file: UploadFile):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > KINDS[kind]["limit"]:
        raise HTTPException(status_code=413, detail="File too large")
    name = clean_name(file.filename)
    mime = file.content_type or mimetypes.guess_type(name)[0] or "application/octet-stream"
    if KINDS[kind]["rtype"] != "raw" and not split_name(name)[1]:
        guessed = (mimetypes.guess_extension(mime) or "").lstrip(".")
        if not guessed:
            raise HTTPException(status_code=400, detail="File name needs an extension")
        name = f"{name}.{guessed}"
    return data, name, mime


def new_id():
    return secrets.token_urlsafe(9).replace("-", "a").replace("_", "b")


async def store(kind, data, name):
    k = KINDS[kind]
    for n in range(MAX_TRIES):
        candidate = numbered(name, n)
        if await exists(kind, candidate):
            continue
        pid = public_id(kind, candidate)
        async with httpx.AsyncClient(timeout=600) as c:
            r = await c.post(
                f"https://api.cloudinary.com/v1_1/{k['cfg']['cloud']}/{k['rtype']}/upload",
                data={"upload_preset": k["cfg"]["preset"], "public_id": pid},
                files={"file": (candidate, data)},
            )
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail="Cloudinary upload failed")
        body = r.json()
        if body.get("existing"):
            continue
        if body.get("public_id") != pid:
            raise HTTPException(status_code=502, detail="Cloudinary preset changed the file name")
        return make_url(kind, candidate)
    raise HTTPException(status_code=409, detail="Too many files with this name")


async def serve(kind: str, name: str, request: Request):
    if not valid_name(name):
        raise HTTPException(status_code=404, detail="Not found")
    if KINDS[kind]["rtype"] != "raw" and not split_name(name)[1]:
        raise HTTPException(status_code=404, detail="Not found")

    headers = {"Accept-Encoding": "identity"}
    rng = request.headers.get("range")
    if rng:
        headers["Range"] = rng

    client = httpx.AsyncClient(timeout=None, follow_redirects=False)
    up = await client.send(client.build_request("GET", upstream_url(kind, name), headers=headers), stream=True)
    if up.status_code >= 300:
        await up.aclose()
        await client.aclose()
        raise HTTPException(status_code=404, detail="Not found")

    mime = mimetypes.guess_type(name)[0] or up.headers.get("content-type") or "application/octet-stream"
    unsafe = mime in UNSAFE_INLINE
    if unsafe:
        mime = "application/octet-stream"

    out = {
        "Content-Type": mime,
        "Accept-Ranges": "bytes",
        "Cache-Control": "public, max-age=31536000",
        "Access-Control-Allow-Origin": "*",
        "X-Content-Type-Options": "nosniff",
    }
    if up.headers.get("content-length"):
        out["Content-Length"] = up.headers["content-length"]
    if up.headers.get("content-range"):
        out["Content-Range"] = up.headers["content-range"]
    if kind == "file":
        disposition = "attachment" if unsafe else "inline"
        fallback = re.sub(r"[^A-Za-z0-9._-]", "_", name)
        out["Content-Disposition"] = f"{disposition}; filename=\"{fallback}\"; filename*=UTF-8''{quote(name, safe='')}"

    async def gen():
        try:
            async for chunk in up.aiter_raw():
                yield chunk
        finally:
            await up.aclose()
            await client.aclose()

    return StreamingResponse(gen(), status_code=up.status_code, headers=out)