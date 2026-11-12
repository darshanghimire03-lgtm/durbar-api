
const REDIS_URL = process.env.UPSTASH_REDIS_REST_URL;
const REDIS_TOKEN = process.env.UPSTASH_REDIS_REST_TOKEN;

async function redis(command, ...args) {
  if (!REDIS_URL || !REDIS_TOKEN) {
    throw new Error("Upstash Redis environment variables are missing");
  }

  const response = await fetch(REDIS_URL, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${REDIS_TOKEN}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify([command, ...args])
  });

  const data = await response.json();

  if (!response.ok || data.error) {
    throw new Error(data.error || "Redis request failed");
  }

  return data.result;
}

async function saveLink(type, filename, url) {
  await redis("SET", `durbar:${type}:${filename}`, url);
}

async function getLink(type, filename) {
  return redis("GET", `durbar:${type}:${filename}`);
}

module.exports = {
  saveLink,
  getLink
};
