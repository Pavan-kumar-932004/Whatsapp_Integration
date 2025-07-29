# Use official Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system packages required for PaddleOCR and PDF/image processing
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

# Copy only the requirements file first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose port for FastAPI
EXPOSE 8000

# Set environment variables for production
ENV PYTHONUNBUFFERED=1

# Start FastAPI app with Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]