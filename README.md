# Durbar API

Backend for the Durbar app. It does three things:

- registers and logs in students and professors
- uploads images, videos and files
- serves the uploaded files on your own domain

Server: `https://durbar-api-1.onrender.com`
Public links: `https://durbar-plus2.vercel.app`

## Project structure

```
project/
├── main.py
├── requirements.txt
├── auth/
│   ├── common.py
│   ├── register.py
│   └── login.py
└── upload/
    ├── common.py
    ├── img.py
    ├── vid.py
    └── file.py
```

Do not add `__init__.py` files.

## Setup

### 1. requirements.txt

```
fastapi
uvicorn
httpx
python-multipart
```

### 2. Render

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

Environment variables:

| Name | Required | What it is |
|---|---|---|
| `FIREBASE_API_KEY` | yes | Firebase web API key |
| `FIREBASE_DB_URL` | yes | Realtime Database URL |
| `CLOUDINARY_VIDEO_CLOUD_NAME` | yes | Cloudinary cloud for videos |
| `CLOUDINARY_VIDEO_PRESET` | yes | Unsigned preset for videos |
| `CLOUDINARY_FILE_CLOUD_NAME` | yes | Cloudinary cloud for files |
| `CLOUDINARY_FILE_PRESET` | yes | Unsigned preset for files |
| `CLOUDINARY_IMAGE_CLOUD_NAME` | no | Cloud for images (defaults to the file cloud) |
| `CLOUDINARY_IMAGE_PRESET` | no | Preset for images (defaults to the file preset) |
| `PUBLIC_BASE_URL` | no | Defaults to `https://durbar-plus2.vercel.app` |
| `UPLOAD_API_KEY` | no | If set, uploads must send it as `X-API-Key` |

If the server crashes with `Missing environment variable`, add the name it shows.

### 3. Firebase

1. Authentication → Sign-in method → enable **Email/Password**.
2. Realtime Database → Rules:

```json
{
  "rules": {
    "users": {
      "$uid": {
        ".read": "auth != null && auth.uid === $uid",
        ".write": "auth != null && auth.uid === $uid"
      }
    }
  }
}
```

### 4. Cloudinary presets

Each unsigned upload preset must have an empty "Asset folder" and "Public ID prefix", must not use random or unique file names, and must have overwrite turned off.

### 5. Vercel

Put this `vercel.json` in the project that hosts `durbar-plus2.vercel.app`, then redeploy:

```json
{
  "rewrites": [
    { "source": "/img/:path*", "destination": "https://durbar-api-1.onrender.com/img/:path*" },
    { "source": "/vid/:path*", "destination": "https://durbar-api-1.onrender.com/vid/:path*" },
    { "source": "/file/:path*", "destination": "https://durbar-api-1.onrender.com/file/:path*" }
  ]
}
```

Send uploads and logins to the Render URL, never through Vercel. Vercel limits request body size.

## How to use

### Register a student

`POST /auth/register`

```json
{
  "role": "student",
  "email": "ram@gmail.com",
  "password": "secret123",
  "fullName": "Ram Sharma",
  "phone": "9812345678",
  "gender": "male",
  "profileImageUrl": "https://durbar-plus2.vercel.app/img/ram.jpg",
  "classLevel": "11",
  "section": "A"
}
```

`classLevel` is optional and defaults to `11`. `section` is `A` or `B`.

### Register a professor

`POST /auth/register`

```json
{
  "role": "professor",
  "email": "sita@gmail.com",
  "password": "secret123",
  "fullName": "Sita Karki",
  "phone": "+9779812345678",
  "gender": "female",
  "profileImageUrl": "",
  "assignedSubject": "Physics"
}
```

Professors have a subject. Students have a class level and section. The server ignores any extra fields.

### Login

`POST /auth/login`

```json
{ "email": "ram@gmail.com", "password": "secret123" }
```

Register and login both return the saved profile:

```json
{
  "uid": "Zk3...",
  "email": "ram@gmail.com",
  "fullName": "Ram Sharma",
  "profileImageUrl": "https://durbar-plus2.vercel.app/img/ram.jpg",
  "role": "student",
  "phone": "+9779812345678",
  "gender": "male",
  "classLevel": "11",
  "section": "A",
  "createdAt": 1731400000000
}
```

The app should keep this profile on the device as its logged-in state. No token is returned.

### Rules for registration

- Email must end in `@gmail.com`.
- Phone: `+977` is added if missing. Other country codes are rejected.
- Password: at least 6 characters.
- Gender: `male`, `female` or `other`.
- `profileImageUrl` must be a link from this server. Upload the picture first, then send the returned link.
- The `uid` is created by the server. Never send one.

### Upload a file

Send `multipart/form-data` with one field named `file`:

| Type | Endpoint | Limit |
|---|---|---|
| Image | `POST /upload/image` | 10 MB |
| Video | `POST /upload/video` | 100 MB |
| File | `POST /upload/file` | 10 MB |

If `UPLOAD_API_KEY` is set, also send the header `X-API-Key`.

Response:

```json
{ "url": "https://durbar-plus2.vercel.app/img/photo.jpg" }
```

Save this `url` and use it as is. The file keeps the name the app sent. If that name is already taken, a number is added: `photo-1.jpg`, `photo-2.jpg` and so on.

Names that contain `? & # \ % < >` or start with a dot are rejected.

### Show an uploaded file

```html
<img src="https://durbar-plus2.vercel.app/img/photo.jpg">
<video src="https://durbar-plus2.vercel.app/vid/clip.mp4" controls></video>
<a href="https://durbar-plus2.vercel.app/file/notes.pdf">Download</a>
```

### Typical flow for a new user

1. Upload the profile picture with `/upload/image` and keep the returned `url`.
2. Call `/auth/register` with that `url` as `profileImageUrl`.
3. Save the returned profile on the device.
4. Next time, call `/auth/login`.

## Test pages

- `test.html` tests the three uploads.
- `login.html` tests login.

Open them in any browser. Both call the Render server directly.

## Errors

Every error has a message you can show to the user:

```json
{ "detail": "Only @gmail.com emails are accepted" }
```

| Status | Meaning |
|---|---|
| 400 | Bad input (email, phone, name, missing field) |
| 401 | Wrong email or password, or bad API key |
| 404 | Profile or file not found |
| 409 | Email already registered |
| 413 | File too large |
| 502 | Firebase or Cloudinary failed |

## Troubleshooting

- **First request is slow:** Render's free tier sleeps when idle. The first call can take up to a minute.
- **Custom links give 404:** the Vercel rewrites are missing or point to the wrong Render URL. The same path on the Render URL should open the file.
- **`Email/password sign-in is not enabled`:** turn on Email/Password in Firebase.
- **`Could not save profile`:** check the Realtime Database rules and `FIREBASE_DB_URL`.
- **`Cloudinary preset changed the file name`:** remove the folder, prefix and unique-name settings from the preset.
- **Deploy crashes on `import`:** the `auth/` and `upload/` folders must be pushed in full, with lowercase names.