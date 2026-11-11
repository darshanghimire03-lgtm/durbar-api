import os
import time
import secrets
import base64
import mimetypes
from urllib.parse import quote

import httpx
from fastapi import FastAPI, UploadFile, File, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

FB_KEY = os.environ["FIREBASE_API_KEY"]
DB = os.environ["FIREBASE_DB_URL"].rstrip("/")
IMGBB_KEY = os.environ["IMGBB_KEY"]
PUBLIC_BASE = os.environ.get("PUBLIC_BASE_URL", "https://durbar-plus2.vercel.app").rstrip("/")

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

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"],
)


class RegisterBody(BaseModel):
    email: str
    password: str
    name: str = ""


class LoginBody(BaseModel):
    email: str
    password: str


class RefreshBody(BaseModel):
    refreshToken: str


def fb_error(r):
    try:
        m = r.json()["error"]["message"]
    except Exception:
        m = "REQUEST_FAILED"
    raise HTTPException(status_code=400, detail=m)


async def get_user(authorization):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization[7:].strip()
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={FB_KEY}",
            json={"idToken": token},
        )
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid token")
    return r.json()["users"][0]["localId"], token


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


async def save_media(kind, mid, ext, url, uid, token, name, mime, size):
    doc = {
        "t": kind,
        "u": url,
        "o": uid,
        "n": name,
        "e": ext,
        "m": mime,
        "s": size,
        "c": int(time.time() * 1000),
    }
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.put(f"{DB}/media/{mid}.json", params={"auth": token}, json=doc)
    if r.status_code != 200:
        raise HTTPException(status_code=500, detail="Database write failed")


async def cloudinary_upload(cfg, resource_type, public_id, data, name):
    async with httpx.AsyncClient(timeout=600) as c:
        r = await c.post(
            f"https://api.cloudinary.com/v1_1/{cfg['cloud']}/{resource_type}/upload",
            data={
                "upload_preset": cfg["preset"],
                "public_id": public_id,
            },
            files={"file": (name, data)},
        )
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Cloudinary upload failed")
    return r.json()["secure_url"]


@app.get("/")
async def root():
    return {"ok": True}


@app.post("/auth/register")
async def register(body: RegisterBody):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FB_KEY}",
            json={"email": body.email, "password": body.password, "returnSecureToken": True},
        )
        if r.status_code != 200:
            fb_error(r)
        j = r.json()
        uid = j["localId"]
        token = j["idToken"]
        profile = {
            "name": body.name,
            "email": body.email,
            "createdAt": int(time.time() * 1000),
        }
        w = await c.put(f"{DB}/users/{uid}.json", params={"auth": token}, json=profile)
        if w.status_code != 200:
            raise HTTPException(status_code=500, detail="Profile save failed")
    return {
        "uid": uid,
        "idToken": token,
        "refreshToken": j["refreshToken"],
        "expiresIn": j["expiresIn"],
        "profile": profile,
    }


@app.post("/auth/login")
async def login(body: LoginBody):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FB_KEY}",
            json={"email": body.email, "password": body.password, "returnSecureToken": True},
        )
        if r.status_code != 200:
            fb_error(r)
        j = r.json()
        uid = j["localId"]
        p = await c.get(f"{DB}/users/{uid}.json", params={"auth": j["idToken"]})
        profile = p.json() if p.status_code == 200 else None
    return {
        "uid": uid,
        "idToken": j["idToken"],
        "refreshToken": j["refreshToken"],
        "expiresIn": j["expiresIn"],
        "profile": profile,
    }


@app.post("/auth/refresh")
async def refresh(body: RefreshBody):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            f"https://securetoken.googleapis.com/v1/token?key={FB_KEY}",
            data={"grant_type": "refresh_token", "refresh_token": body.refreshToken},
        )
    if r.status_code != 200:
        fb_error(r)
    j = r.json()
    return {
        "uid": j["user_id"],
        "idToken": j["id_token"],
        "refreshToken": j["refresh_token"],
        "expiresIn": j["expires_in"],
    }


@app.post("/upload/image")
async def upload_image(file: UploadFile = File(...), authorization: str = Header(None)):
    uid, token = await get_user(authorization)
    data, name, ext, mime = await read_upload(file, MAX_IMAGE)
    if not mime.startswith("image/"):
        raise HTTPException(status_code=400, detail="Not an image")
    mid = secrets.token_urlsafe(9).replace("-", "a").replace("_", "b")
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(
            "https://api.imgbb.com/1/upload",
            params={"key": IMGBB_KEY},
            data={"image": base64.b64encode(data).decode(), "name": mid},
        )
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="imgbb upload failed")
    src = r.json()["data"]["url"]
    await save_media("img", mid, ext, src, uid, token, name, mime, len(data))
    return {"url": f"{PUBLIC_BASE}/img/{mid}.{ext}", "id": mid, "name": name, "size": len(data)}


@app.post("/upload/video")
async def upload_video(file: UploadFile = File(...), authorization: str = Header(None)):
    uid, token = await get_user(authorization)
    data, name, ext, mime = await read_upload(file, MAX_VIDEO)
    if not mime.startswith("video/"):
        raise HTTPException(status_code=400, detail="Not a video")
    mid = secrets.token_urlsafe(9).replace("-", "a").replace("_", "b")
    src = await cloudinary_upload(VID, "video", mid, data, name)
    await save_media("vid", mid, ext, src, uid, token, name, mime, len(data))
    return {"url": f"{PUBLIC_BASE}/vid/{mid}.{ext}", "id": mid, "name": name, "size": len(data)}


@app.post("/upload/file")
async def upload_file(file: UploadFile = File(...), authorization: str = Header(None)):
    uid, token = await get_user(authorization)
    data, name, ext, mime = await read_upload(file, MAX_FILE)
    mid = secrets.token_urlsafe(9).replace("-", "a").replace("_", "b")
    src = await cloudinary_upload(FILE, "raw", f"{mid}.{ext}", data, name)
    await save_media("file", mid, ext, src, uid, token, name, mime, len(data))
    return {"url": f"{PUBLIC_BASE}/file/{mid}.{ext}", "id": mid, "name": name, "size": len(data)}


async def serve(kind: str, filename: str, request: Request):
    if "." not in filename:
        raise HTTPException(status_code=404, detail="Not found")
    mid, ext = filename.rsplit(".", 1)
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{DB}/media/{mid}.json")
    doc = r.json() if r.status_code == 200 else None
    if not doc or doc.get("t") != kind or doc.get("e") != ext.lower():
        raise HTTPException(status_code=404, detail="Not found")

    headers = {"Accept-Encoding": "identity"}
    rng = request.headers.get("range")
    if rng:
        headers["Range"] = rng

    client = httpx.AsyncClient(timeout=None, follow_redirects=True)
    up = await client.send(client.build_request("GET", doc["u"], headers=headers), stream=True)
    if up.status_code >= 400:
        await up.aclose()
        await client.aclose()
        raise HTTPException(status_code=404, detail="Not found")

    out = {
        "Content-Type": doc.get("m") or "application/octet-stream",
        "Accept-Ranges": "bytes",
        "Cache-Control": "public, max-age=31536000, immutable",
        "Access-Control-Allow-Origin": "*",
    }
    if up.headers.get("content-length"):
        out["Content-Length"] = up.headers["content-length"]
    if up.headers.get("content-range"):
        out["Content-Range"] = up.headers["content-range"]
    if kind == "file":
        out["Content-Disposition"] = "inline; filename*=UTF-8''" + quote(doc.get("n") or filename)

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