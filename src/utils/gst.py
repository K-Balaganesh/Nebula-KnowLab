"""GST computation engine strictly adhering to Indian Intra-State tax rules."""

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List


def to_decimal(val: Any) -> Decimal:
    """Safely convert value to Decimal."""
    return Decimal(str(val))


def quantize_paise(val: Decimal) -> Decimal:
    """Round to 2 decimal places (paise) using ROUND_HALF_UP."""
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_item_gst(
    quantity: float,
    selling_price: float,
    gst_rate: float,
    inclusive: bool = True
) -> Dict[str, float]:
    """
    Calculate GST for a single line item.
    In Indian retail (kirana/supermarkets), MRP / retail price is inclusive of GST.
    
    If inclusive:
      gross_total = quantity * selling_price
      taxable_amount = gross_total / (1 + gst_rate)
      total_tax = gross_total - taxable_amount
      cgst_amount = total_tax / 2
      sgst_amount = total_tax - cgst_amount
    
    If exclusive:
      taxable_amount = quantity * selling_price
      total_tax = taxable_amount * gst_rate
      cgst_amount = total_tax / 2
      sgst_amount = total_tax - cgst_amount
      gross_total = taxable_amount + total_tax
    """
    qty = to_decimal(quantity)
    rate = to_decimal(selling_price)
    tax_rate = to_decimal(gst_rate)

    if inclusive:
        gross_total = quantize_paise(qty * rate)
        if tax_rate > Decimal("0"):
            one_plus_tax = Decimal("1") + tax_rate
            taxable_amount = quantize_paise(gross_total / one_plus_tax)
            total_tax = gross_total - taxable_amount
            # Intra-state 50-50 split
            cgst_amount = quantize_paise(total_tax / Decimal("2"))
            sgst_amount = total_tax - cgst_amount  # Keeps exact total_tax balance
        else:
            taxable_amount = gross_total
            total_tax = Decimal("0.00")
            cgst_amount = Decimal("0.00")
            sgst_amount = Decimal("0.00")
    else:
        taxable_amount = quantize_paise(qty * rate)
        total_tax = quantize_paise(taxable_amount * tax_rate)
        cgst_amount = quantize_paise(total_tax / Decimal("2"))
        sgst_amount = total_tax - cgst_amount
        gross_total = taxable_amount + total_tax

    cgst_rate = quantize_paise(tax_rate / Decimal("2"))
    sgst_rate = quantize_paise(tax_rate / Decimal("2"))

    return {
        "quantity": float(qty),
        "unit_price": float(rate),
        "gst_rate": float(tax_rate),
        "cgst_rate": float(cgst_rate),
        "sgst_rate": float(sgst_rate),
        "taxable_amount": float(taxable_amount),
        "cgst_amount": float(cgst_amount),
        "sgst_amount": float(sgst_amount),
        "total_tax": float(total_tax),
        "gross_total": float(gross_total),
    }


def summarize_cart_gst(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Summarize a collection of items into total taxable amount, CGST, SGST, grand total,
    and a breakdown categorized by GST slab (0%, 5%, 12%, 18%, 28%).
    """
    total_taxable = Decimal("0.00")
    total_cgst = Decimal("0.00")
    total_sgst = Decimal("0.00")
    grand_total = Decimal("0.00")

    slab_breakup: Dict[str, Dict[str, Decimal]] = {}

    processed_items = []
    for itm in items:
        qty = float(itm.get("quantity", 1))
        unit_price = float(itm.get("unit_price", itm.get("selling_price", 0)))
        gst_rate = float(itm.get("gst_rate", 0))

        calc = calculate_item_gst(qty, unit_price, gst_rate, inclusive=True)

        total_taxable += to_decimal(calc["taxable_amount"])
        total_cgst += to_decimal(calc["cgst_amount"])
        total_sgst += to_decimal(calc["sgst_amount"])
        grand_total += to_decimal(calc["gross_total"])

        slab_key = f"{int(round(gst_rate * 100))}%"
        if slab_key not in slab_breakup:
            slab_breakup[slab_key] = {
                "taxable": Decimal("0.00"),
                "cgst": Decimal("0.00"),
                "sgst": Decimal("0.00"),
                "total_tax": Decimal("0.00"),
            }
        slab_breakup[slab_key]["taxable"] += to_decimal(calc["taxable_amount"])
        slab_breakup[slab_key]["cgst"] += to_decimal(calc["cgst_amount"])
        slab_breakup[slab_key]["sgst"] += to_decimal(calc["sgst_amount"])
        slab_breakup[slab_key]["total_tax"] += to_decimal(calc["total_tax"])

        item_copy = dict(itm)
        item_copy.update(calc)
        processed_items.append(item_copy)

    # Convert Decimal to float for JSON compatibility
    formatted_slabs = {
        k: {
            "taxable": float(v["taxable"]),
            "cgst": float(v["cgst"]),
            "sgst": float(v["sgst"]),
            "total_tax": float(v["total_tax"]),
        }
        for k, v in slab_breakup.items()
    }

    return {
        "items": processed_items,
        "total_taxable_amount": float(quantize_paise(total_taxable)),
        "total_cgst": float(quantize_paise(total_cgst)),
        "total_sgst": float(quantize_paise(total_sgst)),
        "total_tax": float(quantize_paise(total_cgst + total_sgst)),
        "grand_total": float(quantize_paise(grand_total)),
        "slab_breakup": formatted_slabs,
    }
