const axios = require("axios");
const FormData = require("form-data");

async function uploadCloudinary(file, type) {
  let cloud;
  let preset;
  let resourceType;

  if (type === "video") {
    cloud = process.env.CLOUDINARY_VIDEO_CLOUD_NAME;
    preset = process.env.CLOUDINARY_VIDEO_PRESET;
    resourceType = "video";
  } else if (type === "file") {
    cloud = process.env.CLOUDINARY_FILE_CLOUD_NAME;
    preset = process.env.CLOUDINARY_FILE_PRESET;
    resourceType = "raw";
  } else {
    throw new Error("Invalid upload type");
  }

  if (!cloud || !preset) {
    throw new Error(`Cloudinary ${type} environment variables are missing`);
  }

  const form = new FormData();

  form.append("file", file.buffer, {
    filename: file.originalname,
    contentType: file.mimetype
  });

  form.append("upload_preset", preset);
  form.append("use_filename", "true");
  form.append("unique_filename", "true");

  const endpoint =
    `https://api.cloudinary.com/v1_1/${cloud}/${resourceType}/upload`;

  const response = await axios.post(endpoint, form, {
    headers: form.getHeaders(),
    maxBodyLength: Infinity,
    maxContentLength: Infinity,
    timeout: 600000
  });

  return {
    url: response.data.secure_url,
    publicId: response.data.public_id,
    name: file.originalname,
    format: response.data.format,
    bytes: response.data.bytes
  };
}

module.exports = {
  uploadCloudinary
};