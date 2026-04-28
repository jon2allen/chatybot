#! /usr/bin/env python3
"""
Image Manager Module
Handles image loading, saving, and directory management for saved images
"""

import base64
import os
from pathlib import Path
from typing import Any, Optional, Tuple
import aiohttp


class ImageManager:
    """Manages image loading, saving, and directory operations."""
    
    def __init__(self):
        """Initialize the image manager."""
        self.image_dir = os.path.expanduser("~/chatybot_images")
        os.makedirs(self.image_dir, exist_ok=True)
    
    def set_directory(self, path: str) -> None:
        """
        Set the default image directory.
        
        Args:
            path: Path to set as the image directory
        """
        self.image_dir = os.path.expanduser(path)
        os.makedirs(self.image_dir, exist_ok=True)
        print(f"Image directory set to: {self.image_dir}")
    
    def get_image_directory(self) -> str:
        """Get the current image directory."""
        return self.image_dir
    
    def load_image_data(self, file_path: str) -> Tuple[str, str]:
        """
        Load an image from disk and return (mime_type, base64_data).
        
        Used for loading saved images into imagebanks.
        
        Args:
            file_path: Path to the image file
            
        Returns:
            Tuple of (mime_type, base64_data)
            
        Raises:
            FileNotFoundError: If the image file doesn't exist
            ValueError: If the image format is unsupported
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
            raise ValueError(f"Unsupported image format: {ext}. Use .jpg, .jpeg, .png, or .webp")
        
        with open(file_path, "rb") as f:
            data = f.read()
        
        base64_data = base64.b64encode(data).decode('utf-8')
        return mime_type, base64_data
    
    def load_image_to_bank(self, file_path: str, bank_num: int, buffer_manager: Any) -> None:
        """
        Load an image into a buffer manager's image bank.
        
        Args:
            file_path: Path to the image file
            bank_num: Image bank number (1-5)
            buffer_manager: Reference to BufferManager instance
        """
        mime_type, base64_data = self.load_image_data(file_path)
        data_url = f"data:{mime_type};base64,{base64_data}"
        bank_name = f"imagebank{bank_num}"
        buffer_manager.image_banks[bank_name] = data_url
        print(f"Image '{file_path}' loaded into {bank_name}.")
    
    async def download_image(self, url: str, destination: Optional[str] = None) -> str:
        """
        Download an image from a URL.
        
        Args:
            url: URL of the image to download
            destination: Optional destination path (defaults to image_dir)
            
        Returns:
            Path to the downloaded image file
        """
        if destination is None:
            # Generate a filename from the URL
            import hashlib
            filename = hashlib.md5(url.encode()).hexdigest() + ".jpg"
            destination = os.path.join(self.image_dir, filename)
        
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    raise ValueError(f"Failed to download image: HTTP {resp.status}")
                
                with open(destination, "wb") as f:
                    while True:
                        chunk = await resp.content.read(1024 * 1024)  # 1MB chunks
                        if not chunk:
                            break
                        f.write(chunk)
        
        return destination
    
    def list_saved_images(self, date: Optional[str] = None) -> list:
        """
        List all saved image files, optionally filtered by date.
        
        Args:
            date: Optional date filter (YYYY-MM-DD format)
            
        Returns:
            List of image file paths
        """
        results = []
        image_dir = Path(self.image_dir)
        
        if not image_dir.exists():
            return results
        
        if date:
            # Only check specific date directory
            date_dir = image_dir / date
            if date_dir.exists():
                for img_file in date_dir.iterdir():
                    if img_file.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp']:
                        results.append(str(img_file))
        else:
            # Check all date directories
            for date_dir in sorted(image_dir.iterdir(), reverse=True):
                if date_dir.is_dir():
                    for img_file in date_dir.iterdir():
                        if img_file.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp']:
                            results.append(str(img_file))
        
        return results
    
    def get_image_size(self, file_path: str) -> Tuple[int, int]:
        """
        Get the dimensions of an image file.
        
        Args:
            file_path: Path to the image file
            
        Returns:
            Tuple of (width, height) in pixels
            
        Raises:
            ValueError: If the image cannot be read
        """
        try:
            from PIL import Image
            with Image.open(file_path) as img:
                return img.size
        except ImportError:
            # Fallback: try to get size from file metadata (less reliable)
            # This is a simplified approach without Pillow
            raise ValueError("Pillow library required for image size detection. Install with: pip install Pillow")
        except Exception as e:
            raise ValueError(f"Could not determine image size: {str(e)}")
    
    def convert_image_format(self, input_path: str, output_path: str, format: str) -> None:
        """
        Convert an image from one format to another.
        
        Args:
            input_path: Path to the source image
            output_path: Path for the converted image
            format: Target format ('JPEG', 'PNG', 'WEBP')
            
        Raises:
            ValueError: If conversion fails or formats are invalid
        """
        try:
            from PIL import Image
            with Image.open(input_path) as img:
                img.save(output_path, format=format)
        except ImportError:
            raise ValueError("Pillow library required for image conversion. Install with: pip install Pillow")
        except Exception as e:
            raise ValueError(f"Image conversion failed: {str(e)}")
