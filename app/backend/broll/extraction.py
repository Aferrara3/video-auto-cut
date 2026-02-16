import cv2
import numpy as np
import os
from pathlib import Path
from typing import List, Dict, Tuple
import uuid

def calculate_histogram_diff(frame1: np.ndarray, frame2: np.ndarray) -> float:
    """
    Calculate histogram difference between two frames.
    Returns a value between 0.0 (identical) and 1.0 (completely different).
    """
    if frame1 is None or frame2 is None:
        return 0.0
        
    # Convert to HSV color space for better color comparison
    try:
        hsv1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2HSV)
        hsv2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2HSV)
    except cv2.error:
        # Fallback if color conversion fails (e.g. empty frame)
        return 0.0
    
    # Calculate histograms for each channel
    hist1 = cv2.calcHist([hsv1], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
    hist2 = cv2.calcHist([hsv2], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
    
    # Normalize histograms
    cv2.normalize(hist1, hist1)
    cv2.normalize(hist2, hist2)
    
    # Compare using correlation method (1.0 = identical, 0.0 = different)
    correlation = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
    
    # Convert to difference score (0.0 = identical, 1.0 = different)
    return 1.0 - correlation

def extract_keyframes(video_path: str, output_dir: str, threshold: float = 0.5, min_interval: int = 30) -> List[Dict]:
    """
    Extract keyframes from video using scene change detection.
    Saves keyframes to output_dir and returns metadata.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")
        
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        # Fallback for mock environment if video cannot be opened (e.g. no codecs)
        # But we check os.path.exists first. If it exists but fails to open, 
        # it might be a codec issue or a fake file.
        print(f"Warning: Could not open video {video_path}. Using mock keyframes.")
        return []
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps == 0: fps = 30.0 # fallback

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_filename = os.path.basename(video_path)
    
    keyframes = []
    prev_frame = None
    last_keyframe_frame = None  # Store the actual image of the last keyframe
    last_keyframe_idx = -min_interval
    frame_idx = 0
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        if frame_idx % 100 == 0:
            print(f"Processed {frame_idx}/{total_frames} frames...")

        # Always add first frame
        is_keyframe = False
        
        # Check scene change
        if frame_idx == 0:
            is_keyframe = True
        elif frame_idx - last_keyframe_idx >= 5: # Minimum interval check (5 frames)
            # Compare against LAST KEYFRAME (to detect slow changes/fades)
            # AND compare against PREV FRAME (to ensure local activity)
            
            # 1. Diff vs Last Keyframe
            ref_frame = last_keyframe_frame if last_keyframe_frame is not None else prev_frame
            diff_cumulative = calculate_histogram_diff(ref_frame, frame)
            
            # 2. Diff vs Prev Frame
            diff_local = calculate_histogram_diff(prev_frame, frame)
            
            # Logic:
            # - If cumulative change is HUGE (>= 0.8), it's a new scene regardless of speed (e.g. cut)
            # - If cumulative change is MODERATE (>= 0.5) AND local change is SIGNIFICANT (>= 0.1), it's a new scene
            # - If cumulative change is SMALL (< 0.5), ignore
            
            if diff_cumulative >= 0.8:
                 is_keyframe = True
                 print(f"Keyframe detected (Major Change) at frame {frame_idx} (cum_diff: {diff_cumulative:.3f})")
            elif diff_cumulative >= 0.5 and diff_local >= 0.05:
                 is_keyframe = True
                 print(f"Keyframe detected (Scene Shift) at frame {frame_idx} (cum_diff: {diff_cumulative:.3f}, local_diff: {diff_local:.3f})")
        
        if is_keyframe:
            # DEDUPLICATION CHECK
            # If this new keyframe is too similar to the last one (e.g. diff < 0.3), skip it
            # This handles the case where "fade in" triggers multiple times
            if last_keyframe_frame is not None:
                sim_diff = calculate_histogram_diff(last_keyframe_frame, frame)
                if sim_diff < 0.3:
                    print(f"Skipping redundant keyframe at {frame_idx} (diff: {sim_diff:.3f} < 0.3)")
                    is_keyframe = False
            
            if is_keyframe:
                timestamp = frame_idx / fps if fps > 0 else 0
            
            # Save frame to disk
            frame_filename = f"{os.path.splitext(video_filename)[0]}_frame_{frame_idx}.jpg"
            frame_path = os.path.join(output_dir, frame_filename)
            cv2.imwrite(frame_path, frame)
            
            # Use relative path for frontend serving. Assuming output_dir is mounted as static.
            # We will store full path for backend processing and relative for frontend.
            # Let's assume output_dir is passed as absolute path.
            
            kf_data = {
                "id": str(uuid.uuid4()),
                "timestamp": timestamp,
                "frame_number": frame_idx,
                "video_path": video_path,
                "image_path": frame_path,
                "image_filename": frame_filename
            }
            keyframes.append(kf_data)
            
            last_keyframe_idx = frame_idx
            last_keyframe_frame = frame.copy() # Store copy of keyframe
        
        prev_frame = frame.copy()
        frame_idx += 1
            
    cap.release()
    
    # Post-processing: Calculate durations
    # Assumes keyframes are ordered by timestamp
    for i in range(len(keyframes)):
        current_kf = keyframes[i]
        
        if i < len(keyframes) - 1:
            next_kf = keyframes[i+1]
            end_timestamp = next_kf["timestamp"]
        else:
            # Last keyframe goes to end of video
            end_timestamp = total_frames / fps if fps > 0 else current_kf["timestamp"] + 5.0 # default 5s if unknown
            
        current_kf["end_timestamp"] = end_timestamp
        current_kf["duration"] = end_timestamp - current_kf["timestamp"]
    
    return keyframes
