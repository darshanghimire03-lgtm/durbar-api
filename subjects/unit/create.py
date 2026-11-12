import secrets
import time
from typing import Optional

from fastapi import APIRouter, Header
from pydantic import BaseModel

from post.common import db_put, sign_in
from subjects.common import (
    MAX_UNIT_NAME,
    clean_text,
    creator_role,
    require_manager,
    resolve_subject,
    view_unit,
)

router = APIRouter()


class UnitBody(BaseModel):
    name: Optional[str] = ""


@router.post("/{subject_key}/units")
async def create_unit(
    subject_key: str,
    body: UnitBody,
    x_email: str = Header(None),
    x_password: str = Header(None),
):
    uid, token, user = await sign_in(x_email, x_password)
    resolve_subject(subject_key)
    require_manager(user, subject_key)

    name = clean_text(body.name, "name", 1, MAX_UNIT_NAME)
    unit_id = f"u{int(time.time() * 1000)}{secrets.token_hex(2)}"
    unit = {"id": unit_id, "name": name, "createdByRole": creator_role(user)}

    await db_put(f"units/{subject_key}/{unit_id}", token, unit)
    return view_unit(unit_id, unit)