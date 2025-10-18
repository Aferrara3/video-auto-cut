import subprocess
from pathlib import Path
import json

def concat_clips(clips_dir: str, output_path: str = "story_concat.mp4") -> Path:
    """Concatenate trimmed clips into one video."""
    clips_dir = Path(clips_dir)
    output = Path(output_path)
    concat_file = clips_dir / "concat_list.txt"

    clip_files = sorted(clips_dir.glob("*.mp4"))
    with concat_file.open("w", encoding="utf-8") as f:
        for clip in clip_files:
            f.write(f"file '{clip.resolve()}'\n")

    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_file), "-c", "copy", str(output)
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(f"✅ Concatenated {len(clip_files)} clips into {output}")
    return output

def cut_segments(input_video: str, segments_json: str, output_dir: str = "trimmed_clips") -> Path:
    """Trim selected story segments into clips."""
    input_video = Path(input_video)
    segments = json.loads(Path(segments_json).read_text())
    out_dir = Path(output_dir)
    out_dir.mkdir(exist_ok=True)

    for i, seg in enumerate(segments, start=1):
        start, end = seg["start"], seg["end"]
        clip_name = f"clip_{i:02d}_{start.replace(':', '-')}_{end.replace(':', '-')}.mp4"
        out_path = out_dir / clip_name

        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-ss", start, "-to", end, "-i", str(input_video),
            "-c:v", "libx264", "-c:a", "aac", "-y", str(out_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ ffmpeg failed: {out_path.name}\n{result.stderr}")
        else:
            print(f"✅ {out_path.name}")

    return out_dir

if __name__ == "__main__":
    cut_segments("interview1.mp4", "interview1.story_segments.json")
    concat_clips("trimmed_clips", "interview1.story_concat.mp4")