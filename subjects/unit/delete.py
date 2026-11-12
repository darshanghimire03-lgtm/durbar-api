from fastapi import APIRouter, Header

from post.common import db_delete, sign_in
from subjects.common import load_unit, require_manager

router = APIRouter()


@router.delete("/{subject_key}/units/{unit_id}")
async def delete_unit(
    subject_key: str,
    unit_id: str,
    x_email: str = Header(None),
    x_password: str = Header(None),
):
    uid, token, user = await sign_in(x_email, x_password)
    await load_unit(subject_key, unit_id, token)
    require_manager(user, subject_key)
    await db_delete(f"units/{subject_key}/{unit_id}", token)
    return {"subjectKey": subject_key, "unitId": unit_id, "deleted": True}