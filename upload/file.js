const express = require("express");
const multer = require("multer");
const { uploadCloudinary } = require("../lib/cloudinary");

const router = express.Router();

const upload = multer({
  storage: multer.memoryStorage(),
  limits: {
    fileSize: 10 * 1024 * 1024
  }
});

router.post("/", upload.single("file"), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({
        success: false,
        message: "File is required"
      });
    }

    const result = await uploadCloudinary(req.file, "file");

    return res.status(200).json({
      success: true,
      message: "File uploaded successfully",
      type: "file",
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
        "File upload failed"
    });
  }
});

module.exports = router;