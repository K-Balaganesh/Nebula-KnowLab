"""Inventory skill: Stock queries, stock receiving, new SKU addition, and reorder checks."""

from typing import Any, Dict, List, Optional
from src.database.db import get_db_connection, transaction


def search_inventory(query: str = "") -> Dict[str, Any]:
    """
    Search products in store inventory by name or category.
    Returns matched products with current stock, unit, price, and GST rate.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    clean = query.strip().lower() if query else ""
    if not clean or clean in ("all", "all products", "all items", "everything", "stock", "inventory", "catalog", "items"):
        cursor.execute("SELECT * FROM products ORDER BY name ASC LIMIT 50;")
    else:
        pattern = f"%{query.strip()}%"
        cursor.execute(
            """
            SELECT * FROM products 
            WHERE name LIKE ? OR category LIKE ?
            ORDER BY name ASC;
            """,
            (pattern, pattern)
        )

    rows = cursor.fetchall()
    items = [dict(r) for r in rows]
    return {
        "status": "success",
        "count": len(items),
        "products": items
    }


def stock_in(
    item_name: str,
    quantity: float,
    cost_price: Optional[float] = None,
    selling_price: Optional[float] = None
) -> Dict[str, Any]:
    """
    Receive new stock for an existing product.
    Updates stock quantity atomically, and optionally updates cost or selling price.
    
    Args:
        item_name: Exact or matching product name (e.g. "Maggi 70g")
        quantity: Amount of stock received (must be positive)
        cost_price: Optional new purchase cost (₹)
        selling_price: Optional new retail selling price (₹)
    """
    if quantity <= 0:
        return {"status": "error", "message": "Received quantity must be greater than zero."}

    conn = get_db_connection()
    with transaction(conn):
        cursor = conn.cursor()
        # Find product
        cursor.execute(
            "SELECT * FROM products WHERE name LIKE ? ORDER BY LENGTH(name) ASC LIMIT 1;",
            (f"%{item_name}%",)
        )
        product = cursor.fetchone()
        if not product:
            return {
                "status": "error",
                "message": f"Product '{item_name}' not found in catalog. Add it as a new product first."
            }

        prod_id = product["id"]
        prod_name = product["name"]
        new_cost = cost_price if cost_price is not None else product["cost_price"]
        new_sell = selling_price if selling_price is not None else product["selling_price"]

        # Guardrail: Selling below cost warning / guard
        if new_sell < new_cost:
            return {
                "status": "error",
                "message": f"Guardrail Alert: Selling price (₹{new_sell}) cannot be lower than cost price (₹{new_cost})."
            }

        cursor.execute(
            """
            UPDATE products
            SET stock_quantity = stock_quantity + ?,
                cost_price = ?,
                selling_price = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?;
            """,
            (quantity, new_cost, new_sell, prod_id)
        )

        cursor.execute("SELECT stock_quantity, unit FROM products WHERE id = ?;", (prod_id,))
        updated = cursor.fetchone()

        return {
            "status": "success",
            "message": f"Stock received successfully for {prod_name}.",
            "product_name": prod_name,
            "quantity_added": quantity,
            "new_stock_quantity": updated["stock_quantity"],
            "unit": updated["unit"],
            "cost_price": new_cost,
            "selling_price": new_sell
        }


def add_product(
    name: str,
    category: str,
    unit: str,
    cost_price: float,
    selling_price: float,
    gst_rate: float,
    hsn_code: str = "0000",
    initial_stock: float = 0.0,
    is_loose: bool = False,
    reorder_level: float = 5.0
) -> Dict[str, Any]:
    """
    Add a brand new SKU to the store catalog.
    
    Args:
        name: Full product name (e.g. "Amul Butter 100g")
        category: Product category (e.g. "Dairy", "Staples")
        unit: Unit of measure (e.g. "packet", "kg", "litre")
        cost_price: Wholesale purchase price in ₹
        selling_price: Retail selling price / MRP in ₹
        gst_rate: Tax slab as decimal (0.0, 0.05, 0.12, 0.18, 0.28)
        hsn_code: Indian HSN tax code
        initial_stock: Starting inventory count
        is_loose: True for unpackaged bulk goods (sugar, dal by kg)
        reorder_level: Threshold to flag low-stock warning
    """
    # Guardrails
    if selling_price < cost_price:
        return {
            "status": "error",
            "message": f"Guardrail: Selling price (₹{selling_price}) cannot be less than cost price (₹{cost_price})."
        }
    if gst_rate not in (0.0, 0.05, 0.12, 0.18, 0.28):
        return {
            "status": "error",
            "message": f"Invalid GST rate {gst_rate}. Allowed slabs in India are 0%, 5%, 12%, 18%, 28%."
        }

    conn = get_db_connection()
    try:
        with transaction(conn):
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO products (
                    name, category, unit, is_loose, cost_price, selling_price,
                    stock_quantity, reorder_level, hsn_code, gst_rate
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    name.strip(),
                    category.strip(),
                    unit.strip(),
                    1 if is_loose else 0,
                    cost_price,
                    selling_price,
                    max(0.0, initial_stock),
                    reorder_level,
                    hsn_code.strip(),
                    gst_rate
                )
            )
            prod_id = cursor.lastrowid
            return {
                "status": "success",
                "message": f"Product '{name}' added successfully to inventory.",
                "product_id": prod_id,
                "name": name,
                "selling_price": selling_price,
                "gst_rate": gst_rate,
                "stock": initial_stock
            }
    except Exception as e:
        if "UNIQUE" in str(e):
            with transaction(conn):
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE products
                    SET selling_price = ?, cost_price = ?, gst_rate = ?, hsn_code = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE name LIKE ?;
                    """,
                    (selling_price, cost_price, gst_rate, hsn_code.strip(), name.strip())
                )
                cursor.execute("SELECT id, stock_quantity FROM products WHERE name LIKE ?;", (name.strip(),))
                row = cursor.fetchone()
                return {
                    "status": "success",
                    "message": f"Product '{name}' updated in catalog @ ₹{selling_price:.2f} (GST {int(gst_rate*100)}%).",
                    "product_id": row["id"] if row else None,
                    "name": name,
                    "selling_price": selling_price,
                    "gst_rate": gst_rate,
                    "stock": row["stock_quantity"] if row else initial_stock
                }
        return {"status": "error", "message": f"Failed to add product: {str(e)}"}


def check_low_stock() -> Dict[str, Any]:
    """
    Check all products that are at or below their reorder threshold.
    Returns list of items needing replenishment.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, name, category, unit, stock_quantity, reorder_level, selling_price
        FROM products
        WHERE stock_quantity <= reorder_level
        ORDER BY (stock_quantity / (reorder_level + 0.01)) ASC;
        """
    )
    rows = cursor.fetchall()
    items = [dict(r) for r in rows]
    return {
        "status": "success",
        "low_stock_count": len(items),
        "items": items
    }
