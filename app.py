
import os
import uuid
import subprocess
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import asyncio
import re
from typing import Dict, List

app = FastAPI()

# In-memory job store
jobs: Dict[str, Dict] = {}
OUTPUT_DIR = "separated_audio"
os.makedirs(OUTPUT_DIR, exist_ok=True)

app.mount("/" + OUTPUT_DIR, StaticFiles(directory=OUTPUT_DIR), name="separated")

@app.post("/upload")
async def upload_and_process(file: UploadFile = File(...)):
    job_id = str(uuid.uuid4())
    original_filename = file.filename if file.filename else "audio"
    file_extension = os.path.splitext(original_filename)[1]
    file_path = f"{job_id}{file_extension}"

    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())

    # Add a log to the job to store stderr output
    jobs[job_id] = {"status": "processing", "progress": 0, "files": {}, "log": []}
    
    asyncio.create_task(run_demucs(job_id, file_path))

    return JSONResponse(content={"job_id": job_id})

@app.get("/status/{job_id}")
async def get_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["status"] == "complete":
        base_url = "https://ryanrealaf-stemforge.hf.space"
        job["files"] = {
            "vocals": f"{base_url}/{OUTPUT_DIR}/{job_id}/htdemucs/vocals.wav",
            "bass": f"{base_url}/{OUTPUT_DIR}/{job_id}/htdemucs/bass.wav",
            "drums": f"{base_url}/{OUTPUT_DIR}/{job_id}/htdemucs/drums.wav",
            "other": f"{base_url}/{OUTPUT_DIR}/{job_id}/htdemucs/other.wav"
        }

    return JSONResponse(content=job)

async def run_demucs(job_id: str, file_path: str):
    job = jobs[job_id]
    try:
        # Set a generic progress value to indicate processing has started
        job["progress"] = 50
        job["status"] = "processing"

        command = [
            "python3", "-m", "demucs.separate",
            "-n", "htdemucs",
            "--out", os.path.join(OUTPUT_DIR, job_id),
            file_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *command,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )

        # Wait for the process to finish and read both stdout and stderr
        # This is a more robust method that avoids deadlocks
        stdout_data, stderr_data = await process.communicate()

        # Store logs for debugging if needed
        if stdout_data:
            job['log'].extend(stdout_data.decode('utf-8', 'ignore').strip().split('\n'))
        if stderr_data:
            job['log'].extend(stderr_data.decode('utf-8', 'ignore').strip().split('\n'))

        if process.returncode == 0:
            job["status"] = "complete"
            job["progress"] = 100
        else:
            job["status"] = "error"
            # Provide a more useful error message from the logs
            error_message = "Processing failed. Check logs for details."
            if stderr_data:
                # Try to find a meaningful error line in the last few lines of stderr
                error_lines = stderr_data.decode('utf-8', 'ignore').strip().split('\n')
                if error_lines:
                    error_message = error_lines[-1]

            job["error"] = error_message
    
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        job['log'].append(str(e))
    finally:
        # Clean up the original uploaded file
        if os.path.exists(file_path):
            os.remove(file_path)
