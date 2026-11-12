
const { saveLink } = require("../lib/links");

function makeFilename(originalName) {
  const ext = originalName.match(/\.[a-zA-Z0-9]+$/)?.[0] || ".jpg";

  const base = originalName
    .replace(/\.[^.]+$/, "")
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, "-")
    .replace(/^-|-$/g, "") || "image";

  return `${base}-${Date.now()}${ext.toLowerCase()}`;
}

module.exports = async function uploadImage(req, res) {
  try {
    if (!req.file) {
      return res.status(400).json({
        success: false,
        message: "Please provide an image using the file field."
      });
    }

    if (
      !req.file.mimetype.startsWith("image/") ||
      req.file.mimetype === "image/svg+xml"
    ) {
      return res.status(400).json({
        success: false,
        message: "Only supported image files are allowed."
      });
    }

    const key = process.env.IMGBB_KEY;

    if (!key) {
      return res.status(500).json({
        success: false,
        message: "IMGBB_KEY is missing."
      });
    }

    const form = new FormData();

    form.append(
      "image",
      new Blob([req.file.buffer], {
        type: req.file.mimetype
      }),
      req.file.originalname
    );

    const response = await fetch(
      `https://api.imgbb.com/1/upload?key=${encodeURIComponent(key)}`,
      {
        method: "POST",
        body: form
      }
    );

    const result = await response.json();

    if (!response.ok || !result.success) {
      return res.status(502).json({
        success: false,
        message: result.error?.message || "ImgBB upload failed."
      });
    }

    const filename = makeFilename(req.file.originalname);

    const baseUrl = (
      process.env.PUBLIC_BASE_URL ||
      "https://durbar-plus2.vercel.app"
    ).replace(/\/+$/, "");

    const customUrl =
      `${baseUrl}/img/${encodeURIComponent(filename)}`;

    await saveLink("img", filename, result.data.url);

    return res.status(200).json({
      success: true,
      message: "Image uploaded successfully.",
      name: filename,
      url: customUrl,
      original_url: result.data.url,
      thumbnail_url: result.data.thumb?.url || null
    });

  } catch (error) {
    console.error("Image upload error:", error);

    return res.status(500).json({
      success: false,
      message: "Image upload failed."
    });
  }
};
