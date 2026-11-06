import express from "express";
import cors from "cors";
import crypto from "node:crypto";
import image from "./upload/image.js";
import video from "./upload/video.js";
import files from "./upload/files.js";

const app = express();

const auth = (req, res, next) => {
  const key = process.env.API_KEY || "";
  const bearer = req.headers.authorization?.startsWith("Bearer ")
    ? req.headers.authorization.slice(7)
    : "";
  const provided = String(req.headers["x-api-key"] || bearer);
  const a = Buffer.from(provided);
  const b = Buffer.from(key);
  if (!key || a.length !== b.length || !crypto.timingSafeEqual(a, b)) {
    return res.status(401).json({ success: false, error: "Unauthorized" });
  }
  next();
};

app.set("trust proxy", 1);
app.use(cors());
app.use(express.json({ limit: "1mb" }));

app.get("/health", (req, res) => res.json({ success: true, status: "ok" }));

app.use("/api/image", auth, image);
app.use("/api/video", auth, video);
app.use("/api/files", auth, files);

app.use((req, res) => {
  res.status(404).json({ success: false, error: "Route not found" });
});

app.use((err, req, res, next) => {
  let status = err.status || err.http_code || 500;
  let message = err.message || "Internal server error";
  if (err.code === "LIMIT_FILE_SIZE") {
    status = 413;
    message = "File too large";
  }
  if (status < 400 || status > 599) status = 500;
  if (status === 500) console.error(err);
  res.status(status).json({ success: false, error: message });
});

app.listen(Number(process.env.PORT) || 3000, () => {
  console.log("durbar-api running");
});