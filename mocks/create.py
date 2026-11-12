import secrets
import time
from typing import List, Optional

from fastapi import APIRouter, Header
from pydantic import BaseModel

from auth.common import bad
from mocks.common import (
    MAX_QUESTION,
    clean_options,
    clean_photos,
    editor_subject,
    view_question,
)
from post.common import db_put, sign_in

router = APIRouter()


class QuestionBody(BaseModel):
    question: Optional[str] = ""
    options: Optional[List[str]] = None
    answerIndex: Optional[int] = None
    photos: Optional[List[str]] = None


@router.post("")
async def create_question(
    body: QuestionBody,
    x_email: str = Header(None),
    x_password: str = Header(None),
):
    uid, token, user = await sign_in(x_email, x_password)
    subject, key = editor_subject(user)

    text = str(body.question or "").strip()
    if not text:
        bad("question is required")
    if len(text) > MAX_QUESTION:
        bad(f"question must be at most {MAX_QUESTION} characters")

    options = clean_options(body.options)
    if body.answerIndex is None or not 0 <= body.answerIndex < len(options):
        bad("answerIndex must be between 0 and 3")
    photos = clean_photos(body.photos)

    question_id = f"q{int(time.time() * 1000)}{secrets.token_hex(2)}"
    question = {
        "questionId": question_id,
        "question": text,
        "options": options,
        "answerIndex": body.answerIndex,
        "subject": subject,
    }
    if photos:
        question["photos"] = photos

    await db_put(f"mocks/{key}/subject", token, subject)
    await db_put(f"mocks/{key}/questions/{question_id}", token, question)
    return view_question(question_id, question, key)