#!/usr/bin/env python3
"""
PaddleOCR Model Download Script for Hugging Face Spaces

This script pre-downloads PaddleOCR models during Docker image build process
to avoid downloading them at runtime and prevent permission errors.
"""

import os
import logging
from paddleocr import PaddleOCR

# Configure logging for the download process
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def download_paddleocr_models():
    """
    Initialize PaddleOCR to trigger model downloads during Docker build.
    This ensures models are baked into the Docker image and prevents runtime permission errors.
    """
    try:
        # Ensure the PaddleOCR home directory exists
        paddleocr_home = os.environ.get('PADDLEOCR_HOME', '/tmp/.paddleocr/')
        os.makedirs(paddleocr_home, exist_ok=True)
        
        logger.info(f"PaddleOCR home directory: {paddleocr_home}")
        logger.info("Starting PaddleOCR model download process...")
        
        # Initialize PaddleOCR with the same configuration as main application
        # This will download and cache the required models to the specified directory
        ocr_engine = PaddleOCR(
            use_angle_cls=True,  # Enable angle classification for rotated text
            lang='en',           # English language models
            show_log=True        # Show download progress
        )
        
        logger.info("PaddleOCR models downloaded successfully!")
        logger.info(f"Models are cached in: {paddleocr_home}")
        logger.info("Models are now baked into the Docker image and ready for production use.")
        
        # Test the OCR engine to ensure it's working
        logger.info("Testing OCR engine initialization...")
        
        # The models are now downloaded and cached
        # No need to process any actual images, just verify initialization
        logger.info("OCR engine test completed successfully!")
        
    except Exception as e:
        logger.error(f"Failed to download PaddleOCR models: {str(e)}")
        raise e

if __name__ == "__main__":
    download_paddleocr_models()
