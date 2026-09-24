-- Supermarket Operations Database Schema
-- Designed for SQLite with WAL mode & strict integrity constraints

PRAGMA foreign_keys = ON;

-- 1. Store Preferences (Persistent memory that survives /new chat and reboots)
CREATE TABLE IF NOT EXISTS store_preferences (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Products / Inventory Catalog
-- Note the CHECK constraint on stock_quantity: impossible to go negative at the database layer.
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT COLLATE NOCASE UNIQUE NOT NULL,
    category TEXT NOT NULL,
    unit TEXT NOT NULL,                         -- 'kg', 'g', 'litre', 'ml', 'packet', 'dozen', 'piece'
    is_loose BOOLEAN NOT NULL DEFAULT 0,        -- 1 for loose items (sugar, dal, rice), 0 for packaged
    cost_price REAL NOT NULL CHECK(cost_price >= 0),
    selling_price REAL NOT NULL CHECK(selling_price >= 0),
    stock_quantity REAL NOT NULL DEFAULT 0 CHECK(stock_quantity >= 0), -- Oversell Guard
    reorder_level REAL NOT NULL DEFAULT 5 CHECK(reorder_level >= 0),
    hsn_code TEXT NOT NULL,
    gst_rate REAL NOT NULL CHECK(gst_rate >= 0 AND gst_rate <= 0.28), -- 0.0, 0.05, 0.12, 0.18, 0.28
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);

-- 3. Customers & Khata (Credit Ledger)
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT COLLATE NOCASE UNIQUE NOT NULL,
    phone TEXT,
    balance REAL NOT NULL DEFAULT 0.0,          -- Positive balance = customer owes money to the store
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(name);

CREATE TABLE IF NOT EXISTS khata_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
    transaction_type TEXT NOT NULL CHECK(transaction_type IN ('DEBIT', 'CREDIT')), -- DEBIT: added to debt, CREDIT: repayment
    amount REAL NOT NULL CHECK(amount > 0),
    balance_after REAL NOT NULL,
    bill_id INTEGER REFERENCES bills(id) ON DELETE SET NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_khata_customer ON khata_transactions(customer_id);

-- 4. Draft Bills (Multi-turn bill staging area per chat session)
CREATE TABLE IF NOT EXISTS draft_bills (
    session_id TEXT PRIMARY KEY,               -- Telegram chat_id or CLI session
    items_json TEXT NOT NULL DEFAULT '[]',     -- JSON array of cart items
    customer_name TEXT,
    payment_mode TEXT DEFAULT 'UPI',
    notes TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. Finalized Bills (Sales records)
CREATE TABLE IF NOT EXISTS bills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_number TEXT UNIQUE NOT NULL,
    customer_id INTEGER REFERENCES customers(id) ON DELETE SET NULL,
    customer_name TEXT,
    payment_mode TEXT NOT NULL CHECK(payment_mode IN ('CASH', 'UPI', 'CARD', 'KHATA')),
    total_taxable_amount REAL NOT NULL,
    total_cgst REAL NOT NULL,
    total_sgst REAL NOT NULL,
    grand_total REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bills_number ON bills(bill_number);
CREATE INDEX IF NOT EXISTS idx_bills_created_at ON bills(created_at);

-- 6. Bill Line Items
CREATE TABLE IF NOT EXISTS bill_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id INTEGER NOT NULL REFERENCES bills(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    product_name TEXT NOT NULL,
    quantity REAL NOT NULL CHECK(quantity > 0),
    unit TEXT NOT NULL,
    unit_price REAL NOT NULL,
    cost_price REAL NOT NULL,
    taxable_amount REAL NOT NULL,
    hsn_code TEXT NOT NULL,
    gst_rate REAL NOT NULL,
    cgst_amount REAL NOT NULL,
    sgst_amount REAL NOT NULL,
    total_amount REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bill_items_bill ON bill_items(bill_id);
CREATE INDEX IF NOT EXISTS idx_bill_items_product ON bill_items(product_id);

-- 7. Idempotency Tracking (Prevents duplicate processing of Telegram updates)
CREATE TABLE IF NOT EXISTS processed_updates (
    update_id TEXT PRIMARY KEY,
    action_type TEXT,
    response_summary TEXT,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
