# Durbar Media Backend

Auth, image, video and file upload API. Hosted on Render, served through `https://durbar-plus2.vercel.app`.

## How it works

- Auth and uploads go directly to your Render URL.
- Uploaded media is viewed through your Vercel domain.
- Images are stored on imgbb. Videos and files are stored on separate Cloudinary accounts.
- Every upload returns a link on your own domain.

| Type  | View URL                                          |
|-------|---------------------------------------------------|
| Image | https://durbar-plus2.vercel.app/img/filename.ext  |
| Video | https://durbar-plus2.vercel.app/vid/filename.ext  |
| File  | https://durbar-plus2.vercel.app/file/filename.ext |

Replace `https://YOUR-SERVICE.onrender.com` below with your real Render URL.

## Limits

| Type  | Max size |
|-------|----------|
| Image | 32 MB    |
| Video | 100 MB   |
| File  | 10 MB    |

## API

### Register

`POST /auth/register`

```json
{ "email": "a@b.com", "password": "123456", "name": "Dar" }
```

### Login

`POST /auth/login`

```json
{ "email": "a@b.com", "password": "123456" }
```

### Refresh token

`POST /auth/refresh`

```json
{ "refreshToken": "..." }
```

Register and login return:

```json
{
  "uid": "...",
  "idToken": "...",
  "refreshToken": "...",
  "expiresIn": "3600",
  "profile": { "name": "Dar", "email": "a@b.com", "createdAt": 1700000000000 }
}
```

The `idToken` expires after one hour. Call `/auth/refresh` to get a new one.

### Upload

| Endpoint            | Field  |
|---------------------|--------|
| `POST /upload/image`| `file` |
| `POST /upload/video`| `file` |
| `POST /upload/file` | `file` |

Send as `multipart/form-data` with the header `Authorization: Bearer <idToken>`.

Response:

```json
{
  "url": "https://durbar-plus2.vercel.app/img/Ab3dE9xQ2kLm.jpg",
  "id": "Ab3dE9xQ2kLm",
  "name": "photo.jpg",
  "size": 245678
}
```

Save the returned `url` in your own database (for example in a post or profile) and use it directly.

### Errors

Errors return an HTTP status and:

```json
{ "detail": "EMAIL_EXISTS" }
```

Common values: `EMAIL_EXISTS`, `INVALID_LOGIN_CREDENTIALS`, `WEAK_PASSWORD : Password should be at least 6 characters`, `Invalid token`, `File too large`, `Not an image`, `Not a video`.

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
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit

object Api {
    const val BASE = "https://YOUR-SERVICE.onrender.com"

    private val client = OkHttpClient.Builder()
        .connectTimeout(60, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.MINUTES)
        .writeTimeout(10, TimeUnit.MINUTES)
        .build()

    private val json = "application/json".toMediaType()

    class ApiException(message: String) : Exception(message)

    private fun send(request: Request): JSONObject {
        client.newCall(request).execute().use { r ->
            val text = r.body?.string().orEmpty()
            val obj = if (text.isNotEmpty()) JSONObject(text) else JSONObject()
            if (!r.isSuccessful) throw ApiException(obj.optString("detail", "REQUEST_FAILED"))
            return obj
        }
    }

    fun register(email: String, password: String, name: String): JSONObject {
        val body = JSONObject().put("email", email).put("password", password).put("name", name)
        return send(
            Request.Builder().url("$BASE/auth/register")
                .post(body.toString().toRequestBody(json)).build()
        )
    }

    fun login(email: String, password: String): JSONObject {
        val body = JSONObject().put("email", email).put("password", password)
        return send(
            Request.Builder().url("$BASE/auth/login")
                .post(body.toString().toRequestBody(json)).build()
        )
    }

    fun refresh(refreshToken: String): JSONObject {
        val body = JSONObject().put("refreshToken", refreshToken)
        return send(
            Request.Builder().url("$BASE/auth/refresh")
                .post(body.toString().toRequestBody(json)).build()
        )
    }

    fun upload(context: Context, uri: Uri, type: String, idToken: String): String {
        val resolver = context.contentResolver
        val mime = resolver.getType(uri) ?: "application/octet-stream"
        var name = "file"
        resolver.query(uri, null, null, null, null)?.use { c ->
            val i = c.getColumnIndex(OpenableColumns.DISPLAY_NAME)
            if (i >= 0 && c.moveToFirst()) name = c.getString(i)
        }
        val bytes = resolver.openInputStream(uri)?.use { it.readBytes() }
            ?: throw ApiException("Cannot read file")
        val body = MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart("file", name, bytes.toRequestBody(mime.toMediaType()))
            .build()
        val request = Request.Builder()
            .url("$BASE/upload/$type")
            .header("Authorization", "Bearer $idToken")
            .post(body)
            .build()
        return send(request).getString("url")
    }
}
```

`type` is `image`, `video` or `file`.

### Session.kt

```kotlin
import android.content.Context
import org.json.JSONObject

object Session {
    private fun prefs(c: Context) = c.getSharedPreferences("session", Context.MODE_PRIVATE)

    fun save(c: Context, r: JSONObject) {
        prefs(c).edit()
            .putString("uid", r.getString("uid"))
            .putString("idToken", r.getString("idToken"))
            .putString("refreshToken", r.getString("refreshToken"))
            .putLong("expiresAt", System.currentTimeMillis() + r.getString("expiresIn").toLong() * 1000 - 60000)
            .apply()
    }

    fun uid(c: Context) = prefs(c).getString("uid", null)

    fun clear(c: Context) = prefs(c).edit().clear().apply()

    fun token(c: Context): String? {
        val p = prefs(c)
        val token = p.getString("idToken", null) ?: return null
        if (System.currentTimeMillis() < p.getLong("expiresAt", 0)) return token
        val refresh = p.getString("refreshToken", null) ?: return null
        val r = Api.refresh(refresh)
        save(c, r)
        return r.getString("idToken")
    }
}
```

`Session.token()` makes a network call when the token is expired, so call it from a background thread.

### Usage in an Activity

```kotlin
import android.net.Uri
import android.os.Bundle
import android.widget.ImageView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import coil.load
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

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

    private fun register(email: String, password: String, name: String) {
        lifecycleScope.launch {
            try {
                val r = withContext(Dispatchers.IO) { Api.register(email, password, name) }
                Session.save(this@MainActivity, r)
            } catch (e: Exception) {
                Toast.makeText(this@MainActivity, e.message, Toast.LENGTH_LONG).show()
            }
        }
    }

    private fun login(email: String, password: String) {
        lifecycleScope.launch {
            try {
                val r = withContext(Dispatchers.IO) { Api.login(email, password) }
                Session.save(this@MainActivity, r)
            } catch (e: Exception) {
                Toast.makeText(this@MainActivity, e.message, Toast.LENGTH_LONG).show()
            }
        }
    }

    private fun uploadMedia(uri: Uri, type: String) {
        lifecycleScope.launch {
            try {
                val url = withContext(Dispatchers.IO) {
                    val token = Session.token(this@MainActivity) ?: throw Exception("Not logged in")
                    Api.upload(this@MainActivity, uri, type, token)
                }
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
import androidx.media3.ui.PlayerView

val player = ExoPlayer.Builder(this).build()
playerView.player = player
player.setMediaItem(MediaItem.fromUri("https://durbar-plus2.vercel.app/vid/Ab3dE9xQ2kLm.mp4"))
player.prepare()
player.play()
```

Seeking works because the backend supports Range requests.

### Open or download a file

```kotlin
import android.content.Intent
import android.net.Uri

startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("https://durbar-plus2.vercel.app/file/Ab3dE9xQ2kLm.pdf")))
```

## Website (JavaScript)

### api.js

```javascript
const BASE = "https://YOUR-SERVICE.onrender.com";

async function request(path, options) {
  const res = await fetch(BASE + path, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "REQUEST_FAILED");
  return data;
}

function saveSession(r) {
  localStorage.setItem("uid", r.uid);
  localStorage.setItem("idToken", r.idToken);
  localStorage.setItem("refreshToken", r.refreshToken);
  localStorage.setItem("expiresAt", String(Date.now() + Number(r.expiresIn) * 1000 - 60000));
}

export async function register(email, password, name) {
  const r = await request("/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, name }),
  });
  saveSession(r);
  return r;
}

export async function login(email, password) {
  const r = await request("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  saveSession(r);
  return r;
}

export function logout() {
  localStorage.removeItem("uid");
  localStorage.removeItem("idToken");
  localStorage.removeItem("refreshToken");
  localStorage.removeItem("expiresAt");
}

async function getToken() {
  const token = localStorage.getItem("idToken");
  if (!token) throw new Error("Not logged in");
  if (Date.now() < Number(localStorage.getItem("expiresAt"))) return token;
  const r = await request("/auth/refresh", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refreshToken: localStorage.getItem("refreshToken") }),
  });
  saveSession(r);
  return r.idToken;
}

export async function upload(type, file) {
  const token = await getToken();
  const form = new FormData();
  form.append("file", file);
  const r = await request("/upload/" + type, {
    method: "POST",
    headers: { Authorization: "Bearer " + token },
    body: form,
  });
  return r.url;
}
```

### Usage

```html
<input type="file" id="picker">
<button id="send">Upload image</button>
<img id="preview" width="300">

<script type="module">
  import { login, upload } from "./api.js";

  document.getElementById("send").onclick = async () => {
    try {
      await login("a@b.com", "123456");
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
<img src="https://durbar-plus2.vercel.app/img/Ab3dE9xQ2kLm.jpg">

<video src="https://durbar-plus2.vercel.app/vid/Ab3dE9xQ2kLm.mp4" controls></video>

<a href="https://durbar-plus2.vercel.app/file/Ab3dE9xQ2kLm.pdf">Download</a>
```

## Rules

- Upload and auth requests go to the Render URL. Never send uploads through Vercel, because Vercel limits request body size.
- Only the returned `/img`, `/vid` and `/file` links use the Vercel domain.
- The first request after Render has been idle can take up to a minute on the free tier. Use long timeouts on uploads.
- Use `/auth/refresh` before the token expires instead of asking the user to log in again.

## Deployment

### Render

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Environment variables:
  - `FIREBASE_API_KEY`
  - `FIREBASE_DB_URL`
  - `IMGBB_KEY`
  - `CLOUDINARY_VIDEO_CLOUD_NAME`
  - `CLOUDINARY_VIDEO_PRESET`
  - `CLOUDINARY_FILE_CLOUD_NAME`
  - `CLOUDINARY_FILE_PRESET`
  - `PUBLIC_BASE_URL` = `https://durbar-plus2.vercel.app`

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

### Firebase

Enable Email/Password sign-in under Authentication, create a Realtime Database, and publish the rules shared earlier.