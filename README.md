# Durbar Media Backend

Image, video and file upload API. Hosted on Render, served through `https://durbar-plus2.vercel.app`.

There is no database and no login. Each upload goes to the storage provider first, and the API returns a link on your own domain.

## How it works

- Images are stored on imgbb. Videos and files are stored on separate Cloudinary accounts.
- After the upload, the provider's URL path is encoded into a token. The returned link is `PUBLIC_BASE_URL/<type>/<token>.<ext>`.
- When a link is opened, the backend decodes the token, checks that it points to your own provider account, and streams the file back. Range requests work, so video seeking works.
- Uploads go directly to your Render URL. Only the returned `/img`, `/vid` and `/file` links use the Vercel domain.

| Type  | View URL                                           |
|-------|----------------------------------------------------|
| Image | https://durbar-plus2.vercel.app/img/TOKEN.ext      |
| Video | https://durbar-plus2.vercel.app/vid/TOKEN.ext      |
| File  | https://durbar-plus2.vercel.app/file/TOKEN.ext     |

Replace `https://YOUR-SERVICE.onrender.com` below with your real Render URL.

## Limits

| Type  | Max size |
|-------|----------|
| Image | 32 MB    |
| Video | 100 MB   |
| File  | 10 MB    |

## API

### Upload

| Endpoint             | Field  |
|----------------------|--------|
| `POST /upload/image` | `file` |
| `POST /upload/video` | `file` |
| `POST /upload/file`  | `file` |

Send as `multipart/form-data`. If `UPLOAD_API_KEY` is set on the server, also send the header `X-API-Key: <key>`.

Response:

```json
{
  "url": "https://durbar-plus2.vercel.app/img/aS1kLmliYi5jby9BYjNk.jpg",
  "id": "aS1kLmliYi5jby9BYjNk",
  "name": "photo.jpg",
  "size": 245678
}
```

Save the returned `url` in your own database (for example in a post or profile) and use it directly.

### Health check

`GET /` returns `{ "ok": true }`.

### View

`GET /img/{token}.{ext}`, `GET /vid/{token}.{ext}` and `GET /file/{token}.{ext}` stream the stored file.

### Errors

Errors return an HTTP status and:

```json
{ "detail": "File too large" }
```

Common values: `Invalid API key`, `Empty file`, `File too large`, `Not an image`, `Not a video`, `imgbb upload failed`, `Cloudinary upload failed`, `Unexpected provider URL`, `Not found`.

## Android (Kotlin)

### Dependencies

```gradle
implementation("com.squareup.okhttp3:okhttp:4.12.0")
implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
implementation("io.coil-kt:coil:2.6.0")
implementation("androidx.media3:media3-exoplayer:1.3.1")
implementation("androidx.media3:media3-ui:1.3.1")
```

### Permission

```xml
<uses-permission android:name="android.permission.INTERNET" />
```

### Api.kt

```kotlin
import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit

object Api {
    const val BASE = "https://YOUR-SERVICE.onrender.com"
    const val API_KEY = ""

    private val client = OkHttpClient.Builder()
        .connectTimeout(60, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.MINUTES)
        .writeTimeout(10, TimeUnit.MINUTES)
        .build()

    suspend fun upload(context: Context, uri: Uri, type: String): String =
        withContext(Dispatchers.IO) {
            val resolver = context.contentResolver
            val mime = resolver.getType(uri) ?: "application/octet-stream"
            var name = "file"
            resolver.query(uri, null, null, null, null)?.use { c ->
                val i = c.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                if (i >= 0 && c.moveToFirst()) name = c.getString(i)
            }
            val bytes = resolver.openInputStream(uri)?.use { it.readBytes() }
                ?: throw Exception("Cannot read file")
            val body = MultipartBody.Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart("file", name, bytes.toRequestBody(mime.toMediaType()))
                .build()
            val builder = Request.Builder().url("$BASE/upload/$type").post(body)
            if (API_KEY.isNotEmpty()) builder.header("X-API-Key", API_KEY)
            client.newCall(builder.build()).execute().use { r ->
                val text = r.body?.string().orEmpty()
                val obj = if (text.isNotEmpty()) JSONObject(text) else JSONObject()
                if (!r.isSuccessful) throw Exception(obj.optString("detail", "REQUEST_FAILED"))
                obj.getString("url")
            }
        }
}
```

`type` is `image`, `video` or `file`.

### MainActivity.kt

```kotlin
import android.net.Uri
import android.os.Bundle
import android.widget.ImageView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import coil.load
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {

    private lateinit var imageView: ImageView

    private val pickImage = registerForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (uri != null) uploadMedia(uri, "image")
    }

    private val pickVideo = registerForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (uri != null) uploadMedia(uri, "video")
    }

    private val pickFile = registerForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (uri != null) uploadMedia(uri, "file")
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        imageView = ImageView(this)
        setContentView(imageView)
    }

    private fun uploadMedia(uri: Uri, type: String) {
        lifecycleScope.launch {
            try {
                val url = Api.upload(this@MainActivity, uri, type)
                if (type == "image") imageView.load(url)
                Toast.makeText(this@MainActivity, url, Toast.LENGTH_LONG).show()
            } catch (e: Exception) {
                Toast.makeText(this@MainActivity, e.message, Toast.LENGTH_LONG).show()
            }
        }
    }

    private fun chooseImage() = pickImage.launch("image/*")
    private fun chooseVideo() = pickVideo.launch("video/*")
    private fun chooseFile() = pickFile.launch("*/*")
}
```

### Show an uploaded video

```kotlin
import androidx.media3.common.MediaItem
import androidx.media3.exoplayer.ExoPlayer

val player = ExoPlayer.Builder(this).build()
playerView.player = player
player.setMediaItem(MediaItem.fromUri(url))
player.prepare()
player.play()
```

### Open or download a file

```kotlin
import android.content.Intent
import android.net.Uri

startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
```

## Website (JavaScript)

### api.js

```javascript
const BASE = "https://YOUR-SERVICE.onrender.com";
const API_KEY = "";

export async function upload(type, file) {
  const form = new FormData();
  form.append("file", file);
  const headers = API_KEY ? { "X-API-Key": API_KEY } : {};
  const res = await fetch(BASE + "/upload/" + type, {
    method: "POST",
    headers,
    body: form,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "REQUEST_FAILED");
  return data.url;
}
```

### Usage

```html
<input type="file" id="picker">
<button id="send">Upload image</button>
<img id="preview" width="300">

<script type="module">
  import { upload } from "./api.js";

  document.getElementById("send").onclick = async () => {
    try {
      const file = document.getElementById("picker").files[0];
      const url = await upload("image", file);
      document.getElementById("preview").src = url;
    } catch (e) {
      alert(e.message);
    }
  };
</script>
```

Use `upload("video", file)` for videos and `upload("file", file)` for documents.

### Show media

```html
<img src="https://durbar-plus2.vercel.app/img/TOKEN.jpg">

<video src="https://durbar-plus2.vercel.app/vid/TOKEN.mp4" controls></video>

<a href="https://durbar-plus2.vercel.app/file/TOKEN.pdf">Download</a>
```

## Security notes

- `UPLOAD_API_KEY` is optional. If it is empty, anyone who knows your Render URL can upload to your imgbb and Cloudinary accounts.
- A key placed inside an app or website can be extracted. It stops casual abuse, not a determined attacker.
- The `/img`, `/vid` and `/file` routes only fetch from your own imgbb and Cloudinary accounts. Tokens pointing anywhere else return 404.
- HTML and SVG files are never served inline from your domain. They are forced to download.
- Links created by older versions of this backend (the ones that used a database) no longer work. New uploads do not need any database.

## Rules

- Upload requests go to the Render URL. Never send uploads through Vercel, because Vercel limits request body size.
- The first request after Render has been idle can take up to a minute on the free tier. Use long timeouts on uploads.

## Deployment

### Render

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Environment variables:

| Name                          | Required | Description                                  |
|-------------------------------|----------|----------------------------------------------|
| `IMGBB_KEY`                   | yes      | imgbb API key                                |
| `CLOUDINARY_VIDEO_CLOUD_NAME` | yes      | Cloudinary cloud name for videos             |
| `CLOUDINARY_VIDEO_PRESET`     | yes      | Unsigned upload preset for videos            |
| `CLOUDINARY_FILE_CLOUD_NAME`  | yes      | Cloudinary cloud name for files              |
| `CLOUDINARY_FILE_PRESET`      | yes      | Unsigned upload preset for files             |
| `PUBLIC_BASE_URL`             | no       | Defaults to `https://durbar-plus2.vercel.app` |
| `UPLOAD_API_KEY`              | no       | If set, uploads require `X-API-Key`          |

### requirements.txt

```
fastapi
uvicorn
httpx
python-multipart
```

### Vercel

Add this `vercel.json` to the root of the project that hosts `durbar-plus2.vercel.app`, then redeploy:

```json
{
  "rewrites": [
    { "source": "/img/:path*", "destination": "https://YOUR-SERVICE.onrender.com/img/:path*" },
    { "source": "/vid/:path*", "destination": "https://YOUR-SERVICE.onrender.com/vid/:path*" },
    { "source": "/file/:path*", "destination": "https://YOUR-SERVICE.onrender.com/file/:path*" }
  ]
}
```

### Cloudinary

Create an unsigned upload preset in each Cloudinary account (one for videos, one for files) and put its name in the matching `*_PRESET` variable.