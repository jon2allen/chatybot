#! /usr/bin/env python3
"""
Audio File Manager Module
Handles audio file storage, naming, index management (matches ImageGenerator pattern)
"""

import base64
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List


class AudioFileManager:
    """Manages audio file storage with date-based directory structure and counter persistence."""
    
    # Category and subtype mapping for file naming
    CATEGORY_GENERATE = "generate"
    CATEGORY_ANALYZE = "analyze"
    
    SUBTYPE_MAP = {
        "speak": "speech",
        "tts": "speech",
        "generate": "sfx",  # default for generation
        "sfx": "sfx",
        "sound": "sfx",
        "effect": "sfx",
        "music": "music",
        "song": "music",
        "compose": "music",
        "transcribe": "transcript",
        "stt": "transcript",
        "to_text": "transcript",
        "analyze": "describe",
        "describe": "describe",
        "classify": "recognition",
        "recognize": "recognition",
        "identify": "recognition",
        "detect": "recognition",
        "separate": "separate",
        "split": "separate",
        "isolate": "separate",
    }
    
    # File extensions by format
    FORMAT_EXTENSIONS = {
        "mp3": ".mp3",
        "wav": ".wav",
        "flac": ".flac",
        "ogg": ".ogg",
        "m4a": ".m4a",
        "webm": ".webm",
        "opus": ".opus",
        "aac": ".aac",
        "pcm": ".pcm",
        "json": ".json",
    }
    
    def __init__(self, audio_dir: Optional[str] = None, config_manager: Any = None):
        """
        Initialize the audio file manager.
        
        Args:
            audio_dir: Base directory for audio files (default: ~/chatybot_audio)
            config_manager: Optional reference to ConfigManager
        """
        self.config_manager = config_manager
        self.audio_dir = os.path.expanduser(audio_dir or "~/chatybot_audio")
        self.counters: Dict[str, Dict[str, int]] = {}  # {date: {category: {subtype: count}}}
        self.last_generated: Optional[Tuple[str, str, str]] = None  # (category, subtype, file_path)
        
        # Ensure directory exists
        os.makedirs(self.audio_dir, exist_ok=True)
        
        # Load existing counters from index.json files
        self._load_existing_counters()
    
    def _load_existing_counters(self) -> None:
        """Load counters from existing index.json files to prevent overwrite on restart."""
        audio_dir = Path(self.audio_dir)
        if not audio_dir.exists():
            return
        
        for date_dir in audio_dir.iterdir():
            if not date_dir.is_dir():
                continue
            
            index_path = date_dir / "index.json"
            if index_path.exists():
                try:
                    with open(index_path, "r") as f:
                        data = json.load(f)
                    counters = data.get("counters", {})
                    self.counters[date_dir.name] = counters
                except (json.JSONDecodeError, IOError):
                    # If index.json is corrupted, skip it
                    pass
    
    def set_directory(self, path: str) -> None:
        """Set the audio output directory."""
        self.audio_dir = os.path.expanduser(path)
        os.makedirs(self.audio_dir, exist_ok=True)
        # Reload counters
        self.counters = {}
        self._load_existing_counters()
    
    def get_audio_directory(self) -> str:
        """Get the current audio directory."""
        return self.audio_dir
    
    def _get_date_dir(self, date_str: Optional[str] = None) -> Path:
        """Get the date directory path."""
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
        date_path = Path(self.audio_dir) / date_str
        date_path.mkdir(exist_ok=True)
        return date_path
    
    def _get_next_counter(self, date_str: str, category: str, subtype: str) -> int:
        """Get the next counter value for a given category/subtype on a date."""
        if date_str not in self.counters:
            self.counters[date_str] = {}
        if category not in self.counters[date_str]:
            self.counters[date_str][category] = {}
        if subtype not in self.counters[date_str][category]:
            self.counters[date_str][category][subtype] = 0
        
        self.counters[date_str][category][subtype] += 1
        return self.counters[date_str][category][subtype]
    
    def _save_index(self, date_str: str) -> None:
        """Save counters to index.json for a given date."""
        index_path = self._get_date_dir(date_str) / "index.json"
        index_data = {
            "date": date_str,
            "counters": self.counters.get(date_str, {}),
            "total_files": self._count_files(date_str),
            "total_size_mb": self._calculate_total_size(date_str),
        }
        
        # Add models used if available
        if self.config_manager and hasattr(self.config_manager, 'audio_model'):
            index_data["models_used"] = [self.config_manager.audio_model]
        
        with open(index_path, "w") as f:
            json.dump(index_data, f, indent=2)
    
    def _count_files(self, date_str: str) -> int:
        """Count files in a date directory."""
        date_path = Path(self.audio_dir) / date_str
        if not date_path.exists():
            return 0
        return sum(1 for f in date_path.rglob("*") if f.is_file() and f.name != "index.json")
    
    def _calculate_total_size(self, date_str: str) -> float:
        """Calculate total size in MB for a date directory."""
        date_path = Path(self.audio_dir) / date_str
        if not date_path.exists():
            return 0.0
        total_bytes = sum(f.stat().st_size for f in date_path.rglob("*") if f.is_file())
        return total_bytes / (1024 * 1024)
    
    def generate_filename(
        self,
        category: str,
        subtype: str,
        format: str = "mp3",
        date_str: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Generate a unique filename for audio output.
        
        Args:
            category: Category (generate, analyze)
            subtype: Subtype (speech, sfx, music, transcript, recognition, etc.)
            format: Audio format (mp3, wav, etc.)
            date_str: Date string (YYYY-MM-DD), defaults to today
            
        Returns:
            Tuple of (date_str, filename)
        """
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
        
        # Get counter
        counter = self._get_next_counter(date_str, category, subtype)
        
        # Generate filename
        ext = self.FORMAT_EXTENSIONS.get(format, ".mp3")
        filename = f"{subtype}_{counter:03d}{ext}"
        
        return date_str, filename
    
    def get_output_path(
        self,
        category: str,
        subtype: str,
        format: str = "mp3",
        date_str: Optional[str] = None
    ) -> Path:
        """
        Get the full output path for a new audio file.
        
        Args:
            category: Category (generate, analyze)
            subtype: Subtype (speech, sfx, music, transcript, etc.)
            format: Audio format
            date_str: Date string
            
        Returns:
            Path to output file
        """
        date_str, filename = self.generate_filename(category, subtype, format, date_str)
        output_dir = self._get_date_dir(date_str) / category
        output_dir.mkdir(exist_ok=True)
        
        filepath = output_dir / filename
        self.last_generated = (category, subtype, str(filepath))
        
        # Save index after updating counters
        self._save_index(date_str)
        
        return filepath
    
    def save_audio_file(
        self,
        audio_bytes: bytes,
        category: str,
        subtype: str,
        format: str = "mp3",
        prompt: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        sample_rate: int = 44100,
        channels: int = 1,
        duration: Optional[float] = None,
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, str]:
        """
        Save audio bytes to a file and create metadata.
        
        Args:
            audio_bytes: Raw audio bytes
            category: Category (generate, analyze)
            subtype: Subtype (speech, sfx, music)
            format: Audio format
            prompt: The prompt/text used to generate
            model: Model name
            provider: Provider name
            sample_rate: Audio sample rate
            channels: Number of channels
            duration: Duration in seconds
            extra_metadata: Additional metadata to store
            
        Returns:
            Tuple of (file_path, base64_data_url)
        """
        # Get output path
        filepath = self.get_output_path(category, subtype, format)
        
        # Write audio file
        with open(filepath, "wb") as f:
            f.write(audio_bytes)
        
        # Create base64 data URL
        base64_data = base64.b64encode(audio_bytes).decode('utf-8')
        mime_type = f"audio/{format}" if format != "json" else "application/json"
        data_url = f"data:{mime_type};base64,{base64_data}"
        
        # Create metadata file
        meta_filepath = filepath.parent / f"{filepath.stem}.meta.json"
        metadata = {
            "filename": filepath.name,
            "category": category,
            "subtype": subtype,
            "format": format,
            "prompt": prompt,
            "model": model,
            "provider": provider,
            "sample_rate": sample_rate,
            "channels": channels,
            "duration": duration,
            "bitrate": len(audio_bytes) * 8 / duration if duration else None,
            "size_bytes": len(audio_bytes),
            "base64": data_url,
            "created": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        
        if extra_metadata:
            metadata.update(extra_metadata)
        
        with open(meta_filepath, "w") as f:
            json.dump(metadata, f, indent=2)
        
        return str(filepath), data_url
    
    def save_transcription(
        self,
        text: str,
        input_file: str,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        language: Optional[str] = None,
        duration: Optional[float] = None,
        speakers: Optional[List[Dict[str, Any]]] = None,
        word_timestamps: Optional[List[Dict[str, Any]]] = None,
        diarization: bool = False
    ) -> str:
        """
        Save transcription result to JSON file.
        
        Args:
            text: Transcribed text
            input_file: Input audio file path
            model: Model used
            provider: Provider name
            language: Detected language
            duration: Audio duration in seconds
            speakers: Speaker information (if diarization)
            word_timestamps: Word-level timestamps
            diarization: Whether diarization was used
            
        Returns:
            Path to saved JSON file
        """
        date_str = datetime.now().strftime("%Y-%m-%d")
        category = self.CATEGORY_ANALYZE
        subtype = "transcript"
        format = "json"
        
        counter = self._get_next_counter(date_str, category, subtype)
        filename = f"{subtype}_{counter:03d}.json"
        
        output_dir = self._get_date_dir(date_str) / category
        output_dir.mkdir(exist_ok=True)
        filepath = output_dir / filename
        self.last_generated = (category, subtype, str(filepath))
        
        # Build output data
        output_data = {
            "type": "transcription",
            "input_file": input_file,
            "model": model,
            "provider": provider,
            "text": text,
            "language": language,
            "duration": duration,
            "speakers": speakers,
            "word_timestamps": word_timestamps,
            "diarization": diarization,
            "created": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        
        with open(filepath, "w") as f:
            json.dump(output_data, f, indent=2)
        
        self._save_index(date_str)
        
        return str(filepath)
    
    def save_recognition(
        self,
        sounds: List[Dict[str, Any]],
        categories: Dict[str, float],
        input_file: str,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        detection_type: str = "environmental",
        duration: Optional[float] = None
    ) -> str:
        """
        Save sound recognition result to JSON file.
        
        Args:
            sounds: List of detected sounds with confidence, start, end
            categories: Category scores
            input_file: Input audio file path
            model: Model used
            provider: Provider name
            detection_type: Type of detection
            duration: Audio duration
            
        Returns:
            Path to saved JSON file
        """
        date_str = datetime.now().strftime("%Y-%m-%d")
        category = self.CATEGORY_ANALYZE
        subtype = "recognition"
        format = "json"
        
        counter = self._get_next_counter(date_str, category, subtype)
        filename = f"{subtype}_{counter:03d}.json"
        
        output_dir = self._get_date_dir(date_str) / category
        output_dir.mkdir(exist_ok=True)
        filepath = output_dir / filename
        self.last_generated = (category, subtype, str(filepath))
        
        output_data = {
            "type": "sound_recognition",
            "input_file": input_file,
            "model": model,
            "provider": provider,
            "detection_type": detection_type,
            "sounds": sounds,
            "categories": categories,
            "duration": duration,
            "created": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        
        with open(filepath, "w") as f:
            json.dump(output_data, f, indent=2)
        
        self._save_index(date_str)
        
        return str(filepath)
    
    def list_files(
        self,
        date_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
        subtype_filter: Optional[str] = None,
        format_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List audio files with optional filtering.
        
        Args:
            date_filter: Filter by date (YYYY-MM-DD)
            category_filter: Filter by category
            subtype_filter: Filter by subtype
            format_filter: Filter by format
            
        Returns:
            List of file info dictionaries
        """
        results = []
        audio_dir = Path(self.audio_dir)
        
        if not audio_dir.exists():
            return results
        
        for date_dir in sorted(audio_dir.iterdir(), reverse=True):
            if not date_dir.is_dir():
                continue
            
            if date_filter and date_dir.name != date_filter:
                continue
            
            for category_dir in date_dir.iterdir():
                if not category_dir.is_dir():
                    continue
                
                category = category_dir.name
                if category_filter and category != category_filter:
                    continue
                
                for filepath in sorted(category_dir.iterdir()):
                    if not filepath.is_file():
                        continue
                    if filepath.name == "index.json":
                        continue
                    
                    # Extract info from filename
                    name = filepath.stem
                    ext = filepath.suffix.lstrip('.')
                    
                    # Try to parse counter from filename
                    if '_' in name:
                        parts = name.rsplit('_', 1)
                        if parts[1].isdigit():
                            subtype = parts[0]
                            counter = int(parts[1])
                        else:
                            subtype = name
                            counter = 0
                    else:
                        subtype = name
                        counter = 0
                    
                    if subtype_filter and subtype != subtype_filter:
                        continue
                    if format_filter and ext != format_filter:
                        continue
                    
                    # Get size
                    size_bytes = filepath.stat().st_size
                    size_kb = size_bytes / 1024
                    
                    # Check for metadata file
                    meta_filepath = filepath.parent / f"{filepath.stem}.meta.json"
                    metadata = {}
                    if meta_filepath.exists():
                        try:
                            with open(meta_filepath, "r") as f:
                                metadata = json.load(f)
                        except (json.JSONDecodeError, IOError):
                            pass
                    
                    results.append({
                        "date": date_dir.name,
                        "category": category,
                        "subtype": subtype,
                        "format": ext,
                        "filename": filepath.name,
                        "filepath": str(filepath),
                        "size_bytes": size_bytes,
                        "size_kb": size_kb,
                        "counter": counter,
                        "metadata": metadata,
                    })
        
        return results
    
    def load_external_audio(self, file_path: str, target_format: str = "mp3") -> Tuple[bytes, Dict[str, Any]]:
        """
        Load external audio file and optionally convert format.
        
        Args:
            file_path: Path to audio file
            target_format: Target format (conversion not implemented yet)
            
        Returns:
            Tuple of (audio_bytes, metadata)
            
        Raises:
            FileNotFoundError: If file doesn't exist
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Audio file not found: {file_path}")
        
        with open(file_path, "rb") as f:
            audio_bytes = f.read()
        
        # Basic metadata from file
        ext = os.path.splitext(file_path)[1].lstrip('.')
        metadata = {
            "filename": os.path.basename(file_path),
            "format": ext,
            "size_bytes": len(audio_bytes),
        }
        
        # TODO: Add proper format conversion using pydub/ffmpeg
        # TODO: Add proper audio analysis (duration, sample_rate, etc.)
        
        return audio_bytes, metadata
    
    def detect_audio_format(self, file_path: str) -> str:
        """
        Detect audio MIME type from file extension.
        
        Args:
            file_path: Path to the audio file
            
        Returns:
            MIME type string (e.g., 'audio/mpeg', 'audio/wav')
        """
        ext = Path(file_path).suffix.lower().lstrip('.')
        format_map = {
            'mp3': 'audio/mpeg',
            'wav': 'audio/wav',
            'flac': 'audio/flac',
            'ogg': 'audio/ogg',
            'm4a': 'audio/m4a',
            'webm': 'audio/webm',
            'opus': 'audio/opus',
            'aac': 'audio/aac',
            'pcm': 'audio/pcm',
        }
        return format_map.get(ext, f"audio/{ext}")
    
    def is_audio_variable(self, var_value: str) -> bool:
        """
        Check if a variable value is an audio data URL.
        
        Args:
            var_value: Variable value to check
            
        Returns:
            True if value starts with 'data:audio/'
        """
        return var_value.startswith("data:audio/")
    
    def get_audio_format_from_variable(self, var_value: str) -> Optional[str]:
        """
        Extract audio format from a data URL variable.
        
        Args:
            var_value: Audio data URL
            
        Returns:
            Format string (e.g., 'mp3', 'wav') or None
        """
        if not self.is_audio_variable(var_value):
            return None
        
        # Format is between "data:audio/" and ";base64,"
        parts = var_value.split(";")
        if len(parts) >= 1:
            format_part = parts[0].replace("data:audio/", "")
            return format_part
        return None
    
    def get_audio_bytes_from_variable(self, var_value: str) -> Optional[bytes]:
        """
        Extract audio bytes from a data URL variable.
        
        Args:
            var_value: Audio data URL
            
        Returns:
            Audio bytes or None
        """
        if not self.is_audio_variable(var_value):
            return None
        
        # Extract base64 data
        data_start = var_value.find(",") + 1
        if data_start <= 0:
            return None
        
        base64_data = var_value[data_start:]
        try:
            return base64.b64decode(base64_data)
        except Exception:
            return None
