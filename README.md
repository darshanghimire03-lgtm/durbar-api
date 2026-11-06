# durbar-api

Upload API for images, videos and files.

| Type | Route | Storage | Max size |
|---|---|---|---|
| Image | `POST /api/image` | ImgBB | 32 MB |
| Video | `POST /api/video` | Cloudinary (video account) | 100 MB |
| File | `POST /api/files` | Cloudinary (files account) | 10 MB |
| Delete video | `DELETE /api/video?publicId=...` | Cloudinary (video account) | |
| Delete file | `DELETE /api/files?publicId=...` | Cloudinary (files account) | |

All routes need the header `x-api-key: YOUR_API_KEY`.
Send the file in a multipart field named `file`.

## Setup

```bash
npm install
cp .env.example .env
npm run dev
```

Deploy on Render with the included `render.yaml` and add the env vars from `.env.example`.

## Response

Success:

```json
{
  "success": true,
  "data": {
    "url": "https://...",
    "publicId": "videos/abc123"
  }
}
```

Error:

```json
{
  "success": false,
  "error": "Unauthorized"
}
```

Image responses contain `id`, `url`, `displayUrl`, `thumbUrl`, `deleteUrl`, `width`, `height`, `bytes`.
Video and file responses contain `url`, `publicId`, `bytes` (videos also have `duration`, `width`, `height`, `format`).

## Web (JavaScript)

```js
const BASE_URL = "https://durbar-api.onrender.com";
const API_KEY = "YOUR_API_KEY";

async function upload(type, file) {
  const form = new FormData();
  form.append("file", file);

  const res = await fetch(`${BASE_URL}/api/${type}`, {
    method: "POST",
    headers: { "x-api-key": API_KEY },
    body: form
  });

  const json = await res.json();
  if (!res.ok) throw new Error(json.error);
  return json.data;
}

async function remove(type, publicId) {
  const res = await fetch(
    `${BASE_URL}/api/${type}?publicId=${encodeURIComponent(publicId)}`,
    { method: "DELETE", headers: { "x-api-key": API_KEY } }
  );
  const json = await res.json();
  if (!res.ok) throw new Error(json.error);
  return json.data;
}
```

Usage:

```html
<input type="file" id="picker" />
<script>
  document.getElementById("picker").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    const data = await upload("image", file);
    console.log(data.url);
  });
</script>
```

Use `"image"`, `"video"` or `"files"` as the type.

## Android (Kotlin)

`build.gradle.kts`:

```kotlin
dependencies {
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
}
```

`AndroidManifest.xml`:

```xml
<uses-permission android:name="android.permission.INTERNET" />
```

`DurbarApi.kt`:

```kotlin
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.asRequestBody
import org.json.JSONObject
import java.io.File
import java.net.URLConnection
import java.net.URLEncoder

object DurbarApi {
    private const val BASE_URL = "https://durbar-api.onrender.com"
    private const val API_KEY = "YOUR_API_KEY"
    private val client = OkHttpClient()

    private fun upload(type: String, file: File): JSONObject {
        val mime = URLConnection.guessContentTypeFromName(file.name) ?: "application/octet-stream"
        val body = MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart("file", file.name, file.asRequestBody(mime.toMediaType()))
            .build()

        val request = Request.Builder()
            .url("$BASE_URL/api/$type")
            .header("x-api-key", API_KEY)
            .post(body)
            .build()

        client.newCall(request).execute().use { response ->
            val json = JSONObject(response.body?.string().orEmpty())
            if (!response.isSuccessful) throw Exception(json.optString("error"))
            return json.getJSONObject("data")
        }
    }

    private fun remove(type: String, publicId: String): JSONObject {
        val id = URLEncoder.encode(publicId, "UTF-8")
        val request = Request.Builder()
            .url("$BASE_URL/api/$type?publicId=$id")
            .header("x-api-key", API_KEY)
            .delete()
            .build()

        client.newCall(request).execute().use { response ->
            val json = JSONObject(response.body?.string().orEmpty())
            if (!response.isSuccessful) throw Exception(json.optString("error"))
            return json.getJSONObject("data")
        }
    }

    fun uploadImage(file: File) = upload("image", file)
    fun uploadVideo(file: File) = upload("video", file)
    fun uploadFile(file: File) = upload("files", file)
    fun deleteVideo(publicId: String) = remove("video", publicId)
    fun deleteFile(publicId: String) = remove("files", publicId)
}
```

Usage (network calls must run off the main thread):

```kotlin
lifecycleScope.launch {
    val data = withContext(Dispatchers.IO) {
        DurbarApi.uploadImage(File(path))
    }
    val url = data.getString("url")
}
```

## iOS and Android (Dart / Flutter)

`pubspec.yaml`:

```yaml
dependencies:
  http: ^1.2.0
```

`durbar_api.dart`:

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;

class DurbarApi {
  static const baseUrl = 'https://durbar-api.onrender.com';
  static const apiKey = 'YOUR_API_KEY';

  static Future<Map<String, dynamic>> _upload(String type, String path) async {
    final request = http.MultipartRequest('POST', Uri.parse('$baseUrl/api/$type'))
      ..headers['x-api-key'] = apiKey
      ..files.add(await http.MultipartFile.fromPath('file', path));

    final response = await http.Response.fromStream(await request.send());
    final json = jsonDecode(response.body) as Map<String, dynamic>;
    if (response.statusCode >= 400) throw Exception(json['error']);
    return json['data'] as Map<String, dynamic>;
  }

  static Future<Map<String, dynamic>> _remove(String type, String publicId) async {
    final uri = Uri.parse('$baseUrl/api/$type').replace(queryParameters: {'publicId': publicId});
    final response = await http.delete(uri, headers: {'x-api-key': apiKey});
    final json = jsonDecode(response.body) as Map<String, dynamic>;
    if (response.statusCode >= 400) throw Exception(json['error']);
    return json['data'] as Map<String, dynamic>;
  }

  static Future<Map<String, dynamic>> uploadImage(String path) => _upload('image', path);
  static Future<Map<String, dynamic>> uploadVideo(String path) => _upload('video', path);
  static Future<Map<String, dynamic>> uploadFile(String path) => _upload('files', path);
  static Future<Map<String, dynamic>> deleteVideo(String id) => _remove('video', id);
  static Future<Map<String, dynamic>> deleteFile(String id) => _remove('files', id);
}
```

Usage:

```dart
final data = await DurbarApi.uploadImage(pickedFile.path);
final url = data['url'];
```

Android release builds need the internet permission in `android/app/src/main/AndroidManifest.xml`:

```xml
<uses-permission android:name="android.permission.INTERNET" />
```

iOS needs no extra setup because the API uses HTTPS.

## Notes

- The free Render plan sleeps when idle, so the first request can take about 30 seconds.
- Do not ship `API_KEY` inside a public app or website. Anyone can extract it. For public clients, call this API from your own backend.
- Common errors: `401 Unauthorized` (wrong or missing key), `400` (wrong file type or missing `file` field), `413` (file too large), `500 ... is not configured` (missing env vars on Render).