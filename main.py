from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth.login import router as login_router
from auth.register import router as register_router
from calender.access import router as calendar_access_router
from calender.create import router as calendar_create_router
from mocks.access import router as mock_access_router
from mocks.create import router as mock_create_router
from mocks.delete import router as mock_delete_router
from post.access import router as post_access_router
from post.comment import router as post_comment_router
from post.delete import router as post_delete_router
from post.like import router as post_like_router
from post.post import router as post_create_router
from shorts.access import router as short_access_router
from shorts.delete import router as short_delete_router
from shorts.like import router as short_like_router
from shorts.shorts import router as short_create_router
from upload.file import router as file_router
from upload.img import router as img_router
from upload.vid import router as vid_router

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"],
)

app.include_router(register_router, prefix="/auth")
app.include_router(login_router, prefix="/auth")
app.include_router(calendar_create_router, prefix="/calendar")
app.include_router(calendar_access_router, prefix="/calendar")
app.include_router(post_create_router, prefix="/posts")
app.include_router(post_like_router, prefix="/posts")
app.include_router(post_comment_router, prefix="/posts")
app.include_router(post_delete_router, prefix="/posts")
app.include_router(post_access_router, prefix="/posts")
app.include_router(short_create_router, prefix="/shorts")
app.include_router(short_like_router, prefix="/shorts")
app.include_router(short_delete_router, prefix="/shorts")
app.include_router(short_access_router, prefix="/shorts")
app.include_router(mock_create_router, prefix="/mocks")
app.include_router(mock_delete_router, prefix="/mocks")
app.include_router(mock_access_router, prefix="/mocks")
app.include_router(img_router)
app.include_router(vid_router)
app.include_router(file_router)


@app.get("/")
async def root():
    return {"ok": True}