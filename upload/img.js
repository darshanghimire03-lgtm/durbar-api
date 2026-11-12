const express = require("express");
const axios = require("axios");
const FormData = require("form-data");
const multer = require("multer");
const { createImageLink } = require("../lib/links");

const router = express.Router();

const upload = multer({
  storage: multer.memoryStorage(),
  limits: {
    fileSize: 10 * 1024 * 1024
  },
  fileFilter: (req, file, callback) => {
    if (!file.mimetype.startsWith("image/")) {
      return callback(new Error("Only image files are allowed"));
    }

    callback(null, true);
  }
});

router.post("/", upload.single("file"), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({
        success: false,
        message: "Image file is required"
      });
    }

    const apiKey = process.env.IMGBB_API_KEY;

    if (!apiKey) {
      return res.status(500).json({
        success: false,
        message: "IMGBB_API_KEY environment variable is missing"
      });
    }

    const form = new FormData();

    form.append("image", req.file.buffer.toString("base64"));
    form.append("name", req.file.originalname);

    const response = await axios.post(
      `https://api.imgbb.com/1/upload?key=${apiKey}`,
      form,
      {
        headers: form.getHeaders(),
        timeout: 120000
      }
    );

    const originalUrl = response.data.data.url;
    const custom = createImageLink(originalUrl);

    return res.status(200).json({
      success: true,
      message: "Image uploaded successfully",
      type: "image",
      name: req.file.originalname,
      url: custom.url,
      originalUrl,
      customUrl: true,
      storage: "ImgBB"
    });

  } catch (error) {
    return res.status(500).json({
      success: false,
      message:
        error.response?.data?.error?.message ||
        error.message ||
        "Image upload failed"
    });
  }
});

module.exports = router;