from fastapi import APIRouter, File, Header, Request, UploadFile

from upload.common import check_key, prepare, serve, store

router = APIRouter()


@router.post("/upload/file")
async def upload_file(file: UploadFile = File(...), x_api_key: str = Header(None)):
    check_key(x_api_key)
    data, name, mime = await prepare("file", file)
    url, stored = await store("file", data, name)
    return {"url": url, "name": stored}


@router.get("/file/{name}")
async def get_file(name: str, request: Request):
    return await serve("file", name, request)