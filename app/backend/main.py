from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uuid, os, shutil, asyncio
import asyncio, shutil, uuid, os
from app.backend.pipeline.pipeline import run_full_pipeline

from dotenv import load_dotenv
load_dotenv()

app = FastAPI(title="AutoCut Studio")

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

jobs = {}

class LoginRequest(BaseModel):
    username: str

@app.post("/api/login")
async def login(data: LoginRequest):
    return {"session": str(uuid.uuid4())}

@app.post("/api/upload")
async def upload_video(file: UploadFile, session: str = Form(...)):
    job_id = str(uuid.uuid4())
    upload_path = os.path.join("uploads", f"{job_id}_{file.filename}")
    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    jobs[job_id] = {"status": "pending"}

    async def worker():
        try:
            hf_token = os.getenv("HUGGINGFACE_TOKEN")
            outputs = run_full_pipeline(upload_path, hf_token)
            jobs[job_id] = {
                "status": "done",
                "srt": outputs["srt"],
                "video": outputs["final_video"],
                "segments": [],
            }
        except Exception as e:
            jobs[job_id] = {"status": "error", "error": str(e)}

    asyncio.create_task(worker())
    return {"job_id": job_id}

@app.get("/api/results/{job_id}")
async def get_results(job_id: str):
    job = jobs.get(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    if job["status"] != "done":
        return {"status": job["status"]}
    return {
        "status": "done",
        "srt_url": f"/files/{os.path.basename(job['srt'])}",
        "final_video_url": f"/files/{os.path.basename(job['video'])}",
        "segments": job["segments"],
    }

@app.get("/files/{filename}")
async def get_file(filename: str):
    path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(path):
        return JSONResponse({"error": "File not found"}, status_code=404)
    return FileResponse(path)

# Mount frontend after defining API
app.mount("/", StaticFiles(directory="static", html=True), name="static")
