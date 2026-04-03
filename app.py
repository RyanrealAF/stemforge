from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import uuid
import os

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

OUTPUT_DIR = "separated"
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

jobs = {}

async def run_demucs(job_id: str, file_path: str):
    try:
        output_path = os.path.join(OUTPUT_DIR, job_id)
        command = f"python3 -m demucs.separate -d cpu --two-stems=vocals \"{file_path}\" -o \"{output_path}\""
        
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            jobs[job_id]["status"] = "complete"
        else:
            jobs[job_id]["status"] = "error"
            jobs[job_id]["error"] = stderr.decode().strip()

    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    job_id = str(uuid.uuid4())
    file_path = f"{job_id}_{file.filename}"
    
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    
    jobs[job_id] = {"status": "processing"}
    asyncio.create_task(run_demucs(job_id, file_path))
    
    return JSONResponse(content={"job_id": job_id})

@app.get("/status/{job_id}")
async def get_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job["status"] == "complete":
        # This needs to be your actual HF Space URL
        base_url = "https://ryanrealaf-stemforge.hf.space/file="
        job["files"] = {
            "vocals": f"{base_url}{os.path.join(OUTPUT_DIR, job_id, 'htdemucs', file.filename.split('.')[0], 'vocals.wav')}",
            "bass": f"{base_url}{os.path.join(OUTPUT_DIR, job_id, 'htdemucs', file.filename.split('.')[0], 'bass.wav')}",
            "drums": f"{base_url}{os.path.join(OUTPUT_DIR, job_id, 'htdemucs', file.filename.split('.')[0], 'drums.wav')}",
            "other": f"{base_url}{os.path.join(OUTPUT_DIR, job_id, 'htdemucs', file.filename.split('.')[0], 'other.wav')}"
        }

    return JSONResponse(content=job)
