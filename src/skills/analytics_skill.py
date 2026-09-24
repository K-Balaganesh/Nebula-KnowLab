"""Analytics skill: Daily store close, sales aggregation, tax reporting, and payment method breakdown."""

from datetime import datetime, date
from typing import Any, Dict, List, Optional
from src.database.db import get_db_connection


def get_daily_close(target_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Generate the daily store closing report.
    Answers: "today's sales?", "close the day" -> total revenue, tax collected, cash vs UPI, top items.
    
    Args:
        target_date: Date string 'YYYY-MM-DD'. If None, defaults to current date.
    """
    if target_date is None:
        target_date = date.today().strftime("%Y-%m-%d")

    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Total sales and tax for target date
    cursor.execute(
        """
        SELECT 
            COUNT(*) as total_bills,
            COALESCE(SUM(total_taxable_amount), 0.0) as total_taxable,
            COALESCE(SUM(total_cgst), 0.0) as total_cgst,
            COALESCE(SUM(total_sgst), 0.0) as total_sgst,
            COALESCE(SUM(grand_total), 0.0) as total_revenue
        FROM bills
        WHERE DATE(created_at) = DATE(?);
        """,
        (target_date,)
    )
    sales_row = cursor.fetchone()

    total_bills = sales_row["total_bills"]
    total_revenue = sales_row["total_revenue"]
    total_cgst = sales_row["total_cgst"]
    total_sgst = sales_row["total_sgst"]
    total_tax = round(total_cgst + total_sgst, 2)

    # 2. Payment mode breakdown
    cursor.execute(
        """
        SELECT payment_mode, COUNT(*) as count, COALESCE(SUM(grand_total), 0.0) as amount
        FROM bills
        WHERE DATE(created_at) = DATE(?)
        GROUP BY payment_mode;
        """,
        (target_date,)
    )
    payment_rows = cursor.fetchall()
    payment_breakdown = {r["payment_mode"]: round(r["amount"], 2) for r in payment_rows}

    # 3. Top selling items today
    cursor.execute(
        """
        SELECT bi.product_name, SUM(bi.quantity) as total_qty, bi.unit, SUM(bi.total_amount) as total_sales
        FROM bill_items bi
        JOIN bills b ON bi.bill_id = b.id
        WHERE DATE(b.created_at) = DATE(?)
        GROUP BY bi.product_name
        ORDER BY total_sales DESC
        LIMIT 5;
        """,
        (target_date,)
    )
    top_items = [dict(r) for r in cursor.fetchall()]

    return {
        "status": "success",
        "date": target_date,
        "total_bills": total_bills,
        "total_revenue": total_revenue,
        "total_taxable": sales_row["total_taxable"],
        "total_tax_collected": total_tax,
        "cgst_collected": total_cgst,
        "sgst_collected": total_sgst,
        "payment_breakdown": payment_breakdown,
        "top_items": top_items
    }


def get_weekly_analytics_data() -> Dict[str, Any]:
    """Aggregate last 7 days of store operations for executive analysis deck."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Aggregate total sales
    cursor.execute(
        """
        SELECT 
            COUNT(*) as total_bills,
            COALESCE(SUM(grand_total), 0.0) as total_sales,
            COALESCE(SUM(total_cgst + total_sgst), 0.0) as total_gst
        FROM bills
        WHERE created_at >= DATETIME('now', '-7 days');
        """
    )
    totals = cursor.fetchone()

    # Payment split
    cursor.execute(
        """
        SELECT payment_mode, COALESCE(SUM(grand_total), 0.0) as amount
        FROM bills
        WHERE created_at >= DATETIME('now', '-7 days')
        GROUP BY payment_mode;
        """
    )
    pay_split = {r["payment_mode"]: round(r["amount"], 2) for r in cursor.fetchall()}

    # Top items
    cursor.execute(
        """
        SELECT bi.product_name as name, SUM(bi.quantity) as quantity, SUM(bi.total_amount) as revenue
        FROM bill_items bi
        JOIN bills b ON bi.bill_id = b.id
        WHERE b.created_at >= DATETIME('now', '-7 days')
        GROUP BY bi.product_name
        ORDER BY revenue DESC
        LIMIT 6;
        """
    )
    top_items = [dict(r) for r in cursor.fetchall()]

    # Low stock items
    cursor.execute(
        """
        SELECT name, stock_quantity as stock, reorder_level as reorder, unit,
               CASE 
                   WHEN stock_quantity <= (reorder_level / 2) THEN 'CRITICAL'
                   ELSE 'LOW'
               END as status
        FROM products
        WHERE stock_quantity <= reorder_level
        ORDER BY stock_quantity ASC
        LIMIT 6;
        """
    )
    low_stock = [dict(r) for r in cursor.fetchall()]

    return {
        "total_sales": totals["total_sales"],
        "total_gst": totals["total_gst"],
        "total_bills": totals["total_bills"],
        "payment_split": pay_split,
        "top_items": top_items,
        "low_stock_items": low_stock
    }
