import asyncio

from fastapi import APIRouter, Header, HTTPException

from mocks.common import check_key, view_question
from post.common import as_dict, check_id, db_get, sign_in

router = APIRouter()


async def subject_summary(key, token):
    subject, ids = await asyncio.gather(
        db_get(f"mocks/{key}/subject", token),
        db_get(f"mocks/{key}/questions", token, {"shallow": "true"}),
    )
    return {
        "subjectKey": key,
        "subject": subject if isinstance(subject, str) else key,
        "questionCount": len(as_dict(ids)),
    }


@router.get("")
async def list_subjects(x_email: str = Header(None), x_password: str = Header(None)):
    uid, token, user = await sign_in(x_email, x_password)
    keys = sorted(as_dict(await db_get("mocks", token, {"shallow": "true"})).keys())
    subjects = await asyncio.gather(*(subject_summary(k, token) for k in keys))
    return {"subjects": [s for s in subjects if s["questionCount"] > 0]}


@router.get("/{subject_key}")
async def get_subject(subject_key: str, x_email: str = Header(None), x_password: str = Header(None)):
    uid, token, user = await sign_in(x_email, x_password)
    check_key(subject_key)
    node = await db_get(f"mocks/{subject_key}", token)
    if not isinstance(node, dict):
        raise HTTPException(status_code=404, detail="Subject not found")
    items = [
        view_question(k, v, subject_key)
        for k, v in as_dict(node.get("questions")).items()
        if isinstance(v, dict)
    ]
    items.sort(key=lambda q: q["questionId"])
    subject = node.get("subject")
    return {
        "subjectKey": subject_key,
        "subject": subject if isinstance(subject, str) else subject_key,
        "questionCount": len(items),
        "questions": items,
    }


@router.get("/{subject_key}/{question_id}")
async def get_question(
    subject_key: str,
    question_id: str,
    x_email: str = Header(None),
    x_password: str = Header(None),
):
    uid, token, user = await sign_in(x_email, x_password)
    check_key(subject_key)
    check_id(question_id)
    question = await db_get(f"mocks/{subject_key}/questions/{question_id}", token)
    if not isinstance(question, dict):
        raise HTTPException(status_code=404, detail="Question not found")
    return view_question(question_id, question, subject_key)