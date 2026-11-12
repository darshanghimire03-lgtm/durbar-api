
# Durbar Upload API

JavaScript Node.js upload API hosted on Vercel with Cloudinary storage.

## Requirements

- Node.js 20+
- Vercel account
- Cloudinary account

## Installation

npm install
npm install -g vercel

## Environment variables

CLOUDINARY_IMAGE_CLOUD_NAME=your_cloud_name
CLOUDINARY_IMAGE_PRESET=your_image_preset

CLOUDINARY_VIDEO_CLOUD_NAME=your_cloud_name
CLOUDINARY_VIDEO_PRESET=your_video_preset

CLOUDINARY_FILE_CLOUD_NAME=your_cloud_name
CLOUDINARY_FILE_PRESET=your_file_preset

PUBLIC_BASE_URL=https://your-domain.vercel.app
UPLOAD_API_KEY=your_secret_api_key

## Local development

vercel dev

## Deployment

vercel

vercel --prod

## API endpoints

GET /

POST /upload/image
POST /upload/video
POST /upload/file

POST /upload/direct/image
POST /upload/direct/video
POST /upload/direct/file

GET /img/:name
GET /vid/:name
GET /file/:name

## Upload limits

Small uploads through Vercel:
3.5 MB

Direct Cloudinary uploads:
Image: 10 MB
Video: 100 MB
File: 10 MB

## Authentication

Send X-API-Key when UPLOAD_API_KEY is configured.

## Storage

All uploaded content is stored in Cloudinary.

Vercel is used for API hosting and routing.
