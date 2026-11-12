
const { uploadToCloudinary } = require("../lib/cloudinary");
const { saveLink } = require("../lib/links");

function makeFilename(originalName) {
  const ext = originalName.match(/\.[a-zA-Z0-9]+$/)?.[0] || "";

  const base = originalName
    .replace(/\.[^.]+$/, "")
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, "-")
    .replace(/^-|-$/g, "") || "file";

  return `${base}-${Date.now()}${ext.toLowerCase()}`;
}

module.exports = async function uploadFile(req, res) {
  try {
    if (!req.file) {
      return res.status(400).json({
        success: false,
        message: "Please provide a file."
      });
    }

    const filename = makeFilename(req.file.originalname);

    const result = await uploadToCloudinary(
      req.file.buffer,
      filename,
      "file"
    );

    const baseUrl = (
      process.env.PUBLIC_BASE_URL ||
      "https://durbar-plus2.vercel.app"
    ).replace(/\/+$/, "");

    const customUrl =
      `${baseUrl}/file/${encodeURIComponent(filename)}`;

    await saveLink("file", filename, result.secure_url);

    return res.status(200).json({
      success: true,
      message: "File uploaded successfully.",
      name: filename,
      url: customUrl,
      original_url: result.secure_url
    });

  } catch (error) {
    console.error("File upload error:", error);

    return res.status(500).json({
      success: false,
      message: error.message || "File upload failed."
    });
  }
};
