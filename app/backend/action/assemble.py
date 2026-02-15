import subprocess
import os
from typing import List, Dict

def assemble_action_cut(input_video: str, segments: List[Dict], output_filename: str = "action_highlight.mp4") -> str:
    """
    Cut and assemble action segments into a final video.
    """
    # Create temp dir for clips
    # Use absolute path to avoid ffmpeg confusion
    base_dir = os.path.dirname(os.path.abspath(output_filename))
    temp_dir = os.path.join(base_dir, "action_clips_temp")
    os.makedirs(temp_dir, exist_ok=True)
    
    concat_list_path = os.path.join(temp_dir, "concat_list.txt")
    clip_paths = []
    
    print(f"Cutting {len(segments)} segments...")
    
    for i, seg in enumerate(segments):
        start = seg["timestamp"]
        end = seg["end_timestamp"]
        
        # Ensure we don't cut past end of video (handled by ffmpeg usually but good to be safe)
        
        clip_name = f"clip_{i:03d}.mp4"
        clip_path = os.path.join(temp_dir, clip_name)
        clip_paths.append(clip_path)
        
        # ffmpeg command to cut segment
        # Re-encoding is safer for concatenation to ensure consistent timebase
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-ss", str(start),
            "-to", str(end),
            "-i", input_video,
            "-c:v", "libx264", "-c:a", "aac",
            "-avoid_negative_ts", "make_zero",
            clip_path
        ]
        
        subprocess.run(cmd, check=True)
        print(f"  Cut segment {i}: {start:.1f}s - {end:.1f}s")

    # Create concat list
    with open(concat_list_path, "w") as f:
        for path in clip_paths:
            f.write(f"file '{path}'\n")
            
    # Concatenate
    print("Concatenating clips...")
    output_path = os.path.abspath(output_filename)
    cmd_concat = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_list_path,
        "-c", "copy",
        output_path
    ]
    
    subprocess.run(cmd_concat, check=True)
    print(f"✅ Action highlight created: {output_path}")
    
    # Cleanup (optional - keeping for debug might be good)
    # import shutil
    # shutil.rmtree(temp_dir)
    
    return output_path
