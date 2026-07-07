from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import asyncio
import uuid
import os
import re
import wave
import math
from urllib.parse import quote

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

MIDI_SOURCE_STEMS = ("piano", "guitar", "bass")
MIDI_TICKS_PER_QUARTER = 480
MIDI_TEMPO_MICROSECONDS = 500000
STEM_ROLES = {
    "vocals": "lead vocal / harmonic content",
    "drums": "transient rhythm stem",
    "bass": "low-frequency instrument stem",
    "guitar": "string instrument stem",
    "piano": "keyboard instrument stem",
    "other": "residual harmonic bed",
}

def sanitize_filename(filename: str) -> str:
    """
    Sanitizes an uploaded filename while preserving the extension for Demucs.
    """
    filename = os.path.basename(filename or "upload")
    name, ext = os.path.splitext(filename)
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._-")
    safe_ext = re.sub(r"[^A-Za-z0-9.]+", "", ext)
    return f"{safe_name or 'upload'}{safe_ext}"

def get_separated_outputs(job_id: str):
    """
    Finds all files Demucs generated for a job and returns StaticFiles URLs.
    """
    job_output_dir = os.path.join(OUTPUT_DIR, job_id)
    outputs = []

    if not os.path.isdir(job_output_dir):
        return outputs

    for root, _, filenames in os.walk(job_output_dir):
        for filename in sorted(filenames):
            file_path = os.path.join(root, filename)
            if not os.path.isfile(file_path):
                continue

            relative_path = os.path.relpath(file_path, job_output_dir)
            relative_url_path = relative_path.replace(os.sep, "/")
            url = f"/{OUTPUT_DIR}/{quote(job_id)}/{quote(relative_url_path, safe='/')}"

            outputs.append({
                "filename": filename,
                "relative_path": relative_url_path,
                "size": os.path.getsize(file_path),
                "url": url,
                "analysis": build_file_analysis(filename, file_path)
            })

    outputs.sort(key=lambda output: output["relative_path"])
    return outputs

def build_file_analysis(filename: str, file_path: str):
    """
    Returns lightweight per-file metadata for result dashboards.
    """
    stem_name, extension = os.path.splitext(filename)
    extension = extension.lower().lstrip(".")
    stem_key = stem_name.lower()
    size_bytes = os.path.getsize(file_path)
    is_midi = extension in ("mid", "midi")
    is_wav = extension == "wav"

    return {
        "stem": stem_key,
        "extension": extension,
        "file_type": "midi" if is_midi else "audio" if is_wav else "other",
        "process_stage": "midi transcription" if is_midi else "stem separation" if is_wav else "artifact export",
        "role": STEM_ROLES.get(stem_key, "supporting separation artifact"),
        "size_bytes": size_bytes,
        "size_kb": round(size_bytes / 1024, 2),
        "is_expected_wav_stem": is_wav and stem_key in STEM_ROLES,
        "is_midi_stem": is_midi and stem_key in MIDI_SOURCE_STEMS,
    }

def encode_variable_length_quantity(value: int) -> bytes:
    """
    Encodes an integer as a MIDI variable-length quantity.
    """
    value = max(0, int(value))
    buffer = value & 0x7F

    while value := value >> 7:
        buffer <<= 8
        buffer |= (value & 0x7F) | 0x80

    encoded = bytearray()
    while True:
        encoded.append(buffer & 0xFF)
        if buffer & 0x80:
            buffer >>= 8
        else:
            break

    return bytes(encoded)

def midi_note_from_frequency(frequency: float) -> int:
    """
    Converts a frequency in Hz to the closest MIDI note number.
    """
    if frequency <= 0:
        return 60

    return max(0, min(127, round(69 + 12 * math.log2(frequency / 440.0))))

def estimate_midi_notes_from_wav(wav_path: str):
    """
    Builds a simple monophonic note timeline from a WAV file.

    This intentionally avoids extra runtime dependencies. It is a lightweight
    transcription pass that detects active audio windows and estimates pitch
    from zero crossings, producing useful MIDI guide tracks for instrument
    stems.
    """
    notes = []

    with wave.open(wav_path, "rb") as wav_file:
        sample_rate = wav_file.getframerate()
        sample_width = wav_file.getsampwidth()
        channels = wav_file.getnchannels()

        if sample_width not in (1, 2, 4):
            return notes

        window_size = max(1, int(sample_rate * 0.1))
        start_time = None
        note_samples = []
        sample_index = 0
        silence_windows = 0

        while frames := wav_file.readframes(window_size):
            samples = decode_wav_samples(frames, sample_width, channels)
            if not samples:
                continue

            rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
            peak = max(abs(sample) for sample in samples)
            is_active = rms > 0.015 and peak > 0.05

            if is_active:
                if start_time is None:
                    start_time = sample_index / sample_rate
                    note_samples = []
                silence_windows = 0
                note_samples.extend(samples)
            elif start_time is not None:
                silence_windows += 1
                if silence_windows >= 2:
                    end_time = sample_index / sample_rate
                    notes.append({
                        "start": start_time,
                        "duration": max(0.1, end_time - start_time),
                        "note": midi_note_from_frequency(estimate_frequency(note_samples, sample_rate)),
                        "velocity": 96,
                    })
                    start_time = None
                    note_samples = []
                    silence_windows = 0

            sample_index += len(samples)

        if start_time is not None:
            end_time = sample_index / sample_rate
            notes.append({
                "start": start_time,
                "duration": max(0.1, end_time - start_time),
                "note": midi_note_from_frequency(estimate_frequency(note_samples, sample_rate)),
                "velocity": 96,
            })

    return notes

def decode_wav_samples(frames: bytes, sample_width: int, channels: int):
    samples = []
    frame_width = sample_width * channels

    for frame_start in range(0, len(frames) - frame_width + 1, frame_width):
        channel_samples = []
        for channel in range(channels):
            start = frame_start + channel * sample_width
            sample_bytes = frames[start:start + sample_width]
            if sample_width == 1:
                value = (sample_bytes[0] - 128) / 128.0
            else:
                value = int.from_bytes(sample_bytes, byteorder="little", signed=True)
                value /= float(2 ** (8 * sample_width - 1))
            channel_samples.append(value)
        samples.append(sum(channel_samples) / len(channel_samples))

    return samples

def estimate_frequency(samples, sample_rate: int) -> float:
    if len(samples) < 2:
        return 440.0

    crossings = 0
    previous = samples[0]
    for sample in samples[1:]:
        if previous < 0 <= sample or previous > 0 >= sample:
            crossings += 1
        previous = sample

    duration = len(samples) / sample_rate
    if duration <= 0 or crossings == 0:
        return 440.0

    return crossings / (2 * duration)

def write_midi_file(midi_path: str, notes):
    track = bytearray()
    track.extend(b"\x00\xFF\x51\x03")
    track.extend(MIDI_TEMPO_MICROSECONDS.to_bytes(3, byteorder="big"))

    events = []
    for note in notes:
        start_tick = round(note["start"] * MIDI_TICKS_PER_QUARTER * 2)
        duration_ticks = max(1, round(note["duration"] * MIDI_TICKS_PER_QUARTER * 2))
        events.append((start_tick, 0, note["note"], note["velocity"]))
        events.append((start_tick + duration_ticks, 1, note["note"], 0))

    events.sort(key=lambda event: (event[0], event[1]))
    current_tick = 0
    for tick, event_type, note, velocity in events:
        track.extend(encode_variable_length_quantity(tick - current_tick))
        track.extend(bytes([0x90 if event_type == 0 else 0x80, note, velocity]))
        current_tick = tick

    track.extend(b"\x00\xFF\x2F\x00")

    with open(midi_path, "wb") as midi_file:
        midi_file.write(b"MThd")
        midi_file.write((6).to_bytes(4, byteorder="big"))
        midi_file.write((0).to_bytes(2, byteorder="big"))
        midi_file.write((1).to_bytes(2, byteorder="big"))
        midi_file.write(MIDI_TICKS_PER_QUARTER.to_bytes(2, byteorder="big"))
        midi_file.write(b"MTrk")
        midi_file.write(len(track).to_bytes(4, byteorder="big"))
        midi_file.write(track)

def create_midi_outputs(job_id: str):
    """
    Creates MIDI guide tracks for piano, guitar, and bass stems when present.
    """
    job_output_dir = os.path.join(OUTPUT_DIR, job_id)
    midi_files = []

    for root, _, filenames in os.walk(job_output_dir):
        wav_lookup = {os.path.splitext(filename)[0].lower(): filename for filename in filenames}
        for stem_name in MIDI_SOURCE_STEMS:
            wav_filename = wav_lookup.get(stem_name)
            if not wav_filename:
                continue

            wav_path = os.path.join(root, wav_filename)
            midi_path = os.path.join(root, f"{stem_name}.mid")
            notes = estimate_midi_notes_from_wav(wav_path)
            write_midi_file(midi_path, notes)
            midi_files.append(midi_path)

    return midi_files

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
            "-n",
            "htdemucs_6s",
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
            create_midi_outputs(job_id)
            # If the process is successful, update the status and progress.
            jobs[job_id]["status"] = "complete"
            jobs[job_id]["progress"] = 100
            jobs[job_id]["files"] = get_separated_outputs(job_id)
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

@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    return await get_status(job_id)
