import { Router } from "express";
import multer from "multer";
import { v2 as cloudinary } from "cloudinary";

const router = Router();

const account = () => {
  const cloud_name = process.env.FILES_CLOUD_NAME;
  const api_key = process.env.FILES_API_KEY;
  const api_secret = process.env.FILES_API_SECRET;
  if (!cloud_name || !api_key || !api_secret) {
    const error = new Error("Files Cloudinary is not configured");
    error.status = 500;
    throw error;
  }
  return { cloud_name, api_key, api_secret, secure: true };
};

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 10 * 1024 * 1024, files: 1 }
});

router.post("/", upload.single("file"), async (req, res, next) => {
  try {
    const creds = account();
    if (!req.file) {
      return res.status(400).json({ success: false, error: "Send a file in the 'file' field" });
    }

    const result = await new Promise((resolve, reject) => {
      const stream = cloudinary.uploader.upload_stream(
        {
          ...creds,
          folder: req.body.folder || "files",
          resource_type: "raw",
          use_filename: true,
          unique_filename: true
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
        name: req.file.originalname,
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
      resource_type: "raw"
    });
    res.json({ success: true, data: { publicId, result: result.result } });
  } catch (err) {
    next(err);
  }
});

export default router;