import os
import re
import json
from pathlib import Path
from openai import OpenAI


def extract_text_from_srt(srt_path: str) -> str:
    """Return raw text from SRT for GPT input."""
    text_blocks = []
    with open(srt_path, "r", encoding="utf-8") as f:
        block = []
        for line in f:
            line = line.strip()
            if not line:
                if block:
                    text_blocks.append(" ".join(block))
                    block = []
            else:
                block.append(line)
        if block:
            text_blocks.append(" ".join(block))
    return "\n".join(text_blocks)


def select_story_segments(srt_path: str, max_duration: int = 120, model="gpt-5") -> Path:
    """Call LLM to select key story segments and save JSON."""
    srt_text = extract_text_from_srt(srt_path)
    output_json = Path(srt_path).with_suffix(".story_segments.json")

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    system_prompt = f"""
    You are a video editor creating a concise {max_duration}-second story from a full interview transcript in SRT format.
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

    Output only valid JSON: a list of objects like
    [
    {{"start": "HH:MM:SS.xx", "end": "HH:MM:SS.xx", "spoken_text": "verbatim text"}}
    ]
    """

    user_prompt = f"Here is the full SRT transcript:\n\n{srt_text}\n\nReturn only the JSON list."
    
    print("⏳ Calling LLM to select story segments...")

    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        reasoning={"effort": "medium"},
    )

    raw = resp.output_text.strip()
    if "```" in raw:
        raw = re.sub(r"^```[a-zA-Z0-9]*\n?", "", raw)
        raw = raw.replace("```", "").strip()

    try:
        segments = json.loads(raw)
    except json.JSONDecodeError:
        Path("story_segments_raw.txt").write_text(raw, encoding="utf-8")
        raise RuntimeError("Model output was not valid JSON; saved raw text.")
    
    def normalize_ts(ts: str) -> str:
        """Convert SRT-style timestamps (00:00:12,560) -> ffmpeg-friendly (00:00:12.560)."""
        return re.sub(r",", ".", ts.strip())

    for seg in segments:
        seg["start"] = normalize_ts(seg["start"])
        seg["end"]   = normalize_ts(seg["end"])

    Path(output_json).write_text(json.dumps(segments, indent=2), encoding="utf-8")
    print(f"✅ Saved {len(segments)} story segments to {output_json}")
    return output_json

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    select_story_segments("interview1.srt", model="gpt-5-nano")