import re
from urllib.parse import parse_qs, urlparse

from fastapi import HTTPException

from auth.common import PUBLIC_BASE, bad
from mocks.common import subject_key
from post.common import as_dict, as_list, check_id, check_image, db_get, num

SUPER_EMAIL = "darshanghimire03@gmail.com"

ALL = ["Economic", "Account", "Computer Science", "English", "Nepali"]
CALENDAR = ALL + ["Social"]
SUBJECTS = {subject_key(name): name for name in ALL}

MAX_UNIT_NAME = 100
MAX_TITLE = 150
MAX_DESC = 5000
MAX_PDFS = 10
MAX_PHOTOS = 10
MAX_LINKS = 20
MAX_PDF_BYTES = 10 * 1024 * 1024
YT_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
YT_HOSTS = ("youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com")


def resolve_subject(key):
    name = SUBJECTS.get(str(key or ""))
    if not name:
        raise HTTPException(status_code=404, detail="Subject not found")
    return name


def email_of(user):
    return str(user.get("email", "")).strip().lower()


def role_of(user):
    return str(user.get("role", "")).strip().lower()


def is_super(user):
    return email_of(user) == SUPER_EMAIL


def creator_role(user):
    if is_super(user):
        return "moderator"
    return "professor" if role_of(user) == "professor" else "moderator"


def can_manage_subject(user, key):
    if is_super(user):
        return True
    role = role_of(user)
    if role == "professor":
        return True
    if role != "moderator":
        return False
    assigned = subject_key(user.get("assignedSubject"))
    return assigned != "" and assigned == key


def require_manager(user, key):
    if not can_manage_subject(user, key):
        raise HTTPException(status_code=403, detail="You cannot manage this subject")


def clean_text(value, label, low, high):
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not low <= len(text) <= high:
        bad(f"{label} must be {low}-{high} characters")
    return text


def parse_youtube(raw):
    url = str(raw or "").strip()
    parsed = urlparse(url if "://" in url else "https://" + url)
    host = (parsed.hostname or "").lower()
    video_id = ""
    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
    elif host in YT_HOSTS:
        if parsed.path == "/watch":
            video_id = (parse_qs(parsed.query).get("v") or [""])[0]
        else:
            parts = [p for p in parsed.path.split("/") if p]
            if len(parts) >= 2 and parts[0] in ("shorts", "embed", "live", "v"):
                video_id = parts[1]
    if not YT_ID.fullmatch(video_id):
        bad("Invalid YouTube link")
    return f"https://www.youtube.com/watch?v={video_id}", video_id


def check_pdf(item):
    url = str(item.url or "").strip()
    if len(url) > 500 or not url.startswith(f"{PUBLIC_BASE}/file/"):
        bad("PDF URLs must come from this server's file upload")
    name = re.sub(r"\s+", " ", str(item.name or "")).strip() or url.rsplit("/", 1)[-1]
    if not 1 <= len(name) <= 150:
        bad("PDF name must be 1-150 characters")
    size = num(item.sizeBytes)
    if not 0 <= size <= MAX_PDF_BYTES:
        bad("PDF sizeBytes is out of range")
    return {"url": url, "name": name, "sizeBytes": size}


def view_note(note_id, n):
    return {
        "id": note_id,
        "title": n.get("title", ""),
        "description": n.get("description", ""),
        "pdfs": [
            {"url": p.get("url", ""), "name": p.get("name", ""), "sizeBytes": num(p.get("sizeBytes"))}
            for p in as_list(n.get("pdfs"))
            if isinstance(p, dict)
        ],
        "photos": [{"url": p.get("url", "")} for p in as_list(n.get("photos")) if isinstance(p, dict)],
        "youtubeLinks": [
            {"url": y.get("url", ""), "videoId": y.get("videoId", ""), "videoNumber": num(y.get("videoNumber"))}
            for y in as_list(n.get("youtubeLinks"))
            if isinstance(y, dict)
        ],
        "createdBy": n.get("createdBy", ""),
        "createdAt": num(n.get("createdAt")),
    }


def note_list(node):
    items = [view_note(k, v) for k, v in as_dict(node).items() if isinstance(v, dict)]
    items.sort(key=lambda n: n["createdAt"])
    return items


def view_unit(unit_id, u, with_notes=False):
    notes = as_dict(u.get("notes"))
    result = {
        "id": unit_id,
        "name": u.get("name", ""),
        "createdByRole": u.get("createdByRole", ""),
        "noteCount": sum(1 for v in notes.values() if isinstance(v, dict)),
    }
    if with_notes:
        result["notes"] = note_list(notes)
    return result


async def load_unit(key, unit_id, token):
    subject = resolve_subject(key)
    check_id(unit_id)
    unit = await db_get(f"units/{key}/{unit_id}", token)
    if not isinstance(unit, dict):
        raise HTTPException(status_code=404, detail="Unit not found")
    return subject, unit