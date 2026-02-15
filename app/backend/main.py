from fastapi import FastAPI, UploadFile, Form, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid, os, shutil, asyncio, subprocess, glob, json
from typing import List, Optional
from app.backend.broll import extraction, description, storage, embedding
from app.backend.pipeline import transcribe, summarize, video_utils
from app.backend.utils import load_pickle
import random

from dotenv import load_dotenv
load_dotenv()

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

# In-memory storage for prototype
jobs = {}

# --- Models ---
class LoginRequest(BaseModel):
    username: str

class BrollSearchRequest(BaseModel):
    query: str

class PlanRequest(BaseModel):
    srt_content: str

class RenderRequest(BaseModel):
    clips: List[dict]

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


# --- File Serving ---
@app.get("/files/{filename}")
async def get_file(filename: str):
    # Check in all possible directories
    possible_paths = [
        os.path.join(OUTPUT_DIR, filename),
        os.path.join(UPLOAD_DIR, filename),
        os.path.join(KEYFRAMES_DIR, filename)
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return FileResponse(path)
            
    return JSONResponse({"error": "File not found"}, status_code=404)

# Mount frontend (catch-all for SPA)
# Note: In dev, we use Vite's proxy. In prod, we mount the build folder.
if os.path.exists("app/frontend/dist"):
    app.mount("/", StaticFiles(directory="app/frontend/dist", html=True), name="static")
