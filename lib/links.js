const BASE_URL = (
  process.env.PUBLIC_BASE_URL || "https://durbar-api.vercel.app"
).replace(/\/+$/, "");

function createImageLink(originalUrl) {
  const parsed = new URL(originalUrl);

  if (
    parsed.protocol !== "https:" ||
    !["ibb.co", "ib b.co", "i.ibb.co", "imgbb.com"].includes(parsed.hostname)
  ) {
    throw new Error("Invalid image storage URL");
  }

  const id = Buffer.from(originalUrl).toString("base64url");

  return {
    id,
    url: `${BASE_URL}/img/${id}`
  };
}

function resolveImageLink(id) {
  if (!/^[A-Za-z0-9_-]+$/.test(id)) {
    return null;
  }

  try {
    const originalUrl = Buffer.from(id, "base64url").toString("utf8");
    const parsed = new URL(originalUrl);

    if (
      parsed.protocol !== "https:" ||
      !["ibb.co", "i.ibb.co", "imgbb.com"].includes(parsed.hostname)
    ) {
      return null;
    }

    return originalUrl;
  } catch {
    return null;
  }
}

module.exports = {
  createImageLink,
  resolveImageLink
};