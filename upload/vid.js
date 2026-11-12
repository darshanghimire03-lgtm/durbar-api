const express = require("express");
const multer = require("multer");
const { uploadCloudinary } = require("../lib/cloudinary");

const router = express.Router();

const upload = multer({
  storage: multer.memoryStorage(),
  limits: {
    fileSize: 100 * 1024 * 1024
  },
  fileFilter: (req, file, callback) => {
    if (!file.mimetype.startsWith("video/")) {
      return callback(new Error("Only video files are allowed"));
    }

    callback(null, true);
  }
});

router.post("/", upload.single("file"), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({
        success: false,
        message: "Video file is required"
      });
    }

    const result = await uploadCloudinary(req.file, "video");

    return res.status(200).json({
      success: true,
      message: "Video uploaded successfully",
      type: "video",
      name: result.name,
      url: result.url,
      publicId: result.publicId,
      format: result.format,
      bytes: result.bytes,
      customUrl: false,
      storage: "Cloudinary"
    });

  } catch (error) {
    return res.status(500).json({
      success: false,
      message:
        error.response?.data?.error?.message ||
        error.message ||
        "Video upload failed"
    });
  }
});

module.exports = router;