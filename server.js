
const express = require("express");
const cors = require("cors");
const multer = require("multer");

const { getLink } = require("./lib/links");

const uploadImage = require("./upload/img");
const uploadVideo = require("./upload/vid");
const uploadFile = require("./upload/file");

const app = express();

app.use(cors({
  origin: "*",
  methods: ["GET", "POST", "OPTIONS"],
  allowedHeaders: ["Content-Type", "X-API-Key"]
}));

const upload = multer({
  storage: multer.memoryStorage(),
  limits: {
    fileSize: 4 * 1024 * 1024,
    files: 1
  }
});

app.get("/", (req, res) => {
  res.json({
    success: true,
    name: "Durbar Upload API",
    version: "2.1.0",
    storage: {
      image: "ImgBB",
      video: "Cloudinary unsigned preset",
      file: "Cloudinary unsigned preset"
    },
    endpoints: {
      image: "POST /upload/image",
      video: "POST /upload/video",
      file: "POST /upload/file"
    }
  });
});

app.post("/upload/image", upload.single("file"), uploadImage);
app.post("/upload/video", upload.single("file"), uploadVideo);
app.post("/upload/file", upload.single("file"), uploadFile);

async function redirectToFile(type, req, res) {
  try {
    const filename = req.params.filename;
    const url = await getLink(type, filename);

    if (!url) {
      return res.status(404).json({
        success: false,
        message: "File not found."
      });
    }

    return res.redirect(302, url);

  } catch (error) {
    console.error("Redirect error:", error);

    return res.status(500).json({
      success: false,
      message: "Could not retrieve file."
    });
  }
}

app.get("/img/:filename", (req, res) =>
  redirectToFile("img", req, res)
);

app.get("/vid/:filename", (req, res) =>
  redirectToFile("vid", req, res)
);

app.get("/file/:filename", (req, res) =>
  redirectToFile("file", req, res)
);

app.use((error, req, res, next) => {
  if (error instanceof multer.MulterError || error.status === 413) {
    return res.status(413).json({
      success: false,
      message: "File is too large. Maximum upload size is 4 MB."
    });
  }

  console.error(error);

  return res.status(500).json({
    success: false,
    message: "Internal server error."
  });
});

if (require.main === module) {
  const PORT = process.env.PORT || 3000;

  app.listen(PORT, () => {
    console.log(`Durbar API running on port ${PORT}`);
  });
}

module.exports = app;
