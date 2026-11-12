from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth.login import router as login_router
from auth.register import router as register_router
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
app.include_router(img_router)
app.include_router(vid_router)
app.include_router(file_router)


@app.get("/")
async def root():
    return {"ok": True}