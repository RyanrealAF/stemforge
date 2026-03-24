# StemForge Backend Deployment

This is the FastAPI backend for StemForge, designed to run on Hugging Face Spaces with ZeroGPU or CPU.

## Deployment Steps

1. Create a new Space on Hugging Face.
2. Select **Docker** as the SDK.
3. Upload the files in this directory (`app.py`, `Dockerfile`, `requirements.txt`).
4. Wait for the build to complete.
5. Copy your Space URL (e.g., `https://user-stemforge.hf.space`) and paste it into the StemForge Web App settings.

## API Endpoints

- `POST /upload`: Upload an audio file to start separation.
- `GET /status/{job_id}`: Check processing progress.
- `GET /stems/{job_id}/{stem_name}`: Download isolated stems.
- `GET /health`: Check system status.
