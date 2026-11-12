import re

from fastapi import HTTPException

from auth.common import bad
from post.common import as_list, check_id, check_image, num

EDITOR_ROLES = ("professor", "moderator")
MAX_QUESTION = 500
MAX_OPTION = 200
OPTION_COUNT = 4
MAX_PHOTOS = 4


def subject_key(text):
    key = re.sub(r"[^a-z0-9]+", "_", str(text or "").lower()).strip("_")
    return key[:40]


def check_key(value):
    return check_id(value)


def editor_subject(user, key=None):
    role = str(user.get("role", "")).lower()
    if role not in EDITOR_ROLES:
        raise HTTPException(status_code=403, detail="Only professors and moderators can manage mocks")
    subject = re.sub(r"\s+", " ", str(user.get("assignedSubject") or "")).strip()
    own_key = subject_key(subject)
    if not own_key:
        raise HTTPException(status_code=403, detail="No subject is assigned to your account")
    if key is not None and key != own_key:
        raise HTTPException(status_code=403, detail="You can only manage mocks for your assigned subject")
    return subject, own_key


def clean_options(raw):
    options = [str(o or "").strip() for o in (raw or [])]
    if len(options) != OPTION_COUNT or any(not o for o in options):
        bad(f"options must be exactly {OPTION_COUNT} non-empty answers")
    if any(len(o) > MAX_OPTION for o in options):
        bad(f"Each option must be at most {MAX_OPTION} characters")
    return options


def clean_photos(raw):
    photos = []
    for item in raw or []:
        url = check_image(item)
        if url and url not in photos:
            photos.append(url)
    if len(photos) > MAX_PHOTOS:
        bad(f"A question can have at most {MAX_PHOTOS} photos")
    return photos


def view_question(question_id, q, key):
    return {
        "questionId": question_id,
        "subjectKey": key,
        "subject": q.get("subject", ""),
        "question": q.get("question", ""),
        "options": [str(o) for o in as_list(q.get("options"))],
        "answerIndex": num(q.get("answerIndex")),
        "photos": as_list(q.get("photos")),
    }