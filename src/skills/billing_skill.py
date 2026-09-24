"""Billing skill: Multi-turn cart builder, mid-bill editing, oversell guard, and atomic finalization."""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.database.db import get_db_connection, transaction
from src.generators.invoice_pdf import generate_gst_invoice_pdf
from src.utils.gst import summarize_cart_gst


def _get_draft_cart(conn, session_id: str) -> Dict[str, Any]:
    """Retrieve raw draft bill for session."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM draft_bills WHERE session_id = ?;", (session_id,))
    row = cursor.fetchone()
    if not row:
        return {
            "session_id": session_id,
            "items": [],
            "customer_name": None,
            "payment_mode": "UPI",
            "notes": None
        }
    return {
        "session_id": row["session_id"],
        "items": json.loads(row["items_json"]),
        "customer_name": row["customer_name"],
        "payment_mode": row["payment_mode"] or "UPI",
        "notes": row["notes"]
    }


def _save_draft_cart(conn, session_id: str, cart: Dict[str, Any]) -> None:
    """Save raw draft bill to database."""
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO draft_bills (session_id, items_json, customer_name, payment_mode, notes, updated_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(session_id) DO UPDATE SET
            items_json=excluded.items_json,
            customer_name=excluded.customer_name,
            payment_mode=excluded.payment_mode,
            notes=excluded.notes,
            updated_at=CURRENT_TIMESTAMP;
        """,
        (
            session_id,
            json.dumps(cart.get("items", [])),
            cart.get("customer_name"),
            cart.get("payment_mode", "UPI"),
            cart.get("notes")
        )
    )


def add_or_update_cart(
    session_id: str,
    items: List[Dict[str, Any]],
    customer_name: Optional[str] = None,
    payment_mode: Optional[str] = None
) -> Dict[str, Any]:
    """
    Add items to the active draft cart or create a new draft bill.
    Validates stock availability (Oversell Guard at the tool layer).
    Does NOT decrement inventory yet; inventory is only decremented on finalize_bill.
    
    Args:
        session_id: Chat session ID
        items: List of dicts, each with:
               'item_name' (e.g. 'sugar', 'Maggi 70g') and 'quantity' (e.g. 2, 4)
        customer_name: Optional customer name for khata or invoice
        payment_mode: Optional payment mode ('CASH', 'UPI', 'CARD', 'KHATA')
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cart = _get_draft_cart(conn, session_id)
    current_items = {item["product_id"]: item for item in cart["items"]}

    validation_errors = []
    added_or_modified = []

    for item_req in items:
        raw_name = str(item_req.get("item_name", "")).strip()
        req_qty = float(item_req.get("quantity", 1))

        if req_qty <= 0:
            validation_errors.append(f"Quantity for '{raw_name}' must be greater than zero.")
            continue

        # Look up product in DB (Grounding)
        cursor.execute(
            """
            SELECT * FROM products 
            WHERE name LIKE ? 
            ORDER BY CASE WHEN LOWER(name) = LOWER(?) THEN 0 ELSE 1 END, LENGTH(name) ASC 
            LIMIT 1;
            """,
            (f"%{raw_name}%", raw_name)
        )
        product = cursor.fetchone()
        if not product:
            validation_errors.append(f"Product '{raw_name}' was not found in inventory catalog.")
            continue

        prod_id = product["id"]
        prod_name = product["name"]
        available_stock = product["stock_quantity"]

        # Calculate new total quantity requested for this product in the cart
        existing_qty = current_items.get(prod_id, {}).get("quantity", 0)
        total_requested = existing_qty + req_qty

        # CRITICAL HARD PART 2: Oversell Guard at tool layer
        if total_requested > available_stock:
            validation_errors.append(
                f"Oversell Guard: Cannot bill {total_requested} {product['unit']} of '{prod_name}'. "
                f"Only {available_stock} {product['unit']} in stock."
            )
            continue

        # Update cart entry
        current_items[prod_id] = {
            "product_id": prod_id,
            "product_name": prod_name,
            "unit": product["unit"],
            "unit_price": product["selling_price"],
            "cost_price": product["cost_price"],
            "gst_rate": product["gst_rate"],
            "hsn_code": product["hsn_code"],
            "quantity": total_requested
        }
        added_or_modified.append(f"{prod_name} (x{total_requested})")

    if validation_errors and not current_items:
        return {
            "status": "error",
            "errors": validation_errors,
            "message": "Failed to add items to cart due to stock or lookup errors."
        }

    cart["items"] = list(current_items.values())
    if customer_name:
        cart["customer_name"] = customer_name
    if payment_mode:
        cart["payment_mode"] = payment_mode.upper()

    _save_draft_cart(conn, session_id, cart)

    # Compute live tax breakdown
    summary = summarize_cart_gst(cart["items"])
    summary["session_id"] = session_id
    summary["customer_name"] = cart["customer_name"]
    summary["payment_mode"] = cart["payment_mode"]
    summary["status"] = "success"
    if validation_errors:
        summary["warnings"] = validation_errors

    return summary


def edit_draft_cart(
    session_id: str,
    remove_items: Optional[List[str]] = None,
    set_quantities: Optional[Dict[str, float]] = None,
    payment_mode: Optional[str] = None
) -> Dict[str, Any]:
    """
    Edit an existing draft bill mid-build.
    Handles 'drop the butter', 'make it 6 Maggi', or payment mode change.
    
    Args:
        session_id: Current chat session
        remove_items: List of item names to remove completely (e.g. ['butter', 'sugar'])
        set_quantities: Dict of item name -> exact new quantity (e.g. {'Maggi': 6.0})
        payment_mode: Update payment mode (e.g. 'CASH', 'UPI')
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cart = _get_draft_cart(conn, session_id)

    if not cart["items"]:
        return {"status": "error", "message": "No active draft bill found to edit."}

    # 1. Handle complete removal
    if remove_items:
        for rem in remove_items:
            rem_clean = rem.strip().lower()
            cart["items"] = [
                itm for itm in cart["items"]
                if rem_clean not in itm["product_name"].lower()
            ]

    # 2. Handle quantity override
    if set_quantities:
        for raw_name, new_qty in set_quantities.items():
            if new_qty <= 0:
                # Treat zero or negative quantity as removal
                cart["items"] = [
                    itm for itm in cart["items"]
                    if raw_name.strip().lower() not in itm["product_name"].lower()
                ]
                continue

            # Find matching item in cart
            matched = False
            for itm in cart["items"]:
                if raw_name.strip().lower() in itm["product_name"].lower():
                    # Validate against stock
                    cursor.execute("SELECT stock_quantity, unit FROM products WHERE id = ?;", (itm["product_id"],))
                    prod = cursor.fetchone()
                    if prod and new_qty > prod["stock_quantity"]:
                        return {
                            "status": "error",
                            "message": (
                                f"Oversell Guard: Cannot set '{itm['product_name']}' to {new_qty}. "
                                f"Only {prod['stock_quantity']} {prod['unit']} available in stock."
                            )
                        }
                    itm["quantity"] = new_qty
                    matched = True
                    break

            if not matched:
                # Item wasn't in cart, search catalog and add if available
                cursor.execute(
                    "SELECT * FROM products WHERE name LIKE ? LIMIT 1;",
                    (f"%{raw_name.strip()}%",)
                )
                prod = cursor.fetchone()
                if prod:
                    if new_qty > prod["stock_quantity"]:
                        return {
                            "status": "error",
                            "message": (
                                f"Oversell Guard: Cannot add {new_qty} of '{prod['name']}'. "
                                f"Only {prod['stock_quantity']} available."
                            )
                        }
                    cart["items"].append({
                        "product_id": prod["id"],
                        "product_name": prod["name"],
                        "unit": prod["unit"],
                        "unit_price": prod["selling_price"],
                        "cost_price": prod["cost_price"],
                        "gst_rate": prod["gst_rate"],
                        "hsn_code": prod["hsn_code"],
                        "quantity": new_qty
                    })

    if payment_mode:
        cart["payment_mode"] = payment_mode.upper()

    _save_draft_cart(conn, session_id, cart)

    summary = summarize_cart_gst(cart["items"])
    summary["session_id"] = session_id
    summary["customer_name"] = cart["customer_name"]
    summary["payment_mode"] = cart["payment_mode"]
    summary["status"] = "success"
    summary["message"] = "Draft bill updated successfully."
    return summary


def get_active_bill(session_id: str) -> Dict[str, Any]:
    """Retrieve the current active draft bill summary for a session."""
    conn = get_db_connection()
    cart = _get_draft_cart(conn, session_id)
    if not cart["items"]:
        return {"status": "empty", "message": "No active bill in progress."}

    summary = summarize_cart_gst(cart["items"])
    summary["session_id"] = session_id
    summary["customer_name"] = cart["customer_name"]
    summary["payment_mode"] = cart["payment_mode"]
    summary["status"] = "success"
    return summary


def clear_active_bill(session_id: str) -> Dict[str, Any]:
    """Discard the current active draft bill without modifying stock."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM draft_bills WHERE session_id = ?;", (session_id,))
    return {"status": "success", "message": "Draft bill cleared."}


def finalize_bill(
    session_id: str,
    payment_mode: Optional[str] = None,
    customer_name: Optional[str] = None,
    generate_pdf: bool = True
) -> Dict[str, Any]:
    """
    Finalize the current draft bill.
    ATOMIC TRANSACTION:
      1. Verifies stock for all items
      2. Decrements inventory atomically (CHECK stock_quantity >= 0 enforced)
      3. Records bill and line items in bills and bill_items tables
      4. If payment_mode is KHATA, registers debit transaction on customer ledger
      5. Clears draft bill
      6. Generates GST Tax Invoice PDF artifact
    """
    conn = get_db_connection()
    cart = _get_draft_cart(conn, session_id)

    if not cart["items"]:
        return {"status": "error", "message": "Cannot finalize: cart is empty."}

    final_payment_mode = (payment_mode or cart.get("payment_mode") or "UPI").upper()
    final_customer_name = customer_name or cart.get("customer_name")

    if final_payment_mode == "KHATA" and not final_customer_name:
        return {
            "status": "error",
            "message": "Customer name is required when payment mode is Khata (Credit ledger)."
        }

    # Atomic ACID execution with BEGIN IMMEDIATE
    try:
        with transaction(conn):
            cursor = conn.cursor()

            # 1. Verify and decrement stock atomically
            for itm in cart["items"]:
                prod_id = itm["product_id"]
                req_qty = itm["quantity"]

                cursor.execute("SELECT stock_quantity, name, unit FROM products WHERE id = ?;", (prod_id,))
                prod = cursor.fetchone()
                if not prod or prod["stock_quantity"] < req_qty:
                    avail = prod["stock_quantity"] if prod else 0
                    raise ValueError(
                        f"Oversell Guard: Cannot finalize. '{itm['product_name']}' requires {req_qty}, "
                        f"but only {avail} in stock."
                    )

                cursor.execute(
                    """
                    UPDATE products
                    SET stock_quantity = stock_quantity - ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?;
                    """,
                    (req_qty, prod_id)
                )

            # 2. Compute final GST totals
            cart_summary = summarize_cart_gst(cart["items"])
            taxable = cart_summary["total_taxable_amount"]
            cgst = cart_summary["total_cgst"]
            sgst = cart_summary["total_sgst"]
            grand_total = cart_summary["grand_total"]

            # Customer ID resolution if provided
            cust_id = None
            if final_customer_name:
                cursor.execute("SELECT id, balance FROM customers WHERE name LIKE ?;", (final_customer_name,))
                cust_row = cursor.fetchone()
                if cust_row:
                    cust_id = cust_row["id"]
                else:
                    cursor.execute("INSERT INTO customers (name, balance) VALUES (?, 0.0);", (final_customer_name,))
                    cust_id = cursor.lastrowid

            # 3. Create completed bill record
            import uuid
            timestamp_str = datetime.now().strftime("%Y%m%d%H%M%S")
            bill_number = f"BILL-{timestamp_str}-{uuid.uuid4().hex[:4].upper()}"

            cursor.execute(
                """
                INSERT INTO bills (
                    bill_number, customer_id, customer_name, payment_mode,
                    total_taxable_amount, total_cgst, total_sgst, grand_total
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    bill_number,
                    cust_id,
                    final_customer_name,
                    final_payment_mode,
                    taxable,
                    cgst,
                    sgst,
                    grand_total
                )
            )
            bill_id = cursor.lastrowid

            # 4. Insert bill line items
            for itm in cart_summary["items"]:
                cursor.execute(
                    """
                    INSERT INTO bill_items (
                        bill_id, product_id, product_name, quantity, unit,
                        unit_price, cost_price, taxable_amount, hsn_code,
                        gst_rate, cgst_amount, sgst_amount, total_amount
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        bill_id,
                        itm["product_id"],
                        itm["product_name"],
                        itm["quantity"],
                        itm["unit"],
                        itm["unit_price"],
                        itm["cost_price"],
                        itm["taxable_amount"],
                        itm["hsn_code"],
                        itm["gst_rate"],
                        itm["cgst_amount"],
                        itm["sgst_amount"],
                        itm["gross_total"]
                    )
                )

            # 5. Handle Khata ledger debit if credit sale
            if final_payment_mode == "KHATA" and cust_id:
                cursor.execute(
                    """
                    UPDATE customers
                    SET balance = balance + ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?;
                    """,
                    (grand_total, cust_id)
                )
                cursor.execute("SELECT balance FROM customers WHERE id = ?;", (cust_id,))
                new_bal = cursor.fetchone()["balance"]

                cursor.execute(
                    """
                    INSERT INTO khata_transactions (
                        customer_id, transaction_type, amount, balance_after, bill_id, notes
                    ) VALUES (?, 'DEBIT', ?, ?, ?, ?);
                    """,
                    (cust_id, grand_total, new_bal, bill_id, f"Purchase on {bill_number}")
                )

            # 6. Clear draft bill
            cursor.execute("DELETE FROM draft_bills WHERE session_id = ?;", (session_id,))

        # Transaction successfully committed!

        # 7. Generate PDF Invoice artifact
        pdf_path = None
        if generate_pdf:
            invoice_payload = {
                "bill_number": bill_number,
                "customer_name": final_customer_name,
                "payment_mode": final_payment_mode,
                "created_at": datetime.now().strftime("%d-%m-%Y %H:%M"),
                "total_taxable_amount": taxable,
                "total_cgst": cgst,
                "total_sgst": sgst,
                "grand_total": grand_total,
                "items": cart_summary["items"]
            }
            pdf_path = generate_gst_invoice_pdf(invoice_payload)

        return {
            "status": "success",
            "message": f"Bill {bill_number} finalized successfully.",
            "bill_id": bill_id,
            "bill_number": bill_number,
            "customer_name": final_customer_name,
            "payment_mode": final_payment_mode,
            "grand_total": grand_total,
            "total_tax": cart_summary["total_tax"],
            "total_taxable_amount": taxable,
            "total_cgst": cgst,
            "total_sgst": sgst,
            "items_count": len(cart_summary["items"]),
            "items": cart_summary["items"],
            "invoice_pdf_path": pdf_path
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Finalization failed: {str(e)}"
        }
