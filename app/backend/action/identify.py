from typing import List, Dict
import json
import os
from app.backend.llm_client import get_llm_client

def identify_action_highlights(segments: List[Dict], target_duration: int = 60) -> List[Dict]:
    """
    Analyze segment descriptions and select highlights for an action cut.
    Returns a list of selected segments in order.
    """
    # Prefer gh_copilot for this as it handles large context (many descriptions) well
    # But fallback to azure/openai if not available
    provider = os.getenv("LLM_PROVIDER", "gh_copilot")
    client = get_llm_client(provider)
    
    # 1. Prepare context
    descriptions = []
    for i, seg in enumerate(segments):
        # Add index to segment for easy lookup later
        seg["original_index"] = i
        descriptions.append(f"ID: {i} | Time: {seg['timestamp']:.1f}s - {seg['end_timestamp']:.1f}s | Desc: {seg['description']}")
    
    context_text = "\n".join(descriptions)
    
    # 2. Construct Prompt
    prompt = f"""
You are an expert video editor creating a high-energy action highlight reel.
Here are the descriptions of the video segments available:

{context_text}

Your task:
1. Identify the most exciting, clear, and visually interesting segments.
2. Select enough segments to create a video approximately {target_duration} seconds long.
3. Order them to create a compelling narrative flow (e.g. build up tension, peak action, resolution).
4. Return the selected segments as a JSON list of objects with 'id' (matching the ID provided above) and 'reason' (why you selected it).

Output Format:
```json
[
    {{"id": 0, "reason": "Intro shot establishing the scene"}},
    {{"id": 5, "reason": "High speed movement, very exciting"}},
    ...
]
```
Only return the JSON.
"""

    messages = [{"role": "user", "content": prompt}]
    
    print("Sending descriptions to LLM for action planning...")
    response = client.chat(messages)
    
    # 3. Parse Response
    try:
        # Extract JSON from markdown code block if present
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            json_str = response.split("```")[1].strip()
        else:
            json_str = response.strip()
            
        plan = json.loads(json_str)
        
        # Map back to full segment objects
        selected_segments = []
        for item in plan:
            idx = int(item["id"])
            if 0 <= idx < len(segments):
                seg = segments[idx].copy()
                seg["selection_reason"] = item["reason"]
                selected_segments.append(seg)
                
        return selected_segments
        
    except Exception as e:
        print(f"Failed to parse LLM plan: {e}")
        print(f"Raw response: {response}")
        # Fallback: Return all segments if parsing fails? Or maybe just top 5?
        # For now, return empty list to signal failure
        return []
