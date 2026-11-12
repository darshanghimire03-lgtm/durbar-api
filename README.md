# Durbar Upload API

A small FastAPI server that uploads images, videos and files to Cloudinary and serves them back from your own domain. It also includes a single-page upload tester (`index.html`).

Uploaded files keep their original name. If a file with the same name already exists, a number is added: `photo.png`, `photo-1.png`, `photo-2.png`.

## Project structure

```
.
├── main.py
├── requirements.txt
├── index.html
└── upload/
    ├── common.py
    ├── img.py
    ├── vid.py
    └── file.py
```

## Requirements

- Python 3.10 or newer
- A Cloudinary account with unsigned upload presets

## Install

```bash
pip install -r requirements.txt
```

## Environment variables

| Variable | Required | Description |
| --- | --- | --- |
| `CLOUDINARY_VIDEO_CLOUD_NAME` | Yes | Cloudinary cloud name used for videos |
| `CLOUDINARY_VIDEO_PRESET` | Yes | Unsigned upload preset for videos |
| `CLOUDINARY_FILE_CLOUD_NAME` | Yes | Cloudinary cloud name used for files |
| `CLOUDINARY_FILE_PRESET` | Yes | Unsigned upload preset for files |
| `CLOUDINARY_IMAGE_CLOUD_NAME` | No | Cloud name for images. Falls back to the file cloud name |
| `CLOUDINARY_IMAGE_PRESET` | No | Preset for images. Falls back to the file preset |
| `PUBLIC_BASE_URL` | No | Public address of this server, used in returned links. Default: `https://durbar-plus2.vercel.app` |
| `UPLOAD_API_KEY` | No | If set, every upload must send this key in the `X-API-Key` header |

The server will not start if a required variable is missing.

## Cloudinary preset setup

Create an unsigned upload preset for each of video and file (and image if you use a separate one). In each preset:

- Set the signing mode to **Unsigned**.
- Leave the folder empty.
- Turn off any "use filename" or "unique filename" override.

If a preset renames files or puts them in a folder, uploads fail with `Cloudinary preset changed the file name (expected ..., got ...)`.

## Run locally

```bash
export CLOUDINARY_VIDEO_CLOUD_NAME=your_cloud
export CLOUDINARY_VIDEO_PRESET=your_video_preset
export CLOUDINARY_FILE_CLOUD_NAME=your_cloud
export CLOUDINARY_FILE_PRESET=your_file_preset
export PUBLIC_BASE_URL=http://localhost:8000

uvicorn main:app --reload
```

The server runs at `http://localhost:8000`. A request to `/` returns `{"ok": true}`.

## Deploy (Render)

1. Push the project to a Git repository.
2. Create a new **Web Service** on Render and connect the repository.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add the environment variables from the table above.
6. Set `PUBLIC_BASE_URL` to the public address that serves this API, so returned links point to the right place.

The first request after a period of inactivity can be slow on free plans while the server wakes up.

## API

### Upload an image

`POST /upload/image`

- Body: `multipart/form-data` with a `file` field
- Must be an image, up to 10 MB

### Upload a video

`POST /upload/video`

- Body: `multipart/form-data` with a `file` field
- Must be a video, up to 100 MB

### Upload a file

`POST /upload/file`

- Body: `multipart/form-data` with a `file` field
- Any file type, up to 10 MB

### Upload response

```json
{
  "url": "https://durbar-plus2.vercel.app/file/lecture.pdf",
  "name": "lecture.pdf"
}
```

`name` is the exact stored name. If `lecture.pdf` already existed, it would be `lecture-1.pdf`.

### Fetch an uploaded file

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/img/{name}` | Serve an image |
| `GET` | `/vid/{name}` | Serve a video, supports range requests for seeking |
| `GET` | `/file/{name}` | Serve a file |

Files are streamed through the server and cached for one year.

### Example requests

```bash
curl -X POST https://your-server/upload/image -F "file=@photo.png"
curl -X POST https://your-server/upload/video -F "file=@clip.mp4"
curl -X POST https://your-server/upload/file -F "file=@lecture.pdf"
```

With an API key:

```bash
curl -X POST https://your-server/upload/file \
  -H "X-API-Key: your_key" \
  -F "file=@lecture.pdf"
```

## Naming rules

- The original file name is kept.
- Folder parts are removed. `a/b/c.png` becomes `c.png`.
- Names cannot start with a dot, be longer than 150 characters, or contain `? & # \ % < >` or non-printable characters.
- Images and videos need a file extension. If it is missing, one is added from the file type, or the upload is rejected.
- A name that is already taken gets `-1`, `-2` and so on before the extension.

## Errors

| Status | Meaning |
| --- | --- |
| 400 | Empty file, invalid name, wrong file type or missing extension |
| 401 | Missing or wrong `X-API-Key` |
| 404 | File not found when fetching |
| 409 | Too many files with the same name |
| 413 | File is over the size limit |
| 502 | Cloudinary failed or a preset changed the name. The message says which |

Error responses look like `{"detail": "message"}`.

## Upload test page

`index.html` is a standalone page for trying the three uploads. Open it in a browser, enter the API base URL (and the API key if your server needs one), pick a file and upload. It shows a progress bar, the returned link with a copy button, and a preview for images and videos.

## Security notes

- Set `UPLOAD_API_KEY` if the server is public, otherwise anyone who finds it can upload files.
- HTML, XHTML and SVG files are never served inline. They are sent as downloads so they cannot run scripts on your domain.
- Files cannot be deleted through this API. Remove them from the Cloudinary dashboard.
- The API key typed into the test page is kept in the browser tab's session storage until the tab closes.