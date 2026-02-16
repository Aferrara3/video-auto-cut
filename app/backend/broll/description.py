import os
import base64
import time
from io import BytesIO
from PIL import Image
import cv2
import numpy as np
from typing import List, Dict, Optional
from app.backend.llm_client import get_llm_client

def encode_image_to_base64(image_path: str, max_size: int = 512) -> str:
    """
    Encode image file to base64 string for API transmission.
    Resizes to max_size to reduce API costs.
    """
    # Read image using OpenCV to easily resize
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read image: {image_path}")
        
    # Convert BGR to RGB
    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    # Resize
    height, width = rgb_img.shape[:2]
    if max(height, width) > max_size:
        scale = max_size / max(height, width)
        new_width = int(width * scale)
        new_height = int(height * scale)
        rgb_img = cv2.resize(rgb_img, (new_width, new_height))
    
    # Convert to PIL Image
    pil_img = Image.fromarray(rgb_img)
    
    # Encode to base64
    buffer = BytesIO()
    pil_img.save(buffer, format="JPEG", quality=85)
    img_bytes = buffer.getvalue()
    
    return base64.b64encode(img_bytes).decode('utf-8')

def describe_keyframe(image_path: str, retry_count: int = 3) -> str:
    """
    Generate a semantic description of a keyframe using GPT-4o.
    """
    # Prefer Azure/OpenAI for vision tasks as gh_copilot CLI is text-focused
    preferred_provider = os.getenv("LLM_PROVIDER", "azure").lower()
    if preferred_provider == "gh_copilot":
        preferred_provider = "azure"

    provider_chain = [preferred_provider]
    for fallback in ("openai", "azure"):
        if fallback not in provider_chain:
            provider_chain.append(fallback)

    try:
        base64_image = encode_image_to_base64(image_path)
    except Exception as e:
        return f"[Error encoding image: {str(e)}]"
    
    prompt_text = """Describe this video frame in detail for semantic search purposes. Include:
- The main subject(s) and their actions
- The setting/environment
- Notable objects or elements
- The mood or atmosphere
- Any text visible in the frame

Keep it concise but informative (2-3 sentences).

Do not include boilerplate fluff phrasing such as 'This video frame showcases' or 'In this scene, we see'. Just provide the description directly.
"""
    
    # Construct message with image once
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt_text},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
            ]
        }
    ]

    last_error = None
    for provider in provider_chain:
        client = get_llm_client(provider)
        if not client:
            continue
        for attempt in range(retry_count):
            try:
                response = client.chat(messages, model="gpt-4o", temperature=0.7)
                return response.strip()
            except Exception as e:
                last_error = e
                if attempt < retry_count - 1:
                    print(f"API error ({provider}, attempt {attempt+1}): {e}")
                    time.sleep(2 ** attempt)
                else:
                    print(f"Failed with provider '{provider}': {e}")

    return f"[Error: {str(last_error) if last_error else 'No suitable LLM provider available'}]"
