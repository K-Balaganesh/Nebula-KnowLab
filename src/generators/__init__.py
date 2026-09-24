"""Document artifact generators package (PDF Tax Invoices & PPTX Analysis Decks)."""
from .invoice_pdf import generate_gst_invoice_pdf
from .analysis_pptx import generate_weekly_analysis_pptx

__all__ = ["generate_gst_invoice_pdf", "generate_weekly_analysis_pptx"]
