from fastapi import APIRouter, File, Header, HTTPException, Request, UploadFile

from upload.common import check_key, prepare, serve, store

router = APIRouter()


@router.post("/upload/image")
async def upload_image(file: UploadFile = File(...), x_api_key: str = Header(None)):
    check_key(x_api_key)
    data, name, mime = await prepare("img", file)
    if not mime.startswith("image/"):
        raise HTTPException(status_code=400, detail="Not an image")
    return {"url": await store("img", data, name)}


@router.get("/img/{name}")
async def get_img(name: str, request: Request):
    return await serve("img", name, request)