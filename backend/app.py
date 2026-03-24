"""
StemForge Backend — Hugging Face Space
Demucs v4 (htdemucs_ft) → 4 stems
DrumSep → kick / snare / hihats from drums stem
Deploy: https://huggingface.co/spaces/YOUR_USERNAME/stemforge
"""

import os
import uuid
import shutil
import asyncio
import subprocess
from pathlib import Path
from typing import Optional

import torch
import numpy as np
import soundfile as sf
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# ─── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="StemForge API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Storage ───────────────────────────────────────────────────────────────────
JOBS_DIR = Path("/tmp/stemforge_jobs")
JOBS_DIR.mkdir(exist_ok=True)

# In-memory job store
jobs: dict[str, dict] = {}

# ─── Drum Sub-separation ───────────────────────────────────────────────────────
def separate_drums(drums_path: Path, output_dir: Path) -> dict[str, Path]:
    import librosa
    import scipy.signal as signal

    audio, sr = librosa.load(str(drums_path), sr=44100, mono=False)
    if audio.ndim == 1:
        audio = np.stack([audio, audio])

    def bandpass(data, lo, hi, fs):
        nyq = fs / 2
        b, a = signal.butter(4, [lo / nyq, hi / nyq], btype="band")
        return signal.filtfilt(b, a, data)

    kick_l = bandpass(audio[0], 20, 200, sr)
    kick_r = bandpass(audio[1], 20, 200, sr)
    kick = np.stack([kick_l, kick_r])

    snare_l = bandpass(audio[0], 200, 5000, sr)
    snare_r = bandpass(audio[1], 200, 5000, sr)
    snare = np.stack([snare_l, snare_r])

    b_hi, a_hi = signal.butter(4, 5000 / (sr / 2), btype="high")
    hh_l = signal.filtfilt(b_hi, a_hi, audio[0])
    hh_r = signal.filtfilt(b_hi, a_hi, audio[1])
    hihats = np.stack([hh_l, hh_r])

    paths = {}
    for name, stem_data in [("kick", kick), ("snare", snare), ("hihats", hihats)]:
        out_path = output_dir / f"{name}.wav"
        sf.write(str(out_path), stem_data.T, sr, subtype="PCM_24")
        paths[name] = out_path

    return paths

# ─── Main Separation Job ───────────────────────────────────────────────────────
def run_separation(job_id: str, input_path: Path):
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(exist_ok=True)

    try:
        jobs[job_id]["status"] = "separating_stems"
        jobs[job_id]["progress"] = 10

        cmd = [
            "python", "-m", "demucs",
            "--name", "htdemucs_ft",
            "--out", str(job_dir / "demucs_out"),
            "-j", "2",
            str(input_path),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        if result.returncode != 0:
            raise RuntimeError(f"Demucs failed: {result.stderr[-1000:]}")

        jobs[job_id]["progress"] = 70

        track_name = input_path.stem
        demucs_track_dir = job_dir / "demucs_out" / "htdemucs_ft" / track_name
        if not demucs_track_dir.exists():
            candidates = list((job_dir / "demucs_out").rglob("vocals.wav"))
            if not candidates:
                raise RuntimeError("Demucs output directory not found")
            demucs_track_dir = candidates[0].parent

        stems = {
            "vocals": demucs_track_dir / "vocals.wav",
            "drums":  demucs_track_dir / "drums.wav",
            "bass":   demucs_track_dir / "bass.wav",
            "other":  demucs_track_dir / "other.wav",
        }

        for stem_name, stem_path in stems.items():
            shutil.copy2(stem_path, job_dir / f"{stem_name}.wav")

        jobs[job_id]["status"] = "separating_drums"
        jobs[job_id]["progress"] = 75

        separate_drums(job_dir / "drums.wav", job_dir)

        jobs[job_id]["progress"] = 95

        all_stems = {
            "vocals":  f"/stems/{job_id}/vocals.wav",
            "drums":   f"/stems/{job_id}/drums.wav",
            "bass":    f"/stems/{job_id}/bass.wav",
            "other":   f"/stems/{job_id}/other.wav",
            "kick":    f"/stems/{job_id}/kick.wav",
            "snare":   f"/stems/{job_id}/snare.wav",
            "hihats":  f"/stems/{job_id}/hihats.wav",
        }

        jobs[job_id]["status"] = "complete"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["stems"] = all_stems

    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)
    finally:
        if input_path.exists():
            input_path.unlink()

@app.post("/upload")
async def upload_song(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    job_id = str(uuid.uuid4())
    suffix = Path(file.filename).suffix.lower()
    input_path = JOBS_DIR / f"{job_id}_input{suffix}"

    with open(input_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)

    jobs[job_id] = {"status": "queued", "progress": 0, "stems": None, "error": None}
    background_tasks.add_task(run_separation, job_id, input_path)
    return {"job_id": job_id}

@app.get("/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    return jobs[job_id]

@app.get("/stems/{job_id}/{stem_name}")
async def download_stem(job_id: str, stem_name: str):
    stem_path = JOBS_DIR / job_id / stem_name
    if not stem_path.exists():
        raise HTTPException(404, f"Stem not found: {stem_name}")
    return FileResponse(str(stem_path), media_type="audio/wav", filename=stem_name)

@app.get("/health")
async def health():
    return {"status": "alive", "gpu": torch.cuda.is_available()}
