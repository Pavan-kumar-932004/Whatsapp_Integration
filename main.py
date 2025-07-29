import os
import requests
from fastapi import FastAPI, Form, UploadFile
from fastapi.responses import JSONResponse
from paddleocr import PaddleOCR
import psycopg2
from twilio.rest import Client
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

app = FastAPI()

DATABASE_URL = os.getenv("DATABASE_URL")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

ocr_engine = PaddleOCR(use_angle_cls=True, lang='en')

def extract_invoice_data(text):
    # Dummy parser, replace with actual parsing logic
    invoice_id = "12345"
    total_amount = 100.00
    due_date = datetime.now().date()
    return invoice_id, total_amount, due_date

def save_invoice(invoice_number, total_amount, due_date, sender_whatsapp):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO invoices (invoice_number, total_amount, due_date, sender_whatsapp)
        VALUES (%s, %s, %s, %s)
    """, (invoice_number, total_amount, due_date, sender_whatsapp))
    conn.commit()
    cur.close()
    conn.close()

def send_confirmation(to, invoice_number):
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    message = f"Invoice {invoice_number} processed successfully."
    client.messages.create(
        body=message,
        from_=TWILIO_PHONE_NUMBER,
        to=to
    )

@app.post("/api/whatsapp/webhook")
async def whatsapp_webhook(
    MediaUrl0: str = Form(None),
    From: str = Form(...)
):
    if not MediaUrl0:
        return JSONResponse({"error": "No media found."}, status_code=400)
    # Download media
    response = requests.get(MediaUrl0)
    file_path = "/tmp/invoice_file"
    with open(file_path, "wb") as f:
        f.write(response.content)
    # OCR
    result = ocr_engine.ocr(file_path)
    text = " ".join([line[1][0] for line in result[0]])
    invoice_id, total_amount, due_date = extract_invoice_data(text)
    save_invoice(invoice_id, total_amount, due_date, From)
    send_confirmation(From, invoice_id)
    return {"status": "success", "invoice_id": invoice_id}
