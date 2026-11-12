import asyncio

from fastapi import APIRouter, Header, HTTPException

from post.common import as_dict, check_id, db_get, sign_in
from subjects.common import (
    SUBJECTS,
    load_unit,
    note_list,
    resolve_subject,
    view_note,
    view_unit,
)

router = APIRouter()


async def unit_count(key, token):
    ids = await db_get(f"units/{key}", token, {"shallow": "true"})
    return len(as_dict(ids))


@router.get("")
async def list_subjects(x_email: str = Header(None), x_password: str = Header(None)):
    uid, token, user = await sign_in(x_email, x_password)
    keys = list(SUBJECTS.keys())
    counts = await asyncio.gather(*(unit_count(k, token) for k in keys))
    return {
        "subjects": [
            {"subjectKey": k, "name": SUBJECTS[k], "unitCount": c} for k, c in zip(keys, counts)
        ]
    }


@router.get("/{subject_key}/units")
async def list_units(subject_key: str, x_email: str = Header(None), x_password: str = Header(None)):
    uid, token, user = await sign_in(x_email, x_password)
    subject = resolve_subject(subject_key)
    raw = as_dict(await db_get(f"units/{subject_key}", token))
    units = [view_unit(k, v) for k, v in raw.items() if isinstance(v, dict)]
    units.sort(key=lambda u: u["id"])
    return {"subjectKey": subject_key, "subject": subject, "units": units}


@router.get("/{subject_key}/units/{unit_id}")
async def get_unit(
    subject_key: str,
    unit_id: str,
    x_email: str = Header(None),
    x_password: str = Header(None),
):
    uid, token, user = await sign_in(x_email, x_password)
    subject, unit = await load_unit(subject_key, unit_id, token)
    result = view_unit(unit_id, unit, with_notes=True)
    result["subjectKey"] = subject_key
    result["subject"] = subject
    return result


@router.get("/{subject_key}/units/{unit_id}/notes")
async def list_notes(
    subject_key: str,
    unit_id: str,
    x_email: str = Header(None),
    x_password: str = Header(None),
):
    uid, token, user = await sign_in(x_email, x_password)
    await load_unit(subject_key, unit_id, token)
    node = await db_get(f"units/{subject_key}/{unit_id}/notes", token)
    return {"subjectKey": subject_key, "unitId": unit_id, "notes": note_list(node)}


@router.get("/{subject_key}/units/{unit_id}/notes/{note_id}")
async def get_note(
    subject_key: str,
    unit_id: str,
    note_id: str,
    x_email: str = Header(None),
    x_password: str = Header(None),
):
    uid, token, user = await sign_in(x_email, x_password)
    resolve_subject(subject_key)
    check_id(unit_id)
    check_id(note_id)
    note = await db_get(f"units/{subject_key}/{unit_id}/notes/{note_id}", token)
    if not isinstance(note, dict):
        raise HTTPException(status_code=404, detail="Note not found")
    return view_note(note_id, note)