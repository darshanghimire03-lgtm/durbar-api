import os
import re
import base64
import secrets
import mimetypes
from urllib.parse import quote

import httpx
from fastapi import FastAPI, UploadFile, File, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware


def need(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


IMGBB_KEY = need("IMGBB_KEY")
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

MAX_IMAGE = 32 * 1024 * 1024
MAX_VIDEO = 100 * 1024 * 1024
MAX_FILE = 10 * 1024 * 1024
MAX_NAME = 150

PATTERNS = {
    "img": re.compile(r"i\.ibb\.co(?:\.com)?/[A-Za-z0-9]+/[A-Za-z0-9._-]+"),
    "vid": re.compile(
        r"res\.cloudinary\.com/" + re.escape(VID["cloud"]) + r"/video/upload/(?:v\d+/)?[A-Za-z0-9]+\.[A-Za-z0-9]+"
    ),
    "file": re.compile(
        r"res\.cloudinary\.com/" + re.escape(FILE["cloud"]) + r"/raw/upload/(?:v\d+/)?[A-Za-z0-9]+\.[A-Za-z0-9]+"
    ),
}

UNSAFE_INLINE = {"text/html", "application/xhtml+xml", "image/svg+xml"}

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"],
)


def check_key(key):
    if UPLOAD_API_KEY and not secrets.compare_digest(key or "", UPLOAD_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")


def enc(path):
    return base64.urlsafe_b64encode(path.encode()).decode().rstrip("=")


def dec(token):
    try:
        return base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)).decode()
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")


def clean_name(raw):
    name = (raw or "").replace("\\", "/").split("/")[-1]
    name = "".join(ch for ch in name if ch.isprintable()).strip()
    if not name:
        return "file"
    if len(name) > MAX_NAME:
        stem, ext = os.path.splitext(name)
        ext = ext[:20]
        name = stem[: MAX_NAME - len(ext)] + ext
    return name


def make_url(kind, src, name):
    if not src.startswith("https://"):
        raise HTTPException(status_code=502, detail="Unexpected provider URL")
    path = src[len("https://"):]
    if not PATTERNS[kind].fullmatch(path):
        raise HTTPException(status_code=502, detail="Unexpected provider URL")
    return f"{PUBLIC_BASE}/{kind}/{enc(path)}/{quote(name, safe='')}"


async def read_upload(file: UploadFile, limit: int):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > limit:
        raise HTTPException(status_code=413, detail="File too large")
    name = clean_name(file.filename)
    mime = file.content_type or mimetypes.guess_type(name)[0] or "application/octet-stream"
    ext = os.path.splitext(name)[1].lstrip(".").lower()
    ext = "".join(ch for ch in ext if ch.isalnum())[:10]
    if not ext:
        ext = (mimetypes.guess_extension(mime) or ".bin").lstrip(".")
    return data, name, ext, mime


async def cloudinary_upload(cfg, resource_type, public_id, data, name):
    async with httpx.AsyncClient(timeout=600) as c:
        r = await c.post(
            f"https://api.cloudinary.com/v1_1/{cfg['cloud']}/{resource_type}/upload",
            data={"upload_preset": cfg["preset"], "public_id": public_id},
            files={"file": (name, data)},
        )
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Cloudinary upload failed")
    return r.json()["secure_url"]


def new_id():
    return secrets.token_urlsafe(9).replace("-", "a").replace("_", "b")


@app.get("/")
async def root():
    return {"ok": True}


@app.post("/upload/image")
async def upload_image(file: UploadFile = File(...), x_api_key: str = Header(None)):
    check_key(x_api_key)
    data, name, ext, mime = await read_upload(file, MAX_IMAGE)
    if not mime.startswith("image/"):
        raise HTTPException(status_code=400, detail="Not an image")
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(
            "https://api.imgbb.com/1/upload",
            params={"key": IMGBB_KEY},
            data={"image": base64.b64encode(data).decode(), "name": new_id()},
        )
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="imgbb upload failed")
    return {"url": make_url("img", r.json()["data"]["url"], name)}


@app.post("/upload/video")
async def upload_video(file: UploadFile = File(...), x_api_key: str = Header(None)):
    check_key(x_api_key)
    data, name, ext, mime = await read_upload(file, MAX_VIDEO)
    if not mime.startswith("video/"):
        raise HTTPException(status_code=400, detail="Not a video")
    src = await cloudinary_upload(VID, "video", new_id(), data, name)
    return {"url": make_url("vid", src, name)}


@app.post("/upload/file")
async def upload_file(file: UploadFile = File(...), x_api_key: str = Header(None)):
    check_key(x_api_key)
    data, name, ext, mime = await read_upload(file, MAX_FILE)
    src = await cloudinary_upload(FILE, "raw", f"{new_id()}.{ext}", data, name)
    return {"url": make_url("file", src, name)}


async def serve(kind: str, token: str, name: str, request: Request):
    path = dec(token)
    if not PATTERNS[kind].fullmatch(path):
        raise HTTPException(status_code=404, detail="Not found")

    headers = {"Accept-Encoding": "identity"}
    rng = request.headers.get("range")
    if rng:
        headers["Range"] = rng

    client = httpx.AsyncClient(timeout=None, follow_redirects=False)
    up = await client.send(client.build_request("GET", "https://" + path, headers=headers), stream=True)
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
        "Cache-Control": "public, max-age=31536000, immutable",
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


@app.get("/img/{token}/{name}")
async def get_img(token: str, name: str, request: Request):
    return await serve("img", token, name, request)


@app.get("/vid/{token}/{name}")
async def get_vid(token: str, name: str, request: Request):
    return await serve("vid", token, name, request)


@app.get("/file/{token}/{name}")
async def get_file(token: str, name: str, request: Request):
    return await serve("file", token, name, request)


@app.get("/img/{legacy}")
async def get_img_legacy(legacy: str, request: Request):
    return await serve("img", legacy.rsplit(".", 1)[0], legacy, request)


@app.get("/vid/{legacy}")
async def get_vid_legacy(legacy: str, request: Request):
    return await serve("vid", legacy.rsplit(".", 1)[0], legacy, request)


@app.get("/file/{legacy}")
async def get_file_legacy(legacy: str, request: Request):
    return await serve("file", legacy.rsplit(".", 1)[0], legacy, request)