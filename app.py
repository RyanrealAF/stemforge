from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
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

# In-memory dictionary to store the status and progress of processing jobs.
# In a production environment, you might want to use a more persistent storage
# like Redis or a database.
jobs = {}

async def run_demucs(job_id: str, file_path: str, original_filename: str):
    """
    Runs the demucs command in a subprocess and updates the job status.
    """
    try:
        output_path = os.path.join(OUTPUT_DIR, job_id)
        # The command to run demucs. We're using the CPU version for broader compatibility.
        # You can adjust the separation model as needed.
        command = f"python3 -m demucs.separate -d cpu --two-stems=vocals \"{file_path}\" -o \"{output_path}\""
        
        process = await asyncio.create_subprocess_shell(
            command,
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
            
            # IMPORTANT: Replace with your actual Hugging Face Space URL.
            base_url = "https://ryanrealaf-stemforge.hf.space/file="
            file_name_without_ext = os.path.splitext(original_filename)[0]
            
            # Construct the URLs for the separated audio files.
            jobs[job_id]["files"] = {
                "vocals": f"{base_url}{os.path.join(output_path, 'htdemucs', file_name_without_ext, 'vocals.wav')}",
                "bass": f"{base_url}{os.path.join(output_path, 'htdemucs', file_name_without_ext, 'bass.wav')}",
                "drums": f"{base_url}{os.path.join(output_path, 'htdemucs', file_name_without_ext, 'drums.wav')}",
                "other": f"{base_url}{os.path.join(output_path, 'htdemucs', file_name_without_ext, 'other.wav')}"
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


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Uploads an audio file, saves it temporarily, and starts the demucs processing.
    """
    job_id = str(uuid.uuid4())
    file_path = f"{job_id}_{file.filename}"
    
    # Save the uploaded file to a temporary location.
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    
    # Initialize the job status.
    jobs[job_id] = {"status": "processing", "progress": 0}
    
    # Start the demucs process in the background.
    asyncio.create_task(run_demucs(job_id, file_path, file.filename))
    
    return JSONResponse(content={"job_id": job_id})

@app.get("/status/{job_id}")
async def get_status(job_id: str):
    """
    Returns the status and progress of a processing job.
    """
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JSONResponse(content=job)
