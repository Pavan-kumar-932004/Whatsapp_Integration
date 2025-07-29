CREATE TABLE invoices (
    id SERIAL PRIMARY KEY,
    invoice_number VARCHAR(255),
    total_amount NUMERIC(10, 2),
    due_date DATE,
    sender_whatsapp VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'processed',
    received_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
