from src.config import (
    STORE_ADDRESS,
    STORE_GSTIN,
    STORE_NAME,
    STORE_STATE,
    STORE_STATE_CODE,
)
from src.database.db import get_db_connection, init_db, transaction


def seed_database(reset: bool = False) -> None:
    """Populate database with initial store catalog, preferences, and customers."""
    init_db()
    conn = get_db_connection()

    with transaction(conn):
        if reset:
            conn.execute("DELETE FROM bill_items;")
            conn.execute("DELETE FROM bills;")
            conn.execute("DELETE FROM khata_transactions;")
            conn.execute("DELETE FROM customers;")
            conn.execute("DELETE FROM draft_bills;")
            conn.execute("DELETE FROM products;")
            conn.execute("DELETE FROM store_preferences;")
            conn.execute("DELETE FROM processed_updates;")

        # 1. Default Store Preferences
        default_prefs = [
            ("store_name", STORE_NAME),
            ("store_gstin", STORE_GSTIN),
            ("store_address", STORE_ADDRESS),
            ("store_state", STORE_STATE),
            ("store_state_code", STORE_STATE_CODE),
            ("default_payment_mode", "UPI"),
            ("default_atta", "Aashirvaad Atta 5kg"),
        ]
        for key, val in default_prefs:
            conn.execute(
                """
                INSERT INTO store_preferences (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO NOTHING;
                """,
                (key, val)
            )

        # 2. Indian Grocery Product Catalog
        # Note: Loose staples have 0% GST (HSN 1006, 1701, 0713)
        # Packaged staples: 5% (HSN 1101, 2501, 1512)
        # FMCG packaged foods/soaps: 12% - 18% (HSN 0405, 1902, 1905, 3402)
        initial_products = [
            # Loose Items
            {
                "name": "Sugar (loose)",
                "category": "Staples",
                "unit": "kg",
                "is_loose": 1,
                "cost_price": 38.0,
                "selling_price": 44.0,
                "stock_quantity": 80.0,
                "reorder_level": 20.0,
                "hsn_code": "1701",
                "gst_rate": 0.00
            },
            {
                "name": "Basmati Rice (loose)",
                "category": "Staples",
                "unit": "kg",
                "is_loose": 1,
                "cost_price": 80.0,
                "selling_price": 95.0,
                "stock_quantity": 60.0,
                "reorder_level": 15.0,
                "hsn_code": "1006",
                "gst_rate": 0.00
            },
            {
                "name": "Toor Dal (loose)",
                "category": "Pulses",
                "unit": "kg",
                "is_loose": 1,
                "cost_price": 140.0,
                "selling_price": 165.0,
                "stock_quantity": 40.0,
                "reorder_level": 10.0,
                "hsn_code": "0713",
                "gst_rate": 0.00
            },
            # Packaged Items
            {
                "name": "Aashirvaad Atta 5kg",
                "category": "Flour",
                "unit": "packet",
                "is_loose": 0,
                "cost_price": 240.0,
                "selling_price": 275.0,
                "stock_quantity": 25.0,
                "reorder_level": 5.0,
                "hsn_code": "1101",
                "gst_rate": 0.05
            },
            {
                "name": "Tata Salt 1kg",
                "category": "Staples",
                "unit": "packet",
                "is_loose": 0,
                "cost_price": 22.0,
                "selling_price": 28.0,
                "stock_quantity": 50.0,
                "reorder_level": 10.0,
                "hsn_code": "2501",
                "gst_rate": 0.05
            },
            {
                "name": "Fortune Sunflower Oil 1L",
                "category": "Edible Oil",
                "unit": "packet",
                "is_loose": 0,
                "cost_price": 125.0,
                "selling_price": 145.0,
                "stock_quantity": 30.0,
                "reorder_level": 8.0,
                "hsn_code": "1512",
                "gst_rate": 0.05
            },
            {
                "name": "Amul Butter 100g",
                "category": "Dairy",
                "unit": "packet",
                "is_loose": 0,
                "cost_price": 50.0,
                "selling_price": 60.0,
                "stock_quantity": 20.0,
                "reorder_level": 5.0,
                "hsn_code": "0405",
                "gst_rate": 0.12
            },
            {
                "name": "Maggi 70g",
                "category": "Instant Noodles",
                "unit": "packet",
                "is_loose": 0,
                "cost_price": 12.0,
                "selling_price": 14.0,
                "stock_quantity": 100.0,
                "reorder_level": 25.0,
                "hsn_code": "1902",
                "gst_rate": 0.12
            },
            {
                "name": "Parle-G 250g",
                "category": "Biscuits",
                "unit": "packet",
                "is_loose": 0,
                "cost_price": 20.0,
                "selling_price": 25.0,
                "stock_quantity": 40.0,
                "reorder_level": 10.0,
                "hsn_code": "1905",
                "gst_rate": 0.18
            },
            {
                "name": "Surf Excel 1kg",
                "category": "Detergents",
                "unit": "packet",
                "is_loose": 0,
                "cost_price": 115.0,
                "selling_price": 140.0,
                "stock_quantity": 18.0,
                "reorder_level": 5.0,
                "hsn_code": "3402",
                "gst_rate": 0.18
            }
        ]

        for p in initial_products:
            conn.execute(
                """
                INSERT INTO products (
                    name, category, unit, is_loose, cost_price, selling_price,
                    stock_quantity, reorder_level, hsn_code, gst_rate
                ) VALUES (
                    :name, :category, :unit, :is_loose, :cost_price, :selling_price,
                    :stock_quantity, :reorder_level, :hsn_code, :gst_rate
                )
                ON CONFLICT(name) DO UPDATE SET
                    cost_price=excluded.cost_price,
                    selling_price=excluded.selling_price,
                    hsn_code=excluded.hsn_code,
                    gst_rate=excluded.gst_rate;
                """,
                p
            )

        # 3. Seed Initial Khata Customers
        customers = [
            ("Ramesh", "+91 98450 11223", 0.0),
            ("Priya", "+91 98450 44556", 0.0),
            ("Suresh", "+91 98450 77889", 0.0),
        ]
        for name, phone, bal in customers:
            conn.execute(
                """
                INSERT INTO customers (name, phone, balance)
                VALUES (?, ?, ?)
                ON CONFLICT(name) DO NOTHING;
                """,
                (name, phone, bal)
            )


if __name__ == "__main__":
    seed_database(reset=True)
    print("Database successfully initialized and seeded with Indian grocery catalog.")
