"""
Configuration for Medral AI Healthcare Platform
"""
import os
from pathlib import Path


BASE_DIR = Path(__file__).parent.parent
UPLOADS_DIR = BASE_DIR / "uploads"
TEMP_DIR = "/tmp/medral"


os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)


MODELS_CONFIG = {
    "qwen3_vl": {
        "type": "ollama",
        "model_name": "qwen3-vl:4b",
        "base_url": "http://localhost:11434",
        "enabled": True
    },
    "medgemma": {
        "type": "huggingface",
        "model_name": "google/medgemma-1.5-4b-it",
        "device_map": "auto",
        "torch_dtype": "bfloat16",
        "enabled": True
    }
}


SERVER_CONFIG = {
    "host": "0.0.0.0",
    "port": 8000,
    "debug": True
}


UPLOAD_CONFIG = {
    "max_file_size_mb": 50, 
    "allowed_extensions": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"],
    "max_files_per_request": 10
}


SESSION_CONFIG = {
    "session_timeout_minutes": 30,
    "max_sessions": 100
}


MODEL_LOADING = {
    "load_at_startup": True,  # Load both models when server starts
    "enable_caching": True,
    "cache_dir": str(BASE_DIR / "cache")
}


LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
    "ta": "Tamil",
    "te": "Telugu",
    "ml": "Malayalam",
    "kn": "Kannada",

}
