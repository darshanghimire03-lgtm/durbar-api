from fastapi import APIRouter, Header, HTTPException

from mocks.common import check_key, editor_subject
from post.common import as_dict, check_id, db_delete, db_get, sign_in

router = APIRouter()


@router.delete("/{subject_key}/{question_id}")
async def delete_question(
    subject_key: str,
    question_id: str,
    x_email: str = Header(None),
    x_password: str = Header(None),
):
    uid, token, user = await sign_in(x_email, x_password)
    check_key(subject_key)
    check_id(question_id)
    editor_subject(user, subject_key)

    question = await db_get(f"mocks/{subject_key}/questions/{question_id}", token)
    if not isinstance(question, dict):
        raise HTTPException(status_code=404, detail="Question not found")

    await db_delete(f"mocks/{subject_key}/questions/{question_id}", token)

    left = as_dict(await db_get(f"mocks/{subject_key}/questions", token, {"shallow": "true"}))
    if not left:
        await db_delete(f"mocks/{subject_key}", token)

    return {"subjectKey": subject_key, "questionId": question_id, "deleted": True}