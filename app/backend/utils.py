import hashlib

def hash_file(file_path, algo="sha256", chunk_size=8192):
    """Return hash digest (hex string) of file using the specified algorithm."""
    h = getattr(hashlib, algo)()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()

import pickle
from pathlib import Path
from typing import Any, Optional

def save_pickle(data: Any, filepath: str, create_dirs: bool = True) -> None:
    """
    Save data to a pickle file.
    
    Args:
        data: Data to serialize and save
        filepath: Path where to save the pickle file
        create_dirs: If True, create parent directories if they don't exist
    """
    path = Path(filepath)
    if create_dirs:
        path.parent.mkdir(parents=True, exist_ok=True)
        
    with open(path, 'wb') as f:
        pickle.dump(data, f)

def load_pickle(filepath: str, default: Optional[Any] = None) -> Any:
    """
    Load data from a pickle file.
    
    Args:
        filepath: Path to the pickle file to load
        default: Value to return if file doesn't exist
    
    Returns:
        Deserialized data from pickle file or default if file doesn't exist
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Pickle file not found: {filepath}")
        
    with open(path, 'rb') as f:
        return pickle.load(f)
    
from pathlib import Path
from typing import Optional, Any
import pickle


def save_path_pickle(path_obj: Path | str, filepath: str, create_dirs: bool = True) -> None:
    """
    Save a Path object to a pickle file.
    
    Args:
        path_obj: The Path (or string) to serialize and save
        filepath: Path where to save the pickle file
        create_dirs: If True, create parent directories if they don't exist
    """
    path = Path(filepath)
    if create_dirs:
        path.parent.mkdir(parents=True, exist_ok=True)

    # Always store as a Path for consistency
    to_save = Path(path_obj)

    with open(path, 'wb') as f:
        pickle.dump(to_save, f)


def load_path_pickle(filepath: str) -> Path:
    """
    Load a Path object from a pickle file.
    
    Args:
        filepath: Path to the pickle file to load
        
    Returns:
        A Path object deserialized from the pickle file
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Pickle file not found: {filepath}")

    with open(path, 'rb') as f:
        loaded = pickle.load(f)

    # Ensure return type is a Path even if original was a str
    return Path(loaded)

    
# Example usage
if __name__ == "__main__":
    file_path = "/home/rari/Documents/git/video-auto-cut/uploads/99a4d767-57e3-4474-9428-0ef24c763c01_story_concat.mp4"
    print("SHA256:", hash_file(file_path))
