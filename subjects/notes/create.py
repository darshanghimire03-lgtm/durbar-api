import secrets
import time
from typing import List, Optional

from fastapi import APIRouter, Header
from pydantic import BaseModel

from auth.common import bad
from post.common import check_image, db_put, sign_in
from subjects.common import (
    MAX_DESC,
    MAX_LINKS,
    MAX_PDFS,
    MAX_PHOTOS,
    MAX_TITLE,
    check_pdf,
    clean_text,
    load_unit,
    parse_youtube,
    require_manager,
    view_note,
)

router = APIRouter()


class PdfBody(BaseModel):
    url: Optional[str] = ""
    name: Optional[str] = ""
    sizeBytes: Optional[int] = 0


class PhotoBody(BaseModel):
    url: Optional[str] = ""


class LinkBody(BaseModel):
    url: Optional[str] = ""


class NoteBody(BaseModel):
    title: Optional[str] = ""
    description: Optional[str] = ""
    pdfs: Optional[List[PdfBody]] = None
    photos: Optional[List[PhotoBody]] = None
    youtubeLinks: Optional[List[LinkBody]] = None


@router.post("/{subject_key}/units/{unit_id}/notes")
async def create_note(
    subject_key: str,
    unit_id: str,
    body: NoteBody,
    x_email: str = Header(None),
    x_password: str = Header(None),
):
    uid, token, user = await sign_in(x_email, x_password)
    await load_unit(subject_key, unit_id, token)
    require_manager(user, subject_key)

    title = clean_text(body.title, "title", 1, MAX_TITLE)
    description = str(body.description or "").strip()
    if len(description) > MAX_DESC:
        bad(f"description must be at most {MAX_DESC} characters")

    pdfs = [check_pdf(p) for p in (body.pdfs or [])]
    if len(pdfs) > MAX_PDFS:
        bad(f"A note can have at most {MAX_PDFS} PDFs")

    photos = []
    for p in body.photos or []:
        url = check_image(p.url)
        if url and url not in photos:
            photos.append(url)
    if len(photos) > MAX_PHOTOS:
        bad(f"A note can have at most {MAX_PHOTOS} photos")

    links = []
    seen = set()
    for item in body.youtubeLinks or []:
        url, video_id = parse_youtube(item.url)
        if video_id in seen:
            continue
        seen.add(video_id)
        links.append({"url": url, "videoId": video_id, "videoNumber": len(links) + 1})
    if len(links) > MAX_LINKS:
        bad(f"A note can have at most {MAX_LINKS} YouTube links")

    if not description and not pdfs and not photos and not links:
        bad("A note needs a description, a PDF, a photo or a YouTube link")

    note_id = f"n{int(time.time() * 1000)}{secrets.token_hex(2)}"
    note = {
        "id": note_id,
        "title": title,
        "description": description,
        "createdBy": uid,
        "createdAt": int(time.time() * 1000),
    }
    if pdfs:
        note["pdfs"] = pdfs
    if photos:
        note["photos"] = [{"url": u} for u in photos]
    if links:
        note["youtubeLinks"] = links

    await db_put(f"units/{subject_key}/{unit_id}/notes/{note_id}", token, note)
    return view_note(note_id, note)