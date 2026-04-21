<div align="center">
<img width="1200" height="475" alt="GHBanner" src="https://github.com/user-attachments/assets/0aa67016-6eaf-458a-adb2-6e31a0763ed6" />
</div>

# StemForge: AI-Powered Stem Separation

This repository contains the frontend and backend for StemForge, a web application that uses AI to separate audio files into their constituent stems (vocals, bass, drums, other).

View your app in AI Studio: https://ai.studio/apps/40cab3ac-58b7-466e-a068-8284406d69a7

## Architecture

*   **Frontend**: A static web application located in the `/public` directory. This is designed to be deployed to a static hosting service like Cloudflare Pages.
*   **Backend**: A Python server using `FastAPI` (`app.py`) that handles audio processing with the `demucs` library. This is designed to be deployed to a GPU-powered service like a Hugging Face Space.

## Backend Deployment (Hugging Face)

This application's backend is designed to be deployed as a Hugging Face Space, preferably using a ZeroGPU instance for performance.

### Dependencies

Your `requirements.txt` file on Hugging Face must include the following:

```
fastapi
uvicorn
python-multipart
demucs
# CRITICAL: Add the following lines for torch audio backend
torch --extra-index-url https://download.pytorch.org/whl/cpu
torchaudio --extra-index-url https://download.pytorch.org/whl/cpu
```

Adding `torch` and `torchaudio` is essential for the `demucs` library to function correctly on Hugging Face Spaces.

### Steps

1.  Create a new Hugging Face Space.
2.  Select "ZeroGPU" as the hardware.
3.  Upload your `app.py` and `requirements.txt` files to the root of the Space.
4.  The Space will build and deploy the application. Your backend will be live at the URL of your Space (e.g., `https://YourUser-YourSpace.hf.space`).

## Frontend Deployment (Cloudflare Pages)

The frontend is a static site contained in the `/public` directory.

### Steps

1.  Log in to your Cloudflare dashboard.
2.  Navigate to **Workers & Pages**.
3.  Click **Create application** > **Pages** > **Connect to Git**.
4.  Select this GitHub repository.
5.  In the "Set up builds and deployments" section:
    *   **Build command**: Leave this blank.
    *   **Build output directory**: Set this to `public`.
6.  Click **Save and Deploy**.

## Connecting the Frontend to the Backend

Once both are deployed, you must connect them.

1.  In your `public/index.html` file, find the `state` object in the `<script>` tag.
2.  Update the `hfUrl` property to point to your live Hugging Face Space URL.

```javascript
// In public/index.html
const state = {
  hfUrl: 'https://YourUser-YourSpace.hf.space', // <-- Make sure this is your HF Space URL
  // ...
};
```

3.  Commit and push this change to your GitHub repository. Cloudflare Pages will automatically redeploy your frontend with the updated backend URL.
