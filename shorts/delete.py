from fastapi import APIRouter, Header, HTTPException

from post.common import db_delete, sign_in
from shorts.common import load_short

router = APIRouter()


@router.delete("/{short_id}")
async def delete_short(short_id: str, x_email: str = Header(None), x_password: str = Header(None)):
    uid, token, user = await sign_in(x_email, x_password)
    short = await load_short(short_id, token)
    if short.get("uploaderUid") != uid:
        raise HTTPException(status_code=403, detail="Only the uploader can delete this short")
    await db_delete(f"shorts/{short_id}", token)
    return {"shortId": short_id, "deleted": True}