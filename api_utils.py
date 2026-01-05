"""
API utility functions for OpenRouter and LLM interactions.
"""
import os
import io
import base64
import streamlit as st
from openai import OpenAI
from PIL import Image
import config


def get_openrouter_client():
    """Get OpenRouter API client."""
    api_key = config.OPENROUTER_API_KEY
    if not api_key:
        st.error("OpenRouter API key not found. Please set OPENROUTER_API_KEY in .env file, environment variable, or Streamlit secrets.")
        return None
    
    return OpenAI(
        base_url=config.OPENROUTER_BASE_URL,
        api_key=api_key,
    )


def encode_image_to_base64(image):
    """Convert PIL Image to base64 encoded string for API transmission."""
    buffered = io.BytesIO()
    # Convert RGBA to RGB if necessary (JPEG doesn't support transparency)
    if image.mode in ('RGBA', 'LA', 'P'):
        # Create a white background
        rgb_image = Image.new('RGB', image.size, (255, 255, 255))
        if image.mode == 'P':
            image = image.convert('RGBA')
        rgb_image.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
        image = rgb_image
    elif image.mode != 'RGB':
        image = image.convert('RGB')
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

