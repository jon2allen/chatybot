# src/chatybot/image_manager.py
import os
import base64
from pathlib import Path
from typing import Optional, Tuple


class ImageManager:
    """Manages image loading, saving, and directory operations."""
    
    def __init__(self):
        self.image_dir = os.path.expanduser("~/chatybot_images")
    
    def set_directory(self, path: str) -> None:
        """Set the default image directory."""
        self.image_dir = os.path.expanduser(path)
        os.makedirs(self.image_dir, exist_ok=True)
        print(f"Image directory set to: {self.image_dir}")
    
    def load_image_data(self, file_path: str) -> Tuple[str, str]:
        """
        Load an image from disk and return (mime_type, base64_data).
        
        Used for loading saved images into imagebanks.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {file_path}")
        
        # Detect format from extension
        ext = path.suffix.lower()
        if ext in ['.jpg', '.jpeg']:
            mime_type = 'image/jpeg'
        elif ext == '.png':
            mime_type = 'image/png'
        elif ext == '.webp':
            mime_type = 'image/webp'
        else:
            raise ValueError(f"Unsupported image format: {ext}")
        
        with open(file_path, "rb") as f:
            data = f.read()
        
        base64_data = base64.b64encode(data).decode('utf-8')
        return mime_type, base64_data
    
    def get_image_directory(self) -> str:
        """Get the current image directory."""
        return self.image_dir
