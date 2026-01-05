"""
Configuration file for the OCR annotation tool.
All configuration values are centralized here for easy management.
"""
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
DEFAULT_VISION_MODEL = os.getenv("OPENROUTER_VISION_MODEL")

AUTH_USERNAME = os.getenv("AUTH_USERNAME", "admin")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD")

# LLM API settings
LLM_TEMPERATURE = 1

# Text replacement rules dictionary
RULES_DICT = {
    "governo": "govêrno",
    "Governo": "Govêrno",
    "GOVERNO": "GOVÊRNO",
    "selo": "sêlo",
    "Selo": "Sêlo",
    "nele": "nêle",
    "Nele": "Nêle",
    "esse": "êsse",
    "esses": "êsses",
    "Esse": "Êsse",
    "Esses": "Êsses",
}

# Image transcription prompt
PROMPT_IMAGE = """ 
Transcribe the text highlighted in light blue from the provided image exactly as it appears in Portuguese. 
Maintain all original punctuation, special symbols (such as '$', ':', '§'), and archaic spellings. 
Output only the transcribed text without any additional comments or explanations.
"""

# Directory containing parsed documents
PARSED_DOCS_DIR = Path("parsed_docs")

# Streamlit page configuration
PAGE_TITLE = "Ferramenta de Anotação OCR"
PAGE_LAYOUT = "wide"

# Sidebar logo width
SIDEBAR_LOGO_WIDTH = 150

# Month names in Portuguese
MONTH_NAMES = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro"
}

# Error types
ERROR_TYPES = ["minor", "major"]
ERROR_TYPE_LABELS = {
    "minor": "Menor",
    "major": "Maior"
}

# DPI settings for PDF rendering
TARGET_DPI = 144
DEFAULT_DPI = 72  # PyMuPDF default

# Image offset settings
OFFSET_X = 0
OFFSET_Y = 0

# Image cropping padding
CROP_PADDING = 20

# Bounding box overlay color (RGBA)
# Light blue with transparency: (173, 216, 230, 100) - light blue with ~40% opacity
BBOX_OVERLAY_COLOR = (173, 216, 230, 100)
