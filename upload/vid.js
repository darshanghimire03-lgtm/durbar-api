
const { uploadToCloudinary } = require("../lib/cloudinary");
const { saveLink } = require("../lib/links");

function makeFilename(originalName) {
  const ext = originalName.match(/\.[a-zA-Z0-9]+$/)?.[0] || ".mp4";

  const base = originalName
    .replace(/\.[^.]+$/, "")
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, "-")
    .replace(/^-|-$/g, "") || "video";

  return `${base}-${Date.now()}${ext.toLowerCase()}`;
}

module.exports = async function uploadVideo(req, res) {
  try {
    if (!req.file) {
      return res.status(400).json({
        success: false,
        message: "Please provide a video file."
      });
    }

    if (!req.file.mimetype.startsWith("video/")) {
      return res.status(400).json({
        success: false,
        message: "Only video files are allowed."
      });
    }

    const filename = makeFilename(req.file.originalname);

    const result = await uploadToCloudinary(
      req.file.buffer,
      filename,
      "video"
    );

    const baseUrl = (
      process.env.PUBLIC_BASE_URL ||
      "https://durbar-plus2.vercel.app"
    ).replace(/\/+$/, "");

    const customUrl =
      `${baseUrl}/vid/${encodeURIComponent(filename)}`;

    await saveLink("vid", filename, result.secure_url);

    return res.status(200).json({
      success: true,
      message: "Video uploaded successfully.",
      name: filename,
      url: customUrl,
      original_url: result.secure_url
    });

  } catch (error) {
    console.error("Video upload error:", error);

    return res.status(500).json({
      success: false,
      message: error.message || "Video upload failed."
    });
  }
};
