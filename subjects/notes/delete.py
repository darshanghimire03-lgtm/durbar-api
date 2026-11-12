from fastapi import APIRouter, Header, HTTPException

from post.common import check_id, db_delete, db_get, sign_in
from subjects.common import load_unit, require_manager

router = APIRouter()


@router.delete("/{subject_key}/units/{unit_id}/notes/{note_id}")
async def delete_note(
    subject_key: str,
    unit_id: str,
    note_id: str,
    x_email: str = Header(None),
    x_password: str = Header(None),
):
    uid, token, user = await sign_in(x_email, x_password)
    await load_unit(subject_key, unit_id, token)
    require_manager(user, subject_key)
    check_id(note_id)

    note = await db_get(f"units/{subject_key}/{unit_id}/notes/{note_id}", token)
    if not isinstance(note, dict):
        raise HTTPException(status_code=404, detail="Note not found")

    await db_delete(f"units/{subject_key}/{unit_id}/notes/{note_id}", token)
    return {"subjectKey": subject_key, "unitId": unit_id, "noteId": note_id, "deleted": True}