import os
import re
import json
from pathlib import Path
from dotenv import load_dotenv
from app.backend.llm_client import get_llm_client, GHCopilotCLIClient

load_dotenv()

def parse_srt(srt_path: str) -> list[dict]:
    """Parse SRT file into a list of segments."""
    segments = []
    with open(srt_path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    
    blocks = content.split("\n\n")
    for block in blocks:
        lines = block.split("\n")
        if len(lines) >= 3:
            # multiple lines of text might exist
            timestamp_line = lines[1]
            text = " ".join(lines[2:])
            
            # extract timestamps "00:00:01,000 --> 00:00:04,000"
            times = timestamp_line.split(" --> ")
            if len(times) == 2:
                start, end = times
                segments.append({
                    "start": start.replace(",", "."), 
                    "end": end.replace(",", "."), 
                    "spoken_text": text
                })
    return segments

def extract_text_from_srt(srt_path: str) -> str:
    """Return raw text from SRT for GPT input."""
    segments = parse_srt(srt_path)
    return "\n".join([f"{s['start']} --> {s['end']} {s['spoken_text']}" for s in segments])

def select_story_segments(srt_path: str, max_duration: int = 120, model="gpt-4o-mini") -> Path:
    """Call LLM to select key story segments and save JSON."""
    srt_text = extract_text_from_srt(srt_path)
    output_json = Path(srt_path).with_suffix(".story_segments.json")
    
    # Use gh_copilot by default for summarization due to context window requirements
    # unless LLM_PROVIDER is explicitly set to something else that can handle it
    provider = os.getenv("LLM_PROVIDER", "gh_copilot")
    client = get_llm_client(provider)
    
    # If using Azure with default token, we warn about limits
    # But llm_client handles the abstraction.
    
    print(f"🚀 Using LLM Provider: {provider}")

    system_prompt = f"""
    You are a video editor creating a concise {max_duration}-second story from this SRT transcript.
    Your task is to down-select the most meaningful spoken moments that together form a cohesive story.

    Return only the essential timestamped dialogue segments that preserve:
    - chronological order
    - emotional continuity and completeness of thought
    - total combined runtime of about {max_duration} seconds (±10 seconds)
    - ie Select segments totaling close to 120 seconds of cumulative duration
    - use timestamps exactly as in the transcript
    - do not fabricate or merge lines from different timestamps
    - ignore visual or b-roll info
    - preserve tone and authenticity
    - Remove any segments that are interviewer or narrator questions.
    - If you merge adjacent dialogue lines, set the "start" equal to the earliest start time among them,
    and the "end" equal to the latest end time among them.

    Output ONLY valid JSON (no markdown, no extra text):
    [
    {{"start": "HH:MM:SS.xx", "end": "HH:MM:SS.xx", "spoken_text": "verbatim text"}}
    ]
    """
    
    user_prompt = f"Read the file {os.path.abspath(srt_path)}.\nHere is the full SRT transcript:\n\n{srt_text}\n\nReturn only the JSON list."
    
    # For GHCopilotCLI, passing the file path in prompt helps it look up file context if needed, 
    # but we are also providing full text.
    
    print("⏳ Calling LLM to select story segments...")
    
    try:
        response_text = client.chat([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ], model=model)
        
        # Parse JSON
        try:
            segments = json.loads(response_text)
            
            def normalize_ts(ts: str) -> str:
                return re.sub(r",", ".", ts.strip())

            for seg in segments:
                seg["start"] = normalize_ts(seg["start"])
                seg["end"]   = normalize_ts(seg["end"])

            Path(output_json).write_text(json.dumps(segments, indent=2), encoding="utf-8")
            print(f"✅ Saved {len(segments)} story segments to {output_json}")
            return output_json
        except json.JSONDecodeError:
            print(f"❌ LLM returned invalid JSON: {response_text[:100]}...")
            raise
            
    except Exception as e:
        print(f"❌ LLM failed: {e}")
        print("⚠️ Falling back to mock segments.")
        mock_segments = parse_srt(srt_path)[:5]
        Path(output_json).write_text(json.dumps(mock_segments, indent=2), encoding="utf-8")
        return output_json

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    sample_srt = "sample_videos/interview1.srt"
    if os.path.exists(sample_srt):
        select_story_segments(sample_srt, model="gpt-4o")
    else:
        print(f"Sample file {sample_srt} not found. Please provide a path.")