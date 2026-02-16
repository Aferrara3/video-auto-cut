import os
from typing import List, Dict
from app.backend.broll.extraction import extract_keyframes
from app.backend.broll.description import describe_keyframe

def extract_action_keyframes(video_path: str, output_dir: str) -> List[Dict]:
    """
    Step 1: Extract keyframes from an action video.
    Returns keyframes without descriptions.
    """
    print(f"Extracting keyframes from {video_path}...")
    # This will now include the periodic logging we added to extraction.py
    keyframes = extract_keyframes(video_path, output_dir)
    print(f"Extraction complete. Found {len(keyframes)} keyframes.")
    return keyframes

def describe_action_keyframes(keyframes: List[Dict]) -> List[Dict]:
    """
    Step 2: Describe the extracted keyframes.
    Updates the keyframes list in place and returns it.
    """
    total = len(keyframes)
    print(f"Starting description generation for {total} keyframes...")
    
    for i, kf in enumerate(keyframes):
        print(f"[{i+1}/{total}] Describing frame {kf['frame_number']}...")
        image_path = kf["image_path"]
        
        if os.path.exists(image_path):
            try:
                description = describe_keyframe(image_path)
                kf["description"] = description
                print(f"  -> {description[:60]}...")
            except Exception as e:
                print(f"  -> Error describing frame: {e}")
                kf["description"] = f"[Error: {str(e)}]"
        else:
            print(f"  -> Error: Image file not found at {image_path}")
            kf["description"] = "[Error: Image not found]"
            
    print("Description generation complete.")
    return keyframes

# Legacy wrapper for backward compatibility if needed, though we will update main.py
def ingest_action_video(video_path: str, output_dir: str) -> List[Dict]:
    keyframes = extract_action_keyframes(video_path, output_dir)
    return describe_action_keyframes(keyframes)
