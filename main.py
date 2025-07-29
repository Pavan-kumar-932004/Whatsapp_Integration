import os
import re
import uuid
import requests
from fastapi import FastAPI, Form, UploadFile
from fastapi.responses import JSONResponse
from paddleocr import PaddleOCR
import psycopg2
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from dotenv import load_dotenv
from datetime import datetime
import logging

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

DATABASE_URL = os.getenv("DATABASE_URL")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# Initialize PaddleOCR engine
ocr_engine = PaddleOCR(use_angle_cls=True, lang='en')

def extract_invoice_data(text):
    """
    Intelligent invoice parser using regular expressions to extract:
    - Invoice ID/Number
    - Total Amount
    - Due Date
    
    Args:
        text (str): Raw text extracted from OCR
        
    Returns:
        tuple: (invoice_id, total_amount, due_date)
    """
    logger.info("Starting invoice data extraction from OCR text")
    
    # Initialize default values
    invoice_id = None
    total_amount = None
    due_date = None
    
    # Patterns for Invoice ID/Number (case-insensitive)
    invoice_patterns = [
        r'invoice\s*(?:no\.?|number|#)\s*:?\s*([A-Z0-9\-]+)',
        r'inv\s*(?:no\.?|#)\s*:?\s*([A-Z0-9\-]+)',
        r'bill\s*(?:no\.?|number|#)\s*:?\s*([A-Z0-9\-]+)',
        r'reference\s*(?:no\.?|number|#)\s*:?\s*([A-Z0-9\-]+)'
    ]
    
    # Search for invoice ID
    for pattern in invoice_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            invoice_id = match.group(1).strip()
            logger.info(f"Found invoice ID: {invoice_id}")
            break
    
    # Patterns for Total Amount (with various currency symbols and formatting)
    amount_patterns = [
        r'total\s*(?:amount)?\s*:?\s*[$£€₹]?\s*([0-9,]+\.?\d*)',
        r'amount\s*(?:due|total)?\s*:?\s*[$£€₹]?\s*([0-9,]+\.?\d*)',
        r'grand\s*total\s*:?\s*[$£€₹]?\s*([0-9,]+\.?\d*)',
        r'balance\s*(?:due)?\s*:?\s*[$£€₹]?\s*([0-9,]+\.?\d*)',
        r'[$£€₹]\s*([0-9,]+\.?\d*)\s*(?:total|due|balance)'
    ]
    
    # Search for total amount
    for pattern in amount_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Clean amount string (remove commas, convert to float)
            amount_str = match.group(1).replace(',', '')
            try:
                total_amount = float(amount_str)
                logger.info(f"Found total amount: {total_amount}")
                break
            except ValueError:
                continue
    
    # Patterns for Due Date (various formats)
    date_patterns = [
        r'due\s*(?:date|by)?\s*:?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})',
        r'payment\s*due\s*:?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})',
        r'payable\s*by\s*:?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})',
        r'due\s*on\s*:?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})'
    ]
    
    # Search for due date
    for pattern in date_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            date_str = match.group(1)
            # Try to parse different date formats
            for fmt in ['%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%m-%d-%Y', '%d.%m.%Y', '%m.%d.%Y']:
                try:
                    due_date = datetime.strptime(date_str, fmt).date()
                    logger.info(f"Found due date: {due_date}")
                    break
                except ValueError:
                    continue
            if due_date:
                break
    
    # Fallback values if extraction fails
    if not invoice_id:
        invoice_id = f"INV-{uuid.uuid4().hex[:8].upper()}"
        logger.warning(f"Invoice ID not found, generated: {invoice_id}")
    
    if total_amount is None:
        total_amount = 0.00
        logger.warning("Total amount not found, defaulted to 0.00")
    
    if not due_date:
        due_date = datetime.now().date()
        logger.warning(f"Due date not found, defaulted to today: {due_date}")
    
    return invoice_id, total_amount, due_date

def save_invoice(invoice_number, total_amount, due_date, sender_whatsapp):
    """
    Save invoice data to PostgreSQL database with comprehensive error handling.
    
    Args:
        invoice_number (str): Invoice ID/number
        total_amount (float): Total amount of the invoice
        due_date (date): Due date for payment
        sender_whatsapp (str): WhatsApp number of the sender
    
    Returns:
        bool: True if successful, False if failed
    """
    try:
        logger.info(f"Attempting to save invoice {invoice_number} to database")
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO invoices (invoice_number, total_amount, due_date, sender_whatsapp)
            VALUES (%s, %s, %s, %s)
        """, (invoice_number, total_amount, due_date, sender_whatsapp))
        
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"Successfully saved invoice {invoice_number} to database")
        return True
        
    except psycopg2.Error as e:
        logger.error(f"Database error while saving invoice {invoice_number}: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error while saving invoice {invoice_number}: {str(e)}")
        return False

def send_confirmation(to, invoice_number):
    """
    Send confirmation message via Twilio WhatsApp API with error handling.
    
    Args:
        to (str): Recipient's WhatsApp number
        invoice_number (str): Invoice ID for confirmation message
    
    Returns:
        bool: True if successful, False if failed
    """
    try:
        logger.info(f"Sending confirmation message for invoice {invoice_number} to {to}")
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        message = f"✅ Invoice {invoice_number} has been processed successfully and saved to our system."
        
        result = client.messages.create(
            body=message,
            from_=TWILIO_PHONE_NUMBER,
            to=to
        )
        
        logger.info(f"Confirmation message sent successfully. Message SID: {result.sid}")
        return True
        
    except TwilioRestException as e:
        logger.error(f"Twilio error while sending confirmation for invoice {invoice_number}: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error while sending confirmation for invoice {invoice_number}: {str(e)}")
        return False

@app.post("/api/whatsapp/webhook")
async def whatsapp_webhook(
    MediaUrl0: str = Form(None),
    From: str = Form(...)
):
    """
    WhatsApp webhook endpoint for processing invoice media with comprehensive error handling
    and concurrency safety through unique file naming.
    
    Args:
        MediaUrl0 (str): URL of the media file from Twilio
        From (str): Sender's WhatsApp number
    
    Returns:
        JSONResponse: Success or error response
    """
    logger.info(f"Received webhook from {From} with MediaUrl0: {MediaUrl0}")
    
    # Check if media is provided
    if not MediaUrl0:
        logger.warning(f"No media URL provided in webhook from {From}")
        return JSONResponse({"error": "No media found in the message."}, status_code=400)
    
    # Generate unique filename to prevent race conditions
    unique_filename = f"/tmp/invoice_{uuid.uuid4().hex}.file"
    
    try:
        # Download media file with error handling
        logger.info(f"Downloading media from: {MediaUrl0}")
        
        # Ensure Twilio credentials are available for authentication
        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
            logger.error("Twilio credentials not found in environment variables")
            return JSONResponse(
                {"error": "Server configuration error. Please contact support."}, 
                status_code=500
            )
        
        response = requests.get(
            MediaUrl0,
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            timeout=30
        )
        response.raise_for_status()  # Raises an HTTPError for bad responses
        
        # Save the downloaded file
        with open(unique_filename, "wb") as f:
            f.write(response.content)
        
        logger.info(f"Media file saved as: {unique_filename}")
        
        # Perform OCR with error handling
        logger.info("Starting OCR processing")
        result = ocr_engine.ocr(unique_filename)
        
        if not result or not result[0]:
            logger.error("OCR failed to extract any text from the image")
            return JSONResponse(
                {"error": "Could not extract text from the image. Please ensure the image is clear and contains readable text."}, 
                status_code=400
            )
        
        # Extract text from OCR results
        text = " ".join([line[1][0] for line in result[0] if line[1][0]])
        logger.info(f"OCR extracted text: {text[:100]}...")  # Log first 100 chars
        
        # Parse invoice data using intelligent parser
        invoice_id, total_amount, due_date = extract_invoice_data(text)
        
        # Save to database
        db_success = save_invoice(invoice_id, total_amount, due_date, From)
        if not db_success:
            logger.error(f"Failed to save invoice {invoice_id} to database")
            return JSONResponse(
                {"error": "Failed to save invoice data to database. Please try again later."}, 
                status_code=500
            )
        
        # Send confirmation message
        confirmation_success = send_confirmation(From, invoice_id)
        if not confirmation_success:
            logger.warning(f"Invoice {invoice_id} saved but confirmation message failed to send")
            # Don't return error here as the main operation (saving invoice) succeeded
        
        logger.info(f"Successfully processed invoice {invoice_id} from {From}")
        return JSONResponse({
            "status": "success", 
            "invoice_id": invoice_id,
            "total_amount": total_amount,
            "due_date": str(due_date),
            "message": "Invoice processed successfully"
        })
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download media from {MediaUrl0}: {str(e)}")
        return JSONResponse(
            {"error": "Failed to download the media file. Please check the file and try again."}, 
            status_code=400
        )
    except Exception as e:
        logger.error(f"Unexpected error processing webhook from {From}: {str(e)}")
        return JSONResponse(
            {"error": "An unexpected error occurred while processing your invoice. Please try again later."}, 
            status_code=500
        )
    finally:
        # Always clean up the temporary file to prevent storage issues
        try:
            if os.path.exists(unique_filename):
                os.remove(unique_filename)
                logger.info(f"Cleaned up temporary file: {unique_filename}")
        except Exception as e:
            logger.warning(f"Failed to clean up temporary file {unique_filename}: {str(e)}")
