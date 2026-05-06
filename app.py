from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import asyncio
import uuid
import os
import re

app = FastAPI()

# Configure CORS to allow all origins, which is useful for development.
# For production, you should restrict this to your frontend's domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directory to store the separated audio files.
OUTPUT_DIR = "separated"
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

app.mount(f"/{OUTPUT_DIR}", StaticFiles(directory=OUTPUT_DIR), name=OUTPUT_DIR)

MAX_UPLOAD_SIZE = 100 * 1024 * 1024

# In-memory dictionary to store the status and progress of processing jobs.
# In a production environment, you might want to use a more persistent storage
# like Redis or a database.
jobs = {}

def sanitize_filename(filename: str) -> str:
    """
    Sanitizes an uploaded filename while preserving the extension for Demucs.
    """
    filename = os.path.basename(filename or "upload")
    name, ext = os.path.splitext(filename)
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._-")
    safe_ext = re.sub(r"[^A-Za-z0-9.]+", "", ext)
    return f"{safe_name or 'upload'}{safe_ext}"

async def run_demucs(job_id: str, file_path: str, original_filename: str):
    """
    Runs the demucs command in a subprocess and updates the job status.
    """
    try:
        output_path = os.path.join(OUTPUT_DIR, job_id)
        # The command to run demucs. We're using the CPU version for broader compatibility.
        # You can adjust the separation model as needed.
        process = await asyncio.create_subprocess_exec(
            "python3",
            "-m",
            "demucs.separate",
            "-d",
            "cpu",
            file_path,
            "-o",
            output_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Regex to capture the percentage from the tqdm progress bar used by demucs.
        progress_regex = re.compile(r"(\d+)\%")

        # Read the stderr stream to capture progress updates.
        while process.returncode is None:
            line = await process.stderr.readline()
            if not line:
                break
            line = line.decode().strip()
            
            match = progress_regex.search(line)
            if match:
                progress = int(match.group(1))
                jobs[job_id]["progress"] = progress
            
            await asyncio.sleep(0.1)

        # Wait for the process to finish.
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            # If the process is successful, update the status and progress.
            jobs[job_id]["status"] = "complete"
            jobs[job_id]["progress"] = 100
            
            file_name_without_ext = os.path.splitext(original_filename)[0]
            base_path = f"/{OUTPUT_DIR}/{job_id}/htdemucs/{file_name_without_ext}"
            
            # Construct the URLs for the separated audio files.
            jobs[job_id]["files"] = {
                "vocals": f"{base_path}/vocals.wav",
                "bass": f"{base_path}/bass.wav",
                "drums": f"{base_path}/drums.wav",
                "other": f"{base_path}/other.wav"
            }
        else:
            # If there's an error, capture the error message.
            jobs[job_id]["status"] = "error"
            jobs[job_id]["error"] = stderr.decode().strip()

    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)
    finally:
        # Clean up the temporary uploaded file.
        if os.path.exists(file_path):
            os.remove(file_path)


async def create_separation_job(file: UploadFile):
    """
    Uploads an audio file, saves it temporarily, and starts the demucs processing.
    """
    job_id = str(uuid.uuid4())
    sanitized_filename = sanitize_filename(file.filename)
    file_path = f"{job_id}_{sanitized_filename}"
    
    # Save the uploaded file to a temporary location.
    size = 0
    with open(file_path, "wb") as buffer:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_SIZE:
                os.remove(file_path)
                raise HTTPException(status_code=413, detail="File exceeds 100MB upload limit")
            buffer.write(chunk)
    
    # Initialize the job status.
    jobs[job_id] = {"status": "processing", "progress": 0}
    
    # Start the demucs process in the background.
    asyncio.create_task(run_demucs(job_id, file_path, sanitized_filename))
    
    return JSONResponse(content={"job_id": job_id})

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    return await create_separation_job(file)

@app.post("/separate")
async def separate_file(file: UploadFile = File(...)):
    return await create_separation_job(file)

@app.get("/status/{job_id}")
async def get_status(job_id: str):
    """
    Returns the status and progress of a processing job.
    """
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JSONResponse(content=job)
