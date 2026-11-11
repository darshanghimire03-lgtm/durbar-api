import os
import re
import base64
import secrets
import mimetypes

import httpx
from fastapi import FastAPI, UploadFile, File, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

IMGBB_KEY = os.environ["IMGBB_KEY"]
PUBLIC_BASE = os.environ.get("PUBLIC_BASE_URL", "https://durbar-plus2.vercel.app").rstrip("/")
UPLOAD_API_KEY = os.environ.get("UPLOAD_API_KEY", "")

VID = {
    "cloud": os.environ["CLOUDINARY_VIDEO_CLOUD_NAME"],
    "preset": os.environ["CLOUDINARY_VIDEO_PRESET"],
}
FILE = {
    "cloud": os.environ["CLOUDINARY_FILE_CLOUD_NAME"],
    "preset": os.environ["CLOUDINARY_FILE_PRESET"],
}

MAX_IMAGE = 32 * 1024 * 1024
MAX_VIDEO = 100 * 1024 * 1024
MAX_FILE = 10 * 1024 * 1024

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


def make_url(kind, src, ext):
    if not src.startswith("https://"):
        raise HTTPException(status_code=502, detail="Unexpected provider URL")
    path = src[len("https://"):]
    if not PATTERNS[kind].fullmatch(path):
        raise HTTPException(status_code=502, detail="Unexpected provider URL")
    token = enc(path)
    return f"{PUBLIC_BASE}/{kind}/{token}.{ext}", token


async def read_upload(file: UploadFile, limit: int):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > limit:
        raise HTTPException(status_code=413, detail="File too large")
    name = file.filename or "file"
    ext = os.path.splitext(name)[1].lstrip(".").lower()
    ext = "".join(ch for ch in ext if ch.isalnum())[:10]
    mime = file.content_type or mimetypes.guess_type(name)[0] or "application/octet-stream"
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
    url, token = make_url("img", r.json()["data"]["url"], ext)
    return {"url": url, "id": token, "name": name, "size": len(data)}


@app.post("/upload/video")
async def upload_video(file: UploadFile = File(...), x_api_key: str = Header(None)):
    check_key(x_api_key)
    data, name, ext, mime = await read_upload(file, MAX_VIDEO)
    if not mime.startswith("video/"):
        raise HTTPException(status_code=400, detail="Not a video")
    src = await cloudinary_upload(VID, "video", new_id(), data, name)
    url, token = make_url("vid", src, ext)
    return {"url": url, "id": token, "name": name, "size": len(data)}


@app.post("/upload/file")
async def upload_file(file: UploadFile = File(...), x_api_key: str = Header(None)):
    check_key(x_api_key)
    data, name, ext, mime = await read_upload(file, MAX_FILE)
    src = await cloudinary_upload(FILE, "raw", f"{new_id()}.{ext}", data, name)
    url, token = make_url("file", src, ext)
    return {"url": url, "id": token, "name": name, "size": len(data)}


async def serve(kind: str, filename: str, request: Request):
    if "." not in filename:
        raise HTTPException(status_code=404, detail="Not found")
    token, ext = filename.rsplit(".", 1)
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

    mime = mimetypes.guess_type(f"x.{ext.lower()}")[0] or up.headers.get("content-type") or "application/octet-stream"
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
        out["Content-Disposition"] = f'{"attachment" if unsafe else "inline"}; filename="{filename}"'

    async def gen():
        try:
            async for chunk in up.aiter_raw():
                yield chunk
        finally:
            await up.aclose()
            await client.aclose()

    return StreamingResponse(gen(), status_code=up.status_code, headers=out)


@app.get("/img/{filename}")
async def get_img(filename: str, request: Request):
    return await serve("img", filename, request)


@app.get("/vid/{filename}")
async def get_vid(filename: str, request: Request):
    return await serve("vid", filename, request)


@app.get("/file/{filename}")
async def get_file(filename: str, request: Request):
    return await serve("file", filename, request)