"""Indian GST-compliant Tax Invoice PDF generator."""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from src.config import INVOICES_DIR, STORE_NAME, STORE_GSTIN, STORE_ADDRESS, STORE_STATE, STORE_STATE_CODE


def generate_gst_invoice_pdf(bill_data: Dict[str, Any], output_path: Optional[Path] = None) -> str:
    """
    Generate a professional Indian GST Tax Invoice PDF from bill data.
    
    Args:
        bill_data: Dictionary containing bill_number, items, taxable, cgst, sgst, grand_total, payment_mode, customer_name
        output_path: Optional target file path. If None, saves to INVOICES_DIR.
        
    Returns:
        Absolute string path to the created PDF file.
    """
    bill_no = bill_data.get("bill_number", f"BILL-{int(datetime.now().timestamp())}")
    if output_path is None:
        output_path = INVOICES_DIR / f"invoice_{bill_no.replace('/', '_')}.pdf"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            HRFlowable,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            alignment=1,  # Center
            textColor=colors.HexColor("#1A365D"),
        )
        subtitle_style = ParagraphStyle(
            "DocSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            alignment=1,
            textColor=colors.HexColor("#4A5568"),
        )
        section_style = ParagraphStyle(
            "SectionHead",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#2D3748"),
        )
        cell_style = ParagraphStyle(
            "CellText",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
        )
        cell_bold = ParagraphStyle(
            "CellBold",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
        )

        elements = []

        # 1. Header (Store identity & Tax Invoice title)
        elements.append(Paragraph(STORE_NAME.upper(), title_style))
        store_sub = (
            f"{STORE_ADDRESS}<br/>"
            f"<b>GSTIN:</b> {STORE_GSTIN} | <b>State:</b> {STORE_STATE} (Code: {STORE_STATE_CODE})<br/>"
            f"<b>TAX INVOICE</b>"
        )
        elements.append(Paragraph(store_sub, subtitle_style))
        elements.append(Spacer(1, 10))
        elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#CBD5E0"), spaceAfter=10))

        # 2. Invoice & Customer Meta
        created_date = bill_data.get("created_at", datetime.now().strftime("%d-%m-%Y %H:%M"))
        customer_name = bill_data.get("customer_name") or "Cash Customer"
        pay_mode = bill_data.get("payment_mode", "UPI")

        meta_data = [
            [
                Paragraph(f"<b>Invoice No:</b> {bill_no}", cell_style),
                Paragraph(f"<b>Date:</b> {created_date}", cell_style),
            ],
            [
                Paragraph(f"<b>Billed To:</b> {customer_name}", cell_style),
                Paragraph(f"<b>Payment Mode:</b> {pay_mode}", cell_style),
            ],
            [
                Paragraph(f"<b>Place of Supply:</b> {STORE_STATE} ({STORE_STATE_CODE})", cell_style),
                Paragraph("<b>Reverse Charge:</b> No", cell_style),
            ],
        ]
        meta_table = Table(meta_data, colWidths=[270, 250])
        meta_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7FAFC")),
            ("PADDING", (0, 0), (-1, -1), 4),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements.append(meta_table)
        elements.append(Spacer(1, 12))

        # 3. Line Items Table with GST Columns
        headers = [
            Paragraph("<b>#</b>", cell_bold),
            Paragraph("<b>Item Description</b>", cell_bold),
            Paragraph("<b>HSN</b>", cell_bold),
            Paragraph("<b>Qty</b>", cell_bold),
            Paragraph("<b>Rate (Rs.)</b>", cell_bold),
            Paragraph("<b>Taxable (Rs.)</b>", cell_bold),
            Paragraph("<b>CGST</b>", cell_bold),
            Paragraph("<b>SGST</b>", cell_bold),
            Paragraph("<b>Total (Rs.)</b>", cell_bold),
        ]

        table_data = [headers]
        items = bill_data.get("items", [])
        for idx, itm in enumerate(items, 1):
            name = itm.get("product_name", itm.get("name", "Item"))
            qty = f"{itm.get('quantity', 1)} {itm.get('unit', '')}".strip()
            rate = f"{itm.get('unit_price', itm.get('selling_price', 0)):.2f}"
            taxable = f"{itm.get('taxable_amount', 0):.2f}"
            cgst = f"{itm.get('cgst_amount', 0):.2f}"
            sgst = f"{itm.get('sgst_amount', 0):.2f}"
            total = f"{itm.get('total_amount', itm.get('gross_total', 0)):.2f}"
            hsn = str(itm.get("hsn_code", "0000"))

            row = [
                Paragraph(str(idx), cell_style),
                Paragraph(name, cell_style),
                Paragraph(hsn, cell_style),
                Paragraph(qty, cell_style),
                Paragraph(rate, cell_style),
                Paragraph(taxable, cell_style),
                Paragraph(cgst, cell_style),
                Paragraph(sgst, cell_style),
                Paragraph(total, cell_style),
            ]
            table_data.append(row)

        col_widths = [20, 155, 45, 45, 48, 55, 45, 45, 62]
        items_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        items_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2B6CB0")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("PADDING", (0, 0), (-1, -1), 4),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements.append(items_table)
        elements.append(Spacer(1, 10))

        # 4. Summary & Tax Totals Box
        taxable_tot = bill_data.get("total_taxable_amount", 0.0)
        cgst_tot = bill_data.get("total_cgst", 0.0)
        sgst_tot = bill_data.get("total_sgst", 0.0)
        grand_tot = bill_data.get("grand_total", 0.0)

        summary_rows = [
            [Paragraph("Total Taxable Value:", cell_style), Paragraph(f"Rs. {taxable_tot:.2f}", cell_bold)],
            [Paragraph("Central GST (CGST):", cell_style), Paragraph(f"Rs. {cgst_tot:.2f}", cell_bold)],
            [Paragraph("State GST (SGST):", cell_style), Paragraph(f"Rs. {sgst_tot:.2f}", cell_bold)],
            [Paragraph("<b>Grand Total:</b>", cell_bold), Paragraph(f"<b>Rs. {grand_tot:.2f}</b>", cell_bold)],
        ]
        sum_table = Table(summary_rows, colWidths=[150, 100])
        sum_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EDF2F7")),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("PADDING", (0, 0), (-1, -1), 4),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E0")),
            ("LINEBELOW", (0, -1), (-1, -1), 1.5, colors.HexColor("#2B6CB0")),
        ]))

        # Place summary on the right side
        summary_wrapper = Table(
            [[Paragraph("<i>Thank you for shopping with us!</i><br/>This is a computer-generated tax invoice.", cell_style), sum_table]],
            colWidths=[270, 250]
        )
        summary_wrapper.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ]))
        elements.append(summary_wrapper)

        # Build PDF
        doc.build(elements)
        return str(output_path.resolve())

    except ImportError:
        # Fallback PDF generator using raw PostScript/PDF format if reportlab is not yet installed
        return _generate_fallback_pdf(bill_data, output_path)


def _generate_fallback_pdf(bill_data: Dict[str, Any], output_path: Path) -> str:
    """Creates a basic valid PDF text document without external dependencies."""
    bill_no = bill_data.get("bill_number", "BILL-001")
    lines = [
        f"{STORE_NAME} - GST TAX INVOICE",
        f"GSTIN: {STORE_GSTIN} | Address: {STORE_ADDRESS}",
        f"Invoice: {bill_no} | Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Customer: {bill_data.get('customer_name', 'Cash')} | Mode: {bill_data.get('payment_mode', 'UPI')}",
        "-" * 60,
    ]
    for itm in bill_data.get("items", []):
        name = itm.get("product_name", itm.get("name", "Item"))
        qty = itm.get("quantity", 1)
        rate = itm.get("unit_price", 0)
        tot = itm.get("total_amount", itm.get("gross_total", 0))
        lines.append(f"{name} x {qty} @ Rs {rate:.2f} = Rs {tot:.2f}")

    lines.append("-" * 60)
    lines.append(f"Taxable Value: Rs {bill_data.get('total_taxable_amount', 0):.2f}")
    lines.append(f"CGST: Rs {bill_data.get('total_cgst', 0):.2f} | SGST: Rs {bill_data.get('total_sgst', 0):.2f}")
    lines.append(f"Grand Total: Rs {bill_data.get('grand_total', 0):.2f}")

    content = "\n".join(lines)
    # Minimal PDF syntax
    stream_data = f"BT /F1 10 Tf 50 750 Td 12 TL\n"
    for line in lines:
        escaped = line.replace("(", "\\(").replace(")", "\\)")
        stream_data += f"({escaped}) '\n"
    stream_data += "ET"

    pdf_text = (
        "%PDF-1.4\n"
        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
        f"4 0 obj << /Length {len(stream_data)} >> stream\n{stream_data}\nendstream\nendobj\n"
        "5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Courier >> endobj\n"
        "xref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000228 00000 n \n0000000300 00000 n \n"
        "trailer << /Size 6 /Root 1 0 R >>\nstartxref\n380\n%%EOF"
    )
    with open(output_path, "wb") as f:
        f.write(pdf_text.encode("latin-1"))

    return str(output_path.resolve())
