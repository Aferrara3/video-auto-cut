import json
import os
import numpy as np
from typing import List, Dict

# Simple JSON-based storage for now
DB_PATH = "broll_library.json"

def load_library() -> List[Dict]:
    if not os.path.exists(DB_PATH):
        return []
    try:
        with open(DB_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return []

def save_library(library: List[Dict]):
    with open(DB_PATH, "w") as f:
        json.dump(library, f, indent=2)

def add_items(items: List[Dict]):
    library = load_library()
    library.extend(items)
    save_library(library)

def delete_item(item_id: str):
    library = load_library()
    new_library = [item for item in library if item["id"] != item_id]
    save_library(new_library)

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    if not v1 or not v2:
        return 0.0
    
    # Use numpy for speed if available, else manual
    try:
        a = np.array(v1)
        b = np.array(v2)
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    except Exception:
        return 0.0

def search_library(query: str, query_embedding: List[float] = None) -> List[Dict]:
    """
    Search by semantic similarity if embedding provided, else keyword.
    """
    library = load_library()
    if not query and not query_embedding:
        return library
        
    results = []
    
    # 1. Semantic Search (if embedding available)
    if query_embedding:
        for item in library:
            item_embedding = item.get("embedding")
            if item_embedding:
                score = cosine_similarity(query_embedding, item_embedding)
                if score > 0.2: # Threshold
                    results.append({**item, "score": float(score), "match_type": "semantic"})
    
    # 2. Keyword Search (Fallback or boost)
    query_terms = query.lower().split() if query else []
    for item in library:
        # Check if already added by semantic search
        existing = next((r for r in results if r["id"] == item["id"]), None)
        
        desc = item.get("description", "").lower()
        keyword_score = sum(1 for term in query_terms if term in desc)
        
        if keyword_score > 0:
            if existing:
                existing["score"] += (keyword_score * 0.1) # Boost semantic result
                existing["match_type"] = "hybrid"
            else:
                results.append({**item, "score": keyword_score * 0.1, "match_type": "keyword"})
            
    # Sort by score desc
    results.sort(key=lambda x: x["score"], reverse=True)
    return results

def get_all_items() -> List[Dict]:
    return load_library()
