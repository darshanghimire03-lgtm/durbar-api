import { Router } from "express";
import multer from "multer";
import { v2 as cloudinary } from "cloudinary";

const router = Router();

const account = () => {
  const cloud_name = process.env.VIDEO_CLOUD_NAME;
  const api_key = process.env.VIDEO_API_KEY;
  const api_secret = process.env.VIDEO_API_SECRET;
  if (!cloud_name || !api_key || !api_secret) {
    const error = new Error("Video Cloudinary is not configured");
    error.status = 500;
    throw error;
  }
  return { cloud_name, api_key, api_secret, secure: true };
};

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 100 * 1024 * 1024, files: 1 },
  fileFilter: (req, file, cb) => {
    if (!file.mimetype.startsWith("video/")) {
      const error = new Error("Only video files are allowed");
      error.status = 400;
      return cb(error);
    }
    cb(null, true);
  }
});

router.post("/", upload.single("file"), async (req, res, next) => {
  try {
    const creds = account();
    if (!req.file) {
      return res.status(400).json({ success: false, error: "Send a video in the 'file' field" });
    }

    const result = await new Promise((resolve, reject) => {
      const stream = cloudinary.uploader.upload_stream(
        {
          ...creds,
          folder: req.body.folder || "videos",
          resource_type: "video"
        },
        (err, data) => (err ? reject(err) : resolve(data))
      );
      stream.end(req.file.buffer);
    });

    res.status(201).json({
      success: true,
      data: {
        url: result.secure_url,
        publicId: result.public_id,
        format: result.format,
        duration: result.duration,
        width: result.width,
        height: result.height,
        bytes: result.bytes
      }
    });
  } catch (err) {
    next(err);
  }
});

router.delete("/", async (req, res, next) => {
  try {
    const creds = account();
    const publicId = req.body?.publicId || req.query.publicId;
    if (!publicId) {
      return res.status(400).json({ success: false, error: "publicId is required" });
    }
    const result = await cloudinary.uploader.destroy(publicId, {
      ...creds,
      resource_type: "video"
    });
    res.json({ success: true, data: { publicId, result: result.result } });
  } catch (err) {
    next(err);
  }
});

export default router;