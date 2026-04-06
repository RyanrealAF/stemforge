<div align="center">
<img width="1200" height="475" alt="GHBanner" src="https://github.com/user-attachments/assets/0aa67016-6eaf-458a-adb2-6e31a0763ed6" />
</div>

# StemForge: AI-Powered Stem Separation

This repository contains the frontend and backend for StemForge, a web application that uses AI to separate audio files into their constituent stems (vocals, bass, drums, other).

View your app in AI Studio: https://ai.studio/apps/40cab3ac-58b7-466e-a068-8284406d69a7

## Architecture

*   **Frontend**: A static `index.html` file with vanilla JavaScript that provides the user interface.
*   **Backend**: A Python server using `FastAPI` (`app.py`) that handles audio processing with the `demucs` library.

## Running the Backend on Hugging Face

This application is designed to be deployed as a Hugging Face Space using a ZeroGPU.

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

### Deployment

1.  Create a new Hugging Face Space.
2.  Select "ZeroGPU" as the hardware.
3.  Upload your `app.py` and `requirements.txt` files.
4.  The Space will build and deploy the application. Your backend will be live at the URL of your Space (e.g., `https://YourUser-YourSpace.hf.space`).

## Connecting the Frontend

The `index.html` file connects to the Hugging Face backend. Make sure the `hfUrl` in the `<script>` section of `index.html` is set to the correct URL of your running Hugging Face Space.

```javascript
// In index.html
const state = {
  hfUrl: 'https://Ryanrealaf-stemforge.hf.space', // <-- Make sure this is your HF Space URL
  // ...
};
```
