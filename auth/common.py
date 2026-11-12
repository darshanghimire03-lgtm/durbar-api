import os

import httpx
from fastapi import HTTPException


def need(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


FB_KEY = need("FIREBASE_API_KEY")
DB_URL = need("FIREBASE_DB_URL").rstrip("/")
PUBLIC_BASE = os.environ.get("PUBLIC_BASE_URL", "https://durbar-plus2.vercel.app").strip().rstrip("/")

FB_AUTH = "https://identitytoolkit.googleapis.com/v1/accounts"

FB_ERRORS = {
    "EMAIL_EXISTS": (409, "Email already registered"),
    "WEAK_PASSWORD": (400, "Password must be at least 6 characters"),
    "INVALID_EMAIL": (400, "Invalid email"),
    "EMAIL_NOT_FOUND": (401, "Wrong email or password"),
    "INVALID_PASSWORD": (401, "Wrong email or password"),
    "INVALID_LOGIN_CREDENTIALS": (401, "Wrong email or password"),
    "USER_DISABLED": (403, "Account disabled"),
    "TOO_MANY_ATTEMPTS_TRY_LATER": (429, "Too many attempts, try later"),
    "OPERATION_NOT_ALLOWED": (403, "Email/password sign-in is not enabled in Firebase"),
}


def bad(detail):
    raise HTTPException(status_code=400, detail=detail)


async def fb_call(action, payload):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{FB_AUTH}:{action}", params={"key": FB_KEY}, json=payload)
    if r.status_code != 200:
        try:
            message = r.json().get("error", {}).get("message", "")
        except ValueError:
            message = ""
        code = message.split(" ")[0]
        status, text = FB_ERRORS.get(code, (502, "Firebase request failed"))
        raise HTTPException(status_code=status, detail=text)
    return r.json()


async def db_write(uid, token, profile):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.put(f"{DB_URL}/users/{uid}.json", params={"auth": token}, json=profile)
    return r.status_code == 200


async def db_read(uid, token):
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{DB_URL}/users/{uid}.json", params={"auth": token})
    if r.status_code != 200:
        return None
    data = r.json()
    return data if isinstance(data, dict) else None