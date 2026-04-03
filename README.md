<div align="center">
<img width="1200" height="475" alt="GHBanner" src="https://github.com/user-attachments/assets/0aa67016-6eaf-458a-adb2-6e31a0763ed6" />
</div>

# Run and deploy your AI Studio app

This contains everything you need to run your app locally.

View your app in AI Studio: https://ai.studio/apps/40cab3ac-58b7-466e-a068-8284406d69a7

## Run Locally

**Prerequisites:**  Node.js


1. Install dependencies:
   `npm install`
2. Set the `GEMINI_API_KEY` in [.env.local](.env.local) to your Gemini API key
3. Run the app:
   `npm run dev`

## Project Status & Troubleshooting Summary (For Handoff)

This section provides a detailed breakdown of the project'''s architecture and the troubleshooting steps taken to get it to a working state. It is intended to brief any developer or AI assistant taking over the project.

### Project Overview
- **Application:** StemForge
- **Goal:** A web application that separates an audio file into its constituent stems (vocals, bass, drums, other) using AI.

### Technical Architecture
The project is comprised of two main parts:

1.  **Frontend (in `/src`)**: A **React + Vite** application written in TypeScript.
    - It provides the user interface for file uploads.
    - It communicates with the backend via API calls.
    - After an upload, it polls a `/status` endpoint until the processing is complete.
    - It uses `wavesurfer.js` to display the final separated audio tracks.

2.  **Backend (root folder: `app.py`, `requirements.txt`)**: A **Python + FastAPI** server application designed to be deployed on a platform like Hugging Face Spaces.
    - **`app.py`**: Defines two main API endpoints:
        - `POST /upload`: Receives the audio file, starts the separation process in the background, and returns a `job_id`.
        - `GET /status/{job_id}`: Allows the frontend to check the status of the separation job.
    - **`demucs`**: The core AI model (a Python library) that performs the audio separation.
    - **`requirements.txt`**: Defines the necessary Python dependencies for the Hugging Face environment.

### Troubleshooting History

The project went through several key troubleshooting phases:

1.  **Initial Problem: Processing Stuck at 99%**
    - **Symptom:** The frontend progress bar would reach 99% and never complete.
    - **Root Cause:** A **deadlock** in the `app.py` backend. The original code attempted to read the progress percentage from the `demucs` process in real-time. This method was unreliable and caused both the main script and the `demucs` process to wait for each other indefinitely.
    - **Solution:** The `run_demucs` function in `app.py` was rewritten to use `await process.communicate()`. This is a more robust method that simply waits for the `demucs` subprocess to finish completely, resolving the deadlock.

2.  **Second Problem: Hugging Face Build Failures**
    - **Symptom:** After fixing the deadlock, deploying the application to Hugging Face resulted in a build error.
    - **Root Cause:** The `demucs` library depends on `torch`, but the installer was trying to fetch a GPU version. The Hugging Face server is CPU-only, causing a compatibility failure.
    - **Solution:** The `requirements.txt` file was modified to point to the CPU-specific repository for `torch` and to install `torch` and `torchaudio` explicitly.

3.  **Third Problem: Missing `torchcodec` Dependency**
    - **Symptom:** After fixing the build error, the app would fail during processing with an `ImportError: TorchCodec is required...` message shown on the frontend.
    - **Root Cause:** A sub-component of `demucs` requires the `torchcodec` package to save the final audio files. This package was not included in our list of dependencies.
    - **Solution:** The `torchcodec` package was added to the `requirements.txt` file.

### Current Status

The codebase has been updated to fix the runtime `ImportError` related to the missing `torchcodec` package. The `requirements.txt` file now includes this dependency. The user is in the process of deploying this latest version to their Hugging Face Space. This is believed to be the final dependency required to make the application fully functional.
