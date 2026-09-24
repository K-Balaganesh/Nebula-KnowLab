"""Khata skill: Managing customer credit ledger, balance queries, credit additions, and settlements."""

from typing import Any, Dict, List, Optional
from src.database.db import get_db_connection, transaction


def get_khata_balance(customer_name: str) -> Dict[str, Any]:
    """
    Look up customer credit (khata) balance and recent transaction history.
    
    Args:
        customer_name: Name of the customer (e.g. "Ramesh")
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM customers WHERE name LIKE ? ORDER BY LENGTH(name) ASC LIMIT 1;",
        (f"%{customer_name.strip()}%",)
    )
    customer = cursor.fetchone()
    if not customer:
        return {
            "status": "not_found",
            "message": f"No customer found matching '{customer_name}' in Khata records."
        }

    cust_id = customer["id"]
    cursor.execute(
        """
        SELECT id, transaction_type, amount, balance_after, notes, created_at
        FROM khata_transactions
        WHERE customer_id = ?
        ORDER BY created_at DESC
        LIMIT 10;
        """,
        (cust_id,)
    )
    tx_rows = cursor.fetchall()

    return {
        "status": "success",
        "customer_id": cust_id,
        "customer_name": customer["name"],
        "phone": customer["phone"],
        "balance": customer["balance"],
        "recent_transactions": [dict(t) for t in tx_rows]
    }


def add_credit_entry(
    customer_name: str,
    amount: float,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """
    Put money on customer's credit ledger (increases customer's outstanding balance).
    Example: "put ₹500 on Ramesh's credit"
    
    Args:
        customer_name: Customer name (e.g. "Ramesh")
        amount: Amount to credit in ₹ (must be positive)
        notes: Optional description
    """
    if amount <= 0:
        return {"status": "error", "message": "Credit amount must be greater than zero."}

    conn = get_db_connection()
    with transaction(conn):
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM customers WHERE name LIKE ? LIMIT 1;",
            (f"%{customer_name.strip()}%",)
        )
        customer = cursor.fetchone()

        # If customer does not exist, create new customer ledger
        if not customer:
            cursor.execute(
                "INSERT INTO customers (name, balance) VALUES (?, 0.0);",
                (customer_name.strip(),)
            )
            cust_id = cursor.lastrowid
            cust_name = customer_name.strip()
            prev_balance = 0.0
        else:
            cust_id = customer["id"]
            cust_name = customer["name"]
            prev_balance = customer["balance"]

        new_balance = round(prev_balance + amount, 2)

        cursor.execute(
            "UPDATE customers SET balance = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;",
            (new_balance, cust_id)
        )

        cursor.execute(
            """
            INSERT INTO khata_transactions (
                customer_id, transaction_type, amount, balance_after, notes
            ) VALUES (?, 'DEBIT', ?, ?, ?);
            """,
            (cust_id, amount, new_balance, notes or "Manual credit entry")
        )

        return {
            "status": "success",
            "message": f"Added ₹{amount:.2f} to {cust_name}'s credit.",
            "customer_name": cust_name,
            "amount_added": amount,
            "previous_balance": prev_balance,
            "current_balance": new_balance
        }


def record_khata_payment(
    customer_name: str,
    amount: float,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """
    Record a debt repayment made by a customer (decreases customer's outstanding balance).
    Example: "Ramesh paid ₹300"
    
    HARD PART GUARDRAIL 7:
    Refuse to settle a khata that does not exist.
    
    Args:
        customer_name: Customer name (e.g. "Ramesh")
        amount: Repayment amount in ₹
        notes: Optional payment note
    """
    if amount <= 0:
        return {"status": "error", "message": "Payment amount must be greater than zero."}

    conn = get_db_connection()
    with transaction(conn):
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM customers WHERE name LIKE ? LIMIT 1;",
            (f"%{customer_name.strip()}%",)
        )
        customer = cursor.fetchone()

        # Guardrail: Do not settle a khata that doesn't exist
        if not customer:
            return {
                "status": "error",
                "message": f"Guardrail: Customer '{customer_name}' does not exist in Khata records. Cannot settle a non-existent account."
            }

        cust_id = customer["id"]
        cust_name = customer["name"]
        prev_balance = customer["balance"]

        new_balance = round(prev_balance - amount, 2)

        cursor.execute(
            "UPDATE customers SET balance = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;",
            (new_balance, cust_id)
        )

        cursor.execute(
            """
            INSERT INTO khata_transactions (
                customer_id, transaction_type, amount, balance_after, notes
            ) VALUES (?, 'CREDIT', ?, ?, ?);
            """,
            (cust_id, amount, new_balance, notes or "Cash/UPI repayment")
        )

        return {
            "status": "success",
            "message": f"Payment of ₹{amount:.2f} recorded for {cust_name}.",
            "customer_name": cust_name,
            "amount_paid": amount,
            "previous_balance": prev_balance,
            "current_balance": new_balance
        }


def list_khata_balances() -> Dict[str, Any]:
    """List all customers with outstanding credit balances."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, name, phone, balance, updated_at
        FROM customers
        WHERE balance > 0
        ORDER BY balance DESC;
        """
    )
    rows = cursor.fetchall()
    return {
        "status": "success",
        "total_outstanding": sum(r["balance"] for r in rows),
        "customers": [dict(r) for r in rows]
    }


# Function alias
add_khata_credit = add_credit_entry
