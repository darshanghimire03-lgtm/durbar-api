from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .common import bad, db_read, fb_call

router = APIRouter()


class LoginBody(BaseModel):
    email: str
    password: str


@router.post("/login")
async def login(body: LoginBody):
    email = str(body.email or "").strip().lower()
    if not email or not body.password:
        bad("Email and password are required")

    signed = await fb_call(
        "signInWithPassword",
        {"email": email, "password": body.password, "returnSecureToken": True},
    )
    uid = signed["localId"]
    token = signed["idToken"]

    user = await db_read(uid, token)
    if user is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    return user