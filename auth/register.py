import re
import time
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from auth.common import PUBLIC_BASE, bad, db_write, fb_call

router = APIRouter()

GMAIL = re.compile(r"^[a-z0-9._%+\-]+@gmail\.com$")
ROLES = {"student", "professor"}
GENDERS = {"male", "female", "other"}
CLASS_LEVELS = {"11", "12"}
SECTIONS = {"A", "B"}


class RegisterBody(BaseModel):
    role: str
    email: str
    password: str
    fullName: str
    phone: str
    gender: str
    profileImageUrl: Optional[str] = ""
    assignedSubject: Optional[Any] = None
    classLevel: Optional[Any] = None
    section: Optional[Any] = None


def clean_text(value, label, low, high):
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not low <= len(text) <= high:
        bad(f"{label} must be {low}-{high} characters")
    return text


def normalize_email(raw):
    email = str(raw or "").strip().lower()
    if not GMAIL.fullmatch(email):
        bad("Only @gmail.com emails are accepted")
    return email


def normalize_phone(raw):
    p = re.sub(r"[\s\-()]", "", str(raw or ""))
    if p.startswith("+"):
        if not p.startswith("+977"):
            bad("Only Nepal (+977) phone numbers are accepted")
        rest = p[4:]
    elif p.startswith("977") and len(p) > 10:
        rest = p[3:]
    else:
        rest = p
    if not rest.isdigit() or not 7 <= len(rest) <= 10:
        bad("Invalid phone number")
    return "+977" + rest


def check_profile_image(raw):
    url = str(raw or "").strip()
    if not url:
        return ""
    if len(url) > 500 or not url.startswith(f"{PUBLIC_BASE}/img/"):
        bad("profileImageUrl must be an image URL from this server")
    return url


def build_profile(body: RegisterBody):
    role = str(body.role or "").strip().lower()
    if role not in ROLES:
        bad("role must be student or professor")

    gender = str(body.gender or "").strip().lower()
    if gender not in GENDERS:
        bad("gender must be male, female or other")

    if len(body.password or "") < 6:
        bad("Password must be at least 6 characters")

    profile = {
        "email": normalize_email(body.email),
        "fullName": clean_text(body.fullName, "fullName", 2, 80),
        "profileImageUrl": check_profile_image(body.profileImageUrl),
        "role": role,
        "phone": normalize_phone(body.phone),
        "gender": gender,
    }

    if role == "professor":
        profile["assignedSubject"] = clean_text(body.assignedSubject, "assignedSubject", 1, 60)
    else:
        level = str(body.classLevel).strip() if body.classLevel not in (None, "") else "11"
        if level not in CLASS_LEVELS:
            bad("classLevel must be 11 or 12")
        section = str(body.section or "").strip().upper()
        if section not in SECTIONS:
            bad("section must be A or B")
        profile["classLevel"] = level
        profile["section"] = section

    profile["createdAt"] = int(time.time() * 1000)
    return profile


@router.post("/register")
async def register(body: RegisterBody):
    profile = build_profile(body)

    created = await fb_call(
        "signUp",
        {"email": profile["email"], "password": body.password, "returnSecureToken": True},
    )
    uid = created["localId"]
    token = created["idToken"]

    user = {"uid": uid, **profile}
    if not await db_write(uid, token, user):
        try:
            await fb_call("delete", {"idToken": token})
        except HTTPException:
            pass
        raise HTTPException(status_code=502, detail="Could not save profile, account was not created")

    return user