from fastapi import FastAPI, UploadFile, Form, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid, os, shutil, asyncio, subprocess, glob, json
import sqlite3
import threading
from typing import List, Optional
from app.backend.broll import extraction, description, storage, embedding
from app.backend.pipeline import transcribe, summarize, video_utils
from app.backend.action import ingest, identify, assemble
from app.backend.utils import load_pickle
import random
import static_ffmpeg

from dotenv import load_dotenv
load_dotenv()
static_ffmpeg.add_paths()

# Check for external dependencies
HAS_FFMPEG = shutil.which("ffmpeg") is not None
HAS_HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN") is not None
HAS_OPENAI_KEY = os.getenv("OPENAI_API_KEY") is not None
HAS_GITHUB_TOKEN = os.getenv("GITHUB_TOKEN") is not None

app = FastAPI(title="AutoCut Studio")

# CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"
KEYFRAMES_DIR = "keyframes_output"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(KEYFRAMES_DIR, exist_ok=True)

JOBS_DB_PATH = os.path.join(OUTPUT_DIR, "jobs.sqlite3")
_jobs_db_lock = threading.Lock()


def _init_jobs_db():
    with _jobs_db_lock:
        conn = sqlite3.connect(JOBS_DB_PATH)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()
        finally:
            conn.close()


def _persist_job_to_db(job_id: str, payload: dict):
    with _jobs_db_lock:
        conn = sqlite3.connect(JOBS_DB_PATH)
        try:
            conn.execute(
                """
                INSERT INTO jobs (id, payload, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    payload=excluded.payload,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (job_id, json.dumps(payload)),
            )
            conn.commit()
        finally:
            conn.close()


def _load_jobs_from_db() -> dict:
    with _jobs_db_lock:
        conn = sqlite3.connect(JOBS_DB_PATH)
        try:
            rows = conn.execute("SELECT id, payload FROM jobs").fetchall()
        finally:
            conn.close()
    loaded = {}
    for job_id, payload in rows:
        try:
            loaded[job_id] = json.loads(payload)
        except Exception:
            continue
    return loaded


class JobState(dict):
    def __init__(self, job_id: str, data: dict, persist_callback):
        super().__init__(data)
        self._job_id = job_id
        self._persist = persist_callback

    def _save(self):
        self._persist(self._job_id, dict(self))

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._save()

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        self._save()


class JobsStore(dict):
    def __init__(self, persist_callback):
        super().__init__()
        self._persist = persist_callback

    def __setitem__(self, key, value):
        state = value if isinstance(value, JobState) else JobState(key, value, self._persist)
        super().__setitem__(key, state)
        self._persist(key, dict(state))


_init_jobs_db()
jobs = JobsStore(_persist_job_to_db)
for _job_id, _payload in _load_jobs_from_db().items():
    dict.__setitem__(jobs, _job_id, JobState(_job_id, _payload, _persist_job_to_db))

# --- Models ---
class LoginRequest(BaseModel):
    username: str

class BrollSearchRequest(BaseModel):
    query: str

class PlanRequest(BaseModel):
    srt_content: str

class RenderRequest(BaseModel):
    clips: List[dict]

class RenderActionRequest(BaseModel):
    plan: Optional[List[dict]] = None

# --- Auth ---
@app.post("/api/login")
async def login(data: LoginRequest):
    return {"session": str(uuid.uuid4())}

# --- B-Roll Library Endpoints ---
@app.post("/api/broll/ingest")
async def ingest_broll(file: UploadFile):
    """
    Upload a video, extract keyframes, describe them, and add to library.
    """
    video_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{video_id}_{file.filename}")
    
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    # Process in background or await? 
    # For now, let's await to keep it simple and sync, though it might time out.
    # In a real app, this should be a background task. 
    # Since we are in a dev environment with limited resources, let's do it sync but warn user.
    # Or better, use background tasks but we need a way to poll status.
    # The user asked to "assess clips... and generate metadata".
    # Let's do it inline for now as the user said "We'll worry about details... later".
    
    try:
        # 1. Extract Keyframes
        print(f"Extracting keyframes for {file.filename}...")
        keyframes = extraction.extract_keyframes(file_path, KEYFRAMES_DIR)
        
        # 2. Describe Keyframes
        print(f"Describing {len(keyframes)} keyframes...")
        for kf in keyframes:
            # Generate description
            desc = description.describe_keyframe(kf["image_path"])
            kf["description"] = desc
            
            # Generate embedding
            emb = embedding.generate_embedding(desc)
            kf["embedding"] = emb
            
            # Add relative URL for serving
            # We serve files from /files/{filename}. 
            # Need to ensure KEYFRAMES_DIR content is accessible via get_file or static mount.
            # Our get_file checks OUTPUT_DIR and UPLOAD_DIR. Let's update get_file or add KEYFRAMES_DIR to it.
            # Or just update get_file to look in KEYFRAMES_DIR too.
            kf["keyframe_path"] = f"/files/{kf['image_filename']}"
            
        # 3. Store
        storage.add_items(keyframes)
        
        return {"status": "success", "video_id": video_id, "keyframes_count": len(keyframes)}
        
    except Exception as e:
        print(f"Error processing video: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/broll/search")
async def search_broll(query: str = ""):
    """
    Search B-roll library by semantic query.
    """
    query_emb = None
    if query:
        query_emb = embedding.generate_embedding(query)
        
    results = storage.search_library(query, query_emb)
    return {"results": results}

@app.get("/api/broll/library")
async def get_broll_library():
    """Get all B-roll items."""
    items = storage.get_all_items()
    return {"items": items}

# --- Story Workflow Endpoints ---
@app.post("/api/jobs/upload")
async def upload_job_video(file: UploadFile):
    job_id = str(uuid.uuid4())
    upload_path = os.path.join(UPLOAD_DIR, f"{job_id}_{file.filename}")
    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    jobs[job_id] = {
        "status": "uploaded",
        "video_path": upload_path,
        "filename": file.filename
    }
    return {"job_id": job_id, "status": "uploaded"}

@app.post("/api/jobs/{job_id}/transcribe")
async def transcribe_job(job_id: str, background_tasks: BackgroundTasks):
    if job_id not in jobs:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    
    jobs[job_id]["status"] = "transcribing"
    
    async def run_transcription():
        try:
            if HAS_FFMPEG and HAS_HF_TOKEN:
                print(f"Starting real transcription for {job_id}")
                video_path = jobs[job_id]["video_path"]
                hf_token = os.getenv("HUGGINGFACE_TOKEN")
                
                # Run in thread pool to not block async loop
                loop = asyncio.get_running_loop()
                srt_path = await loop.run_in_executor(
                    None, 
                    transcribe.transcribe_video, 
                    video_path, 
                    hf_token
                )
                
                # Read SRT content
                with open(srt_path, "r") as f:
                    content = f.read()
                    
                jobs[job_id]["status"] = "transcribed"
                jobs[job_id]["srt_path"] = str(srt_path)
                jobs[job_id]["srt_content"] = content
                
            else:
                print(f"Mocking transcription (FFmpeg={HAS_FFMPEG}, HF_TOKEN={HAS_HF_TOKEN})")
                await asyncio.sleep(3)
                
                # Try to load from cache if available (Demo Mode)
                cached_srts = glob.glob("cache/*.srt.pkl")
                if cached_srts:
                    print(f"Loading cached SRT from {cached_srts[0]}")
                    try:
                        content = load_pickle(cached_srts[0])
                        jobs[job_id]["status"] = "transcribed"
                        jobs[job_id]["srt_content"] = content
                        # We don't have a real path, but that's okay for mock
                        jobs[job_id]["srt_path"] = "mock_cached.srt" 
                    except Exception as e:
                        print(f"Failed to load cache: {e}")
                        jobs[job_id]["status"] = "transcribed"
                        jobs[job_id]["srt_content"] = "1\n00:00:01,000 --> 00:00:04,000\nHello, this is a sample transcript.\n\n2\n00:00:04,500 --> 00:00:08,000\nWe are building an awesome video tool."
                else:
                    jobs[job_id]["status"] = "transcribed"
                    jobs[job_id]["srt_content"] = "1\n00:00:01,000 --> 00:00:04,000\nHello, this is a sample transcript.\n\n2\n00:00:04,500 --> 00:00:08,000\nWe are building an awesome video tool."
        except Exception as e:
            print(f"Transcription failed: {e}")
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["error"] = str(e)
    
    background_tasks.add_task(run_transcription)
    return {"status": "started"}

@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    return jobs.get(job_id, {"status": "not_found"})

@app.post("/api/jobs/{job_id}/plan")
async def generate_plan(job_id: str, request: PlanRequest):
    if job_id not in jobs:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    
    # Save the edited SRT
    jobs[job_id]["srt_content"] = request.srt_content
    jobs[job_id]["status"] = "planning"
    
    # Save SRT to file if it was edited or mocked
    srt_path = jobs[job_id].get("srt_path")
    if not srt_path or not os.path.exists(srt_path):
         # Create temp srt file
         video_path = jobs[job_id]["video_path"]
         srt_path = os.path.splitext(video_path)[0] + ".srt"
         with open(srt_path, "w") as f:
             f.write(request.srt_content)
         jobs[job_id]["srt_path"] = srt_path

    try:
        if HAS_GITHUB_TOKEN or HAS_OPENAI_KEY:
            # Run real summarization
            loop = asyncio.get_running_loop()
            json_path = await loop.run_in_executor(
                None,
                summarize.select_story_segments,
                srt_path
            )
            
            # Load the plan
            with open(json_path, "r") as f:
                plan = json.load(f)
                
            jobs[job_id]["status"] = "planned"
            jobs[job_id]["plan"] = plan
            jobs[job_id]["plan_path"] = str(json_path)
            
        else:
            # Mock but smart: pick random segments from the SRT
            await asyncio.sleep(2)
            
            # Parse the SRT
            try:
                # If we have a path, use it. If not (edited content only), write temp again?
                # We ensured srt_path exists above.
                segments = summarize.parse_srt(srt_path)
                
                # Pick 3-5 random consecutive segments as a "story"
                if segments:
                    start_idx = random.randint(0, max(0, len(segments) - 5))
                    mock_plan = segments[start_idx : start_idx + 5]
                else:
                    mock_plan = [
                        {"start": "00:00:01.000", "end": "00:00:04.000", "spoken_text": "Hello, this is a sample transcript."},
                        {"start": "00:00:04.500", "end": "00:00:08.000", "spoken_text": "We are building an awesome video tool."}
                    ]
            except Exception as e:
                print(f"Failed to parse SRT for mock plan: {e}")
                mock_plan = [
                    {"start": "00:00:01.000", "end": "00:00:04.000", "spoken_text": "Hello, this is a sample transcript."},
                    {"start": "00:00:04.500", "end": "00:00:08.000", "spoken_text": "We are building an awesome video tool."}
                ]
            
            jobs[job_id]["status"] = "planned"
            jobs[job_id]["plan"] = mock_plan
            
        return {"status": "planned", "plan": jobs[job_id]["plan"]}
        
    except Exception as e:
        print(f"Planning failed: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/jobs/{job_id}/render")
async def render_video(job_id: str, request: RenderRequest, background_tasks: BackgroundTasks):
    if job_id not in jobs:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    
    jobs[job_id]["status"] = "rendering"
    
    # Save plan to json if modified
    # In real flow, we might need to update the json file if user re-ordered clips
    # But for now assuming simple flow
    
    async def run_render():
        try:
            if HAS_FFMPEG:
                video_path = jobs[job_id]["video_path"]
                # We need a json file for cut_segments
                # Use the one we generated or create new one from request.clips
                
                # Let's write request.clips to a temp file to support re-ordering/editing
                plan_path = os.path.splitext(video_path)[0] + ".final_plan.json"
                
                # Transform request.clips back to expected format if needed
                # Request clips: [{"start":..., "end":...}]
                # Pipeline expects: same
                import json
                with open(plan_path, "w") as f:
                    json.dump(request.clips, f)
                    
                loop = asyncio.get_running_loop()
                
                # 1. Cut segments
                output_dir = os.path.join(OUTPUT_DIR, f"{job_id}_clips")
                await loop.run_in_executor(
                    None,
                    video_utils.cut_segments,
                    video_path,
                    plan_path,
                    output_dir
                )
                
                # 2. Concat
                final_output = os.path.join(OUTPUT_DIR, f"{job_id}_final.mp4")
                await loop.run_in_executor(
                    None,
                    video_utils.concat_clips,
                    output_dir,
                    final_output
                )
                
                jobs[job_id]["status"] = "done"
                jobs[job_id]["final_video_url"] = f"/files/{os.path.basename(final_output)}"
                
            else:
                await asyncio.sleep(3)
                jobs[job_id]["status"] = "done"
                # Return the original video as "final" since we can't render
                # Or just a placeholder
                jobs[job_id]["final_video_url"] = f"/files/{jobs[job_id]['filename']}" 
                
        except Exception as e:
            print(f"Render failed: {e}")
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["error"] = str(e)
            
    background_tasks.add_task(run_render)
    
    return {"status": "started"}


# --- Action Cut Endpoints ---
@app.post("/api/action/ingest")
async def ingest_action(file: UploadFile, background_tasks: BackgroundTasks):
    """
    Upload and process an action video (Action Cut Workflow).
    Extracts keyframes and describes them in background.
    """
    job_id = str(uuid.uuid4())
    upload_path = os.path.join(UPLOAD_DIR, f"{job_id}_{file.filename}")
    
    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
        
    jobs[job_id] = {
        "type": "action",
        "status": "ingesting",
        "video_path": upload_path,
        "filename": file.filename,
        "segments": []
    }
    
    def run_ingest():
        try:
            print(f"Starting action ingest for {job_id}")
            # Use KEYFRAMES_DIR/job_id to avoid clutter
            job_keyframes_dir = os.path.join(KEYFRAMES_DIR, job_id)
            os.makedirs(job_keyframes_dir, exist_ok=True)
            
            # Run the heavy lifting
            segments = ingest.ingest_action_video(upload_path, job_keyframes_dir)
            
            # Update paths for web serving
            for seg in segments:
                seg["image_url"] = f"/files/{job_id}/{seg['image_filename']}"
                
            jobs[job_id]["segments"] = segments
            jobs[job_id]["status"] = "ingested"
            print(f"Action ingest complete for {job_id}: {len(segments)} segments")
            
        except Exception as e:
            print(f"Action ingest failed: {e}")
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["error"] = str(e)
            
    background_tasks.add_task(run_ingest)
    
    return {"job_id": job_id, "status": "ingesting"}

@app.post("/api/action/{job_id}/plan")
async def plan_action_cut(job_id: str):
    """
    Generate an action highlight plan using LLM.
    """
    if job_id not in jobs:
        return JSONResponse({"error": "Job not found"}, status_code=404)
        
    job = jobs[job_id]
    if job.get("status") not in ["ingested", "planned"]:
        return JSONResponse({"error": "Job not ready (must be ingested)"}, status_code=400)
        
    try:
        segments = job["segments"]
        print(f"Identifying highlights for {len(segments)} segments...")
        
        # Call the identification logic
        selected_segments = identify.identify_action_highlights(segments)
        
        job["plan"] = selected_segments
        job["status"] = "planned"
        
        return {"status": "planned", "plan": selected_segments}
        
    except Exception as e:
        print(f"Action planning failed: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/action/{job_id}/render")
async def render_action_cut(job_id: str, request: RenderActionRequest, background_tasks: BackgroundTasks):
    """
    Render the final action highlight video.
    """
    if job_id not in jobs:
        return JSONResponse({"error": "Job not found"}, status_code=404)
        
    job = jobs[job_id]
    
    # Update plan if provided
    if request.plan:
        job["plan"] = request.plan
        
    if "plan" not in job or not job["plan"]:
        return JSONResponse({"error": "No plan found (must run plan first)"}, status_code=400)
        
    job["status"] = "rendering"
    
    def run_render():
        try:
            print(f"Starting action render for {job_id}")
            output_filename = os.path.join(OUTPUT_DIR, f"{job_id}_action_highlight.mp4")
            
            # Run assembly
            final_path = assemble.assemble_action_cut(
                job["video_path"],
                job["plan"],
                output_filename
            )
            
            job["final_video_url"] = f"/files/{os.path.basename(final_path)}"
            job["status"] = "done"
            print(f"Action render complete: {final_path}")
            
        except Exception as e:
            print(f"Action render failed: {e}")
            job["status"] = "failed"
            job["error"] = str(e)
            
    background_tasks.add_task(run_render)
    
    return {"status": "rendering"}

# --- File Serving ---
@app.get("/files/{path:path}")
async def get_file(path: str):
    # Check in all possible directories
    # Logic extended to support subdirectories (like job_id/frame.jpg)
    
    # Secure path check to prevent traversal
    if ".." in path:
        return JSONResponse({"error": "Invalid path"}, status_code=400)
        
    possible_roots = [
        OUTPUT_DIR,
        UPLOAD_DIR,
        KEYFRAMES_DIR
    ]
    
    for root in possible_roots:
        full_path = os.path.join(root, path)
        if os.path.exists(full_path) and os.path.isfile(full_path):
            return FileResponse(full_path)
            
    return JSONResponse({"error": "File not found"}, status_code=404)

# Mount frontend (catch-all for SPA)
# Note: In dev, we use Vite's proxy. In prod, we mount the build folder.
if os.path.exists("app/frontend/dist"):
    app.mount("/", StaticFiles(directory="app/frontend/dist", html=True), name="static")
