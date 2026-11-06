import { Router } from "express";
import multer from "multer";

const router = Router();

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 32 * 1024 * 1024, files: 1 },
  fileFilter: (req, file, cb) => {
    if (!file.mimetype.startsWith("image/")) {
      const error = new Error("Only image files are allowed");
      error.status = 400;
      return cb(error);
    }
    cb(null, true);
  }
});

router.post("/", upload.single("file"), async (req, res, next) => {
  try {
    if (!process.env.IMGBB_API_KEY) {
      const error = new Error("ImgBB is not configured");
      error.status = 500;
      throw error;
    }
    if (!req.file) {
      return res.status(400).json({ success: false, error: "Send an image in the 'file' field" });
    }

    const body = new URLSearchParams();
    body.set("image", req.file.buffer.toString("base64"));
    body.set("name", req.body.name || req.file.originalname);

    const query = new URLSearchParams({ key: process.env.IMGBB_API_KEY });
    const expiration = Number(req.body.expiration);
    if (expiration >= 60 && expiration <= 15552000) {
      query.set("expiration", String(expiration));
    }

    const response = await fetch(`https://api.imgbb.com/1/upload?${query}`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body
    });

    const json = await response.json().catch(() => null);

    if (!response.ok || !json?.success) {
      const error = new Error(json?.error?.message || "ImgBB upload failed");
      error.status = response.status >= 400 ? response.status : 502;
      throw error;
    }

    const d = json.data;
    res.status(201).json({
      success: true,
      data: {
        id: d.id,
        url: d.url,
        displayUrl: d.display_url,
        thumbUrl: d.thumb?.url || null,
        deleteUrl: d.delete_url,
        width: d.width,
        height: d.height,
        bytes: d.size
      }
    });
  } catch (err) {
    next(err);
  }
});

export default router;