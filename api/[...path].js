
import Busboy from "busboy";
import path from "node:path";

const MAX_NAME = 150;
const MAX_UPLOAD = 3.5 * 1024 * 1024;
const BAD_CHARS = /[?&#\\%<>]/;
const UNSAFE_INLINE = new Set([
  "text/html",
  "application/xhtml+xml",
  "image/svg+xml"
]);

const config = {
  img: {
    cloud: process.env.CLOUDINARY_IMAGE_CLOUD_NAME || process.env.CLOUDINARY_FILE_CLOUD_NAME,
    preset: process.env.CLOUDINARY_IMAGE_PRESET || process.env.CLOUDINARY_FILE_PRESET,
    type: "image",
    limit: 10 * 1024 * 1024
  },
  vid: {
    cloud: process.env.CLOUDINARY_VIDEO_CLOUD_NAME,
    preset: process.env.CLOUDINARY_VIDEO_PRESET,
    type: "video",
    limit: 100 * 1024 * 1024
  },
  file: {
    cloud: process.env.CLOUDINARY_FILE_CLOUD_NAME,
    preset: process.env.CLOUDINARY_FILE_PRESET,
    type: "raw",
    limit: 10 * 1024 * 1024
  }
};

function json(res, status, data) {
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json");
  res.end(JSON.stringify(data));
}

function error(res, status, message) {
  json(res, status, { detail: message });
}

function validName(name) {
  return Boolean(
    name &&
    name !== "." &&
    name !== ".." &&
    !name.startsWith(".") &&
    name.length <= MAX_NAME &&
    !BAD_CHARS.test(name) &&
    [...name].every(char => char.charCodeAt(0) >= 32)
  );
}

function cleanName(raw) {
  const name = path.basename(String(raw || "").replaceAll("\\", "/")).trim();

  if (!validName(name)) {
    throw new Error("Invalid file name");
  }

  return name;
}

function numbered(name, number) {
  if (number === 0) return name;

  const ext = path.extname(name);
  const stem = name.slice(0, name.length - ext.length);
  const suffix = `-${number}`;

  return `${stem.slice(0, MAX_NAME - ext.length - suffix.length)}${suffix}${ext}`;
}

function publicId(kind, name) {
  if (kind === "file") return name;
  return name.slice(0, name.length - path.extname(name).length);
}

function deliveryUrl(kind, name) {
  const item = config[kind];
  const resource = item.type;
  const encoded = name.split("/").map(encodeURIComponent).join("/");
  return `https://res.cloudinary.com/${item.cloud}/${resource}/upload/${encoded}`;
}

function publicUrl(kind, name, req) {
  const base = (process.env.PUBLIC_BASE_URL || `${req.headers["x-forwarded-proto"] || "https"}://${req.headers.host}`).replace(/\/+$/, "");
  return `${base}/${kind}/${encodeURIComponent(name)}`;
}

function checkKey(req) {
  const expected = process.env.UPLOAD_API_KEY;

  if (expected && req.headers["x-api-key"] !== expected) {
    throw Object.assign(new Error("Invalid API key"), { status: 401 });
  }
}

function checkConfig(kind) {
  const item = config[kind];

  if (!item?.cloud || !item?.preset) {
    throw Object.assign(new Error(`Cloudinary configuration missing for ${kind}`), { status: 500 });
  }

  return item;
}

function readMultipart(req) {
  return new Promise((resolve, reject) => {
    let parser;

    try {
      parser = Busboy({
        headers: req.headers,
        limits: {
          files: 1,
          fileSize: MAX_UPLOAD,
          fields: 5
        }
      });
    } catch {
      reject(Object.assign(new Error("Expected multipart/form-data"), { status: 400 }));
      return;
    }

    let fileData = null;
    let fileName = "";
    let mime = "application/octet-stream";
    let failed = false;

    parser.on("file", (field, stream, info) => {
      if (field !== "file") {
        stream.resume();
        return;
      }

      fileName = info.filename;
      mime = info.mimeType || mime;

      const chunks = [];

      stream.on("data", chunk => chunks.push(chunk));

      stream.on("limit", () => {
        failed = true;
        reject(Object.assign(new Error("File exceeds the Vercel upload limit of 3.5 MB"), { status: 413 }));
      });

      stream.on("end", () => {
        if (!failed) fileData = Buffer.concat(chunks);
      });
    });

    parser.on("filesLimit", () => {
      failed = true;
      reject(Object.assign(new Error("Only one file is allowed"), { status: 400 }));
    });

    parser.on("error", reject);

    parser.on("finish", () => {
      if (failed) return;

      if (!fileData?.length) {
        reject(Object.assign(new Error("Empty file"), { status: 400 }));
        return;
      }

      resolve({ data: fileData, name: fileName, mime });
    });

    req.pipe(parser);
  });
}

async function exists(kind, name) {
  const response = await fetch(deliveryUrl(kind, name), {
    method: "HEAD",
    redirect: "manual"
  });

  return response.ok;
}

async function getUniqueName(kind, original) {
  for (let i = 0; i < 1000; i++) {
    const candidate = numbered(original, i);

    if (!(await exists(kind, candidate))) {
      return candidate;
    }
  }

  throw Object.assign(new Error("Too many files with this name"), { status: 409 });
}

async function uploadToCloudinary(kind, name, data, mime) {
  const item = checkConfig(kind);
  const resource = item.type;

  const form = new FormData();

  form.append("upload_preset", item.preset);
  form.append("public_id", publicId(kind, name));
  form.append("overwrite", "false");
  form.append("unique_filename", "false");
  form.append("use_filename", "false");
  form.append("file", new Blob([data], { type: mime }), name);

  const response = await fetch(
    `https://api.cloudinary.com/v1_1/${item.cloud}/${resource}/upload`,
    {
      method: "POST",
      body: form,
      signal: AbortSignal.timeout(60000)
    }
  );

  const result = await response.json();

  if (!response.ok) {
    throw Object.assign(
      new Error(result?.error?.message || "Cloudinary upload failed"),
      { status: 502 }
    );
  }

  if (result.public_id !== publicId(kind, name)) {
    throw Object.assign(new Error("Cloudinary changed the file name"), { status: 502 });
  }

  return result;
}

async function upload(kind, req, res) {
  checkKey(req);
  const item = checkConfig(kind);
  const { data, name: original, mime } = await readMultipart(req);

  if (data.length > Math.min(item.limit, MAX_UPLOAD)) {
    return error(res, 413, "File too large for this Vercel upload endpoint. Use direct Cloudinary upload.");
  }

  let name;

  try {
    name = cleanName(original);
  } catch (e) {
    return error(res, 400, e.message);
  }

  if (kind === "img" && !mime.startsWith("image/")) {
    return error(res, 400, "Not an image");
  }

  if (kind === "vid" && !mime.startsWith("video/")) {
    return error(res, 400, "Not a video");
  }

  if (kind !== "file" && !path.extname(name)) {
    return error(res, 400, "File name needs an extension");
  }

  for (let attempt = 0; attempt < 1000; attempt++) {
    const candidate = numbered(name, attempt);

    if (await exists(kind, candidate)) continue;

    try {
      await uploadToCloudinary(kind, candidate, data, mime);

      return json(res, 200, {
        url: publicUrl(kind, candidate, req),
        name: candidate
      });
    } catch (e) {
      if (e.status === 409) continue;
      throw e;
    }
  }

  return error(res, 409, "Too many files with this name");
}

async function directConfig(kind, req, res) {
  checkKey(req);

  const item = checkConfig(kind);

  let body = "";

  for await (const chunk of req) {
    body += chunk.toString();

    if (body.length > 10000) {
      return error(res, 413, "Request too large");
    }
  }

  let input;

  try {
    input = JSON.parse(body);
  } catch {
    return error(res, 400, "Invalid JSON");
  }

  let name;

  try {
    name = cleanName(input.name);
  } catch (e) {
    return error(res, 400, e.message);
  }

  if (kind !== "file" && !path.extname(name)) {
    return error(res, 400, "File name needs an extension");
  }

  for (let i = 0; i < 1000; i++) {
    const candidate = numbered(name, i);

    if (await exists(kind, candidate)) continue;

    return json(res, 200, {
      uploadUrl: `https://api.cloudinary.com/v1_1/${item.cloud}/${item.type}/upload`,
      cloudName: item.cloud,
      resourceType: item.type,
      uploadPreset: item.preset,
      publicId: publicId(kind, candidate),
      name: candidate,
      url: publicUrl(kind, candidate, req),
      maxSize: item.limit
    });
  }

  return error(res, 409, "Too many files with this name");
}

function serve(kind, name, req, res) {
  if (!validName(name)) {
    return error(res, 404, "Not found");
  }

  if (kind !== "file" && !path.extname(name)) {
    return error(res, 404, "Not found");
  }

  const target = deliveryUrl(kind, name);

  res.statusCode = 302;
  res.setHeader("Location", target);
  res.setHeader("Cache-Control", "public, max-age=31536000, immutable");
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Accept-Ranges", "bytes");
  res.setHeader("X-Content-Type-Options", "nosniff");
  res.end();
}

export default async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, X-API-Key, Range");
  res.setHeader("Access-Control-Expose-Headers", "Content-Range, Accept-Ranges, Content-Length");

  if (req.method === "OPTIONS") {
    res.statusCode = 204;
    return res.end();
  }

  const pathname = new URL(req.url, `https://${req.headers.host || "localhost"}`).pathname;
  const parts = pathname.split("/").filter(Boolean);

  if (pathname === "/" || pathname === "/api") {
    return json(res, 200, {
      ok: true,
      name: "Durbar Upload API",
      version: "2.0.0",
      runtime: "Node.js",
      endpoints: [
        "POST /upload/image",
        "POST /upload/video",
        "POST /upload/file",
        "POST /upload/direct/image",
        "POST /upload/direct/video",
        "POST /upload/direct/file",
        "GET /img/:name",
        "GET /vid/:name",
        "GET /file/:name"
      ]
    });
  }

  if (parts.length === 2 && parts[0] === "upload" && ["image", "video", "file"].includes(parts[1]) && req.method === "POST") {
    const kind = { image: "img", video: "vid", file: "file" }[parts[1]];

    try {
      return await upload(kind, req, res);
    } catch (e) {
      return error(res, e.status || 502, e.message || "Upload failed");
    }
  }

  if (parts.length === 3 && parts[0] === "upload" && parts[1] === "direct" && ["image", "video", "file"].includes(parts[2]) && req.method === "POST") {
    const kind = { image: "img", video: "vid", file: "file" }[parts[2]];

    try {
      return await directConfig(kind, req, res);
    } catch (e) {
      return error(res, e.status || 502, e.message || "Unable to prepare upload");
    }
  }

  if (parts.length >= 2 && ["img", "vid", "file"].includes(parts[0]) && ["GET", "HEAD"].includes(req.method)) {
    const kind = parts[0];
    const name = decodeURIComponent(parts.slice(1).join("/"));

    return serve(kind, name, req, res);
  }

  return error(res, 404, "Route not found");
}
