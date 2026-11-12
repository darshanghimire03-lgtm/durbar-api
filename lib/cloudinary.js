
async function uploadToCloudinary(buffer, filename, type) {
  const isVideo = type === "video";

  const cloudName = isVideo
    ? process.env.CLOUDINARY_VIDEO_CLOUD_NAME
    : process.env.CLOUDINARY_FILE_CLOUD_NAME;

  const preset = isVideo
    ? process.env.CLOUDINARY_VIDEO_PRESET
    : process.env.CLOUDINARY_FILE_PRESET;

  if (!cloudName || !preset) {
    throw new Error(
      `Cloudinary ${type} cloud name or upload preset is missing`
    );
  }

  const endpoint = isVideo ? "video" : "raw";

  const form = new FormData();

  form.append(
    "file",
    new Blob([buffer]),
    filename
  );

  form.append("upload_preset", preset);
  form.append("public_id", filename);
  form.append("folder", `durbar/${isVideo ? "videos" : "files"}`);

  const response = await fetch(
    `https://api.cloudinary.com/v1_1/${encodeURIComponent(cloudName)}/${endpoint}/upload`,
    {
      method: "POST",
      body: form
    }
  );

  const result = await response.json();

  if (!response.ok || !result.secure_url) {
    throw new Error(
      result.error?.message || `Cloudinary ${type} upload failed`
    );
  }

  return result;
}

module.exports = { uploadToCloudinary };
