const express = require("express");
const cors = require("cors");

const imageRouter = require("../upload/img");
const videoRouter = require("../upload/vid");
const fileRouter = require("../upload/file");

const { resolveImageLink } = require("../lib/links");

const app = express();

app.use(cors({
  origin: "*",
  methods: ["GET", "POST", "OPTIONS"],
  allowedHeaders: ["Content-Type", "X-API-Key"]
}));

app.get("/", (req, res) => {
  res.json({
    success: true,
    name: "Durbar Upload API",
    version: "4.0.0",
    storage: {
      image: "ImgBB",
      video: "Cloudinary",
      file: "Cloudinary"
    },
    customUrls: {
      image: true,
      video: false,
      file: false
    },
    database: false,
    redis: false,
    endpoints: {
      image: "POST /upload/image",
      video: "POST /upload/video",
      file: "POST /upload/file"
    }
  });
});

app.use("/upload/image", imageRouter);
app.use("/upload/video", videoRouter);
app.use("/upload/file", fileRouter);

app.get("/img/:id", (req, res) => {
  try {
    const originalUrl = resolveImageLink(req.params.id);

    if (!originalUrl) {
      return res.status(404).json({
        success: false,
        message: "Invalid image URL"
      });
    }

    return res.redirect(302, originalUrl);

  } catch (error) {
    return res.status(500).json({
      success: false,
      message: "Image redirect failed"
    });
  }
});

app.use((req, res) => {
  res.status(404).json({
    success: false,
    message: "Endpoint not found"
  });
});

app.use((error, req, res, next) => {
  res.status(error.status || 500).json({
    success: false,
    message: error.message || "Internal server error"
  });
});

module.exports = app;