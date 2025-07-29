# Use official Python image with system dependencies
FROM python:3.10-slim

# Install system packages required for PaddleOCR and PDF/image processing
RUN apt-get update && apt-get install -y \
    build-essential \
    libglib2.0-0 \
    libsm6 \
    libxrender-dev \
    libxext6 \
    libgl1-mesa-glx \
    ttf-dejavu \
    wget \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port for FastAPI
EXPOSE 8000

# Set environment variables for production
ENV PYTHONUNBUFFERED=1

# Start FastAPI app with Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
