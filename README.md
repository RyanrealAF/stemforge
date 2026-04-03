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
    - **Solution:** The `run_demucs` function in `app.py` was rewritten to use `await process.communicate()`. This is a more robust method that simply waits for the `demucs` subprocess to finish completely, resolving the deadlock. The trade-off is the loss of a real-time progress bar in favor of system stability.

2.  **Second Problem: Hugging Face Build Failures**
    - **Symptom:** After fixing the deadlock, deploying the application to Hugging Face resulted in a build error.
    - **Root Cause:** The `demucs` library depends on the `torch` machine learning library. By default, the installer (`pip`) would try to fetch a version of `torch` that required a GPU. The free Hugging Face Spaces provide a CPU-only environment, causing the build to fail because it couldn'''t find a compatible library version.
    - **Solution:** The `requirements.txt` file was significantly modified to be very explicit about dependencies.
        - `--extra-index-url https://download.pytorch.org/whl/cpu`: This line was added to tell the installer to *also* look in the official PyTorch repository that contains CPU-only versions.
        - `torch` and `torchaudio` were explicitly added to the list. This ensures that the correct CPU versions are installed *before* the installer tries to install `demucs`.

### Current Status

The codebase is now believed to be stable and correct. The `app.py` script resolves the processing deadlock, and the `requirements.txt` file should allow the project to build successfully on a Hugging Face CPU environment. The user is in the process of deploying this final version to their Hugge Face Space.
