"""Document generation skill: Triggers real GST invoice PDFs and PowerPoint analysis decks."""

from typing import Any, Dict, Optional
from src.database.db import get_db_connection
from src.generators.invoice_pdf import generate_gst_invoice_pdf
from src.generators.analysis_pptx import generate_weekly_analysis_pptx
from src.skills.analytics_skill import get_weekly_analytics_data


def generate_bill_invoice_pdf(bill_number_or_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Generate a GST-correct tax invoice PDF document for a bill.
    If no bill number is provided, produces PDF for the latest finalized bill.
    
    Args:
        bill_number_or_id: Optional bill number (e.g. 'BILL-20260923171500') or bill ID.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if bill_number_or_id:
        cursor.execute(
            "SELECT * FROM bills WHERE bill_number = ? OR id = ? LIMIT 1;",
            (bill_number_or_id, bill_number_or_id)
        )
    else:
        cursor.execute("SELECT * FROM bills ORDER BY id DESC LIMIT 1;")

    bill_row = cursor.fetchone()
    if not bill_row:
        return {
            "status": "error",
            "message": "No finalized bill found to generate PDF invoice."
        }

    bill_id = bill_row["id"]
    cursor.execute("SELECT * FROM bill_items WHERE bill_id = ?;", (bill_id,))
    item_rows = cursor.fetchall()

    bill_data = dict(bill_row)
    bill_data["items"] = [dict(i) for i in item_rows]

    pdf_path = generate_gst_invoice_pdf(bill_data)
    return {
        "status": "success",
        "message": f"Generated GST Tax Invoice PDF for {bill_row['bill_number']}.",
        "bill_number": bill_row["bill_number"],
        "pdf_path": pdf_path,
        "is_file_artifact": True,
        "artifact_type": "PDF"
    }


def generate_analysis_deck_pptx() -> Dict[str, Any]:
    """
    Generate an executive PowerPoint (.pptx) deck analyzing store performance with real charts.
    Includes sales KPIs, top SKUs column chart, payment mode pie chart, and stock health table.
    """
    analytics_data = get_weekly_analytics_data()
    pptx_path = generate_weekly_analysis_pptx(analytics_data)

    return {
        "status": "success",
        "message": "Weekly business analysis PowerPoint presentation generated successfully with embedded charts.",
        "pptx_path": pptx_path,
        "is_file_artifact": True,
        "artifact_type": "PPTX"
    }
