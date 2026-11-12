from fastapi import APIRouter, File, Header, HTTPException, Request, UploadFile

from upload.common import check_key, prepare, serve, store

router = APIRouter()


@router.post("/upload/video")
async def upload_video(file: UploadFile = File(...), x_api_key: str = Header(None)):
    check_key(x_api_key)
    data, name, mime = await prepare("vid", file)
    if not mime.startswith("video/"):
        raise HTTPException(status_code=400, detail="Not a video")
    return {"url": await store("vid", data, name)}


@router.get("/vid/{name}")
async def get_vid(name: str, request: Request):
    return await serve("vid", name, request)