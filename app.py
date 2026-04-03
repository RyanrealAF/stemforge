
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

        progress_regex = re.compile(r"(\d+)\s*%\|")
        
        if process.stderr:
            while not process.stderr.at_eof():
                line_bytes = await process.stderr.readline()
                if not line_bytes:
                    break
                
                line = line_bytes.decode('utf-8', 'ignore').strip()
                # Add every line from stderr to our log
                job["log"].append(line)
                
                if '\r' in line:
                    line = line.split('\r')[-1]

                match = progress_regex.search(line)
                if match:
                    progress_percent = int(match.group(1))
                    job["progress"] = min(progress_percent, 99)

        stdout_data, stderr_data = await process.communicate()

        if stderr_data:
            job['log'].extend(stderr_data.decode('utf-8', 'ignore').strip().split('\n'))

        if process.returncode == 0:
            job["status"] = "complete"
            job["progress"] = 100
        else:
            job["status"] = "error"
            job["error"] = "Processing failed. See log for details."
    
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        job['log'].append(str(e))
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
