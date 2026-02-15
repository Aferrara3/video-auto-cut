import os
from typing import List, Dict
from app.backend.broll.extraction import extract_keyframes
from app.backend.broll.description import describe_keyframe

def ingest_action_video(video_path: str, output_dir: str) -> List[Dict]:
    """
    Ingest an action video: extract keyframes and describe them.
    Returns a list of segments with descriptions.
    """
    # 1. Extract Keyframes
    print(f"Extracting keyframes from {video_path}...")
    keyframes = extract_keyframes(video_path, output_dir)
    
    # 2. Describe Keyframes
    print(f"Describing {len(keyframes)} keyframes...")
    for kf in keyframes:
        image_path = kf["image_path"]
        if os.path.exists(image_path):
            # Pass image path to description module
            # Note: describe_keyframe handles the LLM call
            description = describe_keyframe(image_path)
            kf["description"] = description
            print(f"Frame {kf['frame_number']}: {description[:50]}...")
        else:
            kf["description"] = "[Error: Image not found]"
            
    return keyframes
