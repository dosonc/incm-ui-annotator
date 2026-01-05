# Use Python 3.11 slim image for AMD64 architecture
FROM --platform=linux/amd64 python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies required for PyMuPDF and image processing
RUN apt-get update && apt-get install -y \
    libmupdf-dev \
    libfreetype6-dev \
    libjpeg-dev \
    zlib1g-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY config.py .
COPY parser.py .
COPY parser_dots.py .
COPY database.py .
COPY api_utils.py .
COPY text_utils.py .
COPY document_utils.py .
COPY image_utils.py .

# Copy public directory (logos)
COPY public/ ./public/

# Copy parsed documents directory
COPY parsed_docs/ ./parsed_docs/

# Copy database file (if it doesn't exist, the app will create it on first run via init_db())
COPY annotations.db* ./

# Expose Streamlit port
EXPOSE 8501

# Set environment variables (must be set in Azure Container Apps configuration)
# These are set here as placeholders but should be overridden at runtime
ENV AUTH_USERNAME=""
ENV AUTH_PASSWORD=""
ENV OPENROUTER_API_KEY=""
ENV OPENROUTER_MODEL=""
ENV OPENROUTER_VISION_MODEL=""

# Health check (using curl as it's more reliable)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Run Streamlit app
# Azure Container Apps will set environment variables at runtime
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]

