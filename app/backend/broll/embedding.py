import os
import time
from typing import List, Optional

try:
    from azure.ai.inference import EmbeddingsClient
    from azure.core.credentials import AzureKeyCredential
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False
    print("Warning: Azure AI Inference SDK not found or EmbeddingsClient missing.")

def get_client():
    if not AZURE_AVAILABLE:
        return None
        
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("Warning: GITHUB_TOKEN not found")
        return None
        
    return EmbeddingsClient(
        endpoint="https://models.inference.ai.azure.com",
        credential=AzureKeyCredential(token),
    )

def generate_embedding(text: str) -> Optional[List[float]]:
    """
    Generate embedding for text using text-embedding-3-small via GitHub Models.
    """
    if not text:
        return None
        
    client = get_client()
    if not client:
        # Mock embedding for dev if no token
        # Return a random vector or just None
        return [0.1] * 1536 

    try:
        response = client.embed(
            model="text-embedding-3-small",
            input=[text]
        )
        return response.data[0].embedding
        
    except Exception as e:
        print(f"Embedding error: {e}")
        return None
