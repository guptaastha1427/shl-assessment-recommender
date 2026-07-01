"""Configuration and environment variables."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CATALOG_PATH = DATA_DIR / "shl_catalog.json"

# LLM
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# Embeddings
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# Search
TOP_K_RETRIEVAL = int(os.getenv("TOP_K_RETRIEVAL", "20"))
MAX_RECOMMENDATIONS = int(os.getenv("MAX_RECOMMENDATIONS", "10"))
MIN_RECOMMENDATIONS = int(os.getenv("MIN_RECOMMENDATIONS", "1"))

# Agent behavior
MAX_TURNS = int(os.getenv("MAX_TURNS", "8"))
RESPONSE_TIMEOUT = int(os.getenv("RESPONSE_TIMEOUT", "25"))  # seconds, leave buffer from 30s cap
