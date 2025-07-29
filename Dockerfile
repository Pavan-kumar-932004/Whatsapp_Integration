# Use official Python image
FROM python:3.10-slim

# Set environment variables at the top
ENV PYTHONUNBUFFERED=1
ENV PADDLEOCR_HOME=/tmp/.paddleocr/

# Set working directory
WORKDIR /app

# Install system packages...
RUN apt-get update && apt-get install -y \
    build-essential \
    libglib2.0-0 \
    libsm6 \
    libxrender-dev \
    libxext6 \
    libgl1-mesa-glx \
    fonts-dejavu-core \
    wget \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file first...
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy model download script and pre-download PaddleOCR models
COPY download_models.py .
RUN python download_models.py

# Clean up the download script to keep image tidy
RUN rm download_models.py

# Copy the rest of the application code
COPY . .

# Expose port 7860 for Hugging Face Spaces
EXPOSE 7860

# Set environment variables for production
ENV PYTHONUNBUFFERED=1

# --- NEW: Set a writable directory for PaddleOCR models ---
ENV PADDLEOCR_HOME=/tmp/.paddleocr/

# Start FastAPI app with Uvicorn on port 7860
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]