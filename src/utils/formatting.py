"""Formatting utilities for Telegram chat responses and console output."""

from typing import Any, Dict, List


def format_currency(amount: float) -> str:
    """Format floating point numbers as Indian Rupees (₹)."""
    return f"₹{amount:,.2f}"


def format_bill_summary(bill: Dict[str, Any], is_draft: bool = False) -> str:
    """Format a bill or draft cart into a crisp Telegram HTML message."""
    title = "🛒 <b>CURRENT DRAFT BILL</b>" if is_draft else f"🧾 <b>BILL #{bill.get('bill_number', 'N/A')}</b>"
    lines = [
        title,
        "────────────────────────"
    ]

    if not is_draft and bill.get("customer_name"):
        lines.append(f"Customer :- <b>{bill['customer_name']}</b>")

    lines.append(f"Payment Mode :- <b>{bill.get('payment_mode', 'UPI')}</b>")
    lines.append("────────────────────────")

    items = bill.get("items", [])
    if not items:
        lines.append("<i>(No items added yet)</i>")
    else:
        for idx, itm in enumerate(items, 1):
            name = itm.get("product_name", itm.get("name", "Item"))
            qty = float(itm.get("quantity", 1))
            unit = itm.get("unit", "unit")
            rate = float(itm.get("unit_price", itm.get("selling_price", 0)))
            gross = float(itm.get("gross_total", round(qty * rate, 2)))
            gst_pct = int(round(float(itm.get("gst_rate", 0)) * 100))
            lines.append(
                f"{idx}. <b>{name}</b> :- <code>{qty:.1f} {unit}</code> @ ₹{rate:.2f} [GST {gst_pct}%] = <b>₹{gross:.2f}</b>"
            )

    lines.append("────────────────────────")
    
    total_items = len(items)
    total_units = sum(float(itm.get("quantity", 1)) for itm in items)
    unit_str = "item" if total_items == 1 else "items"
    lines.append(f"Total Items :- <b>{total_items} {unit_str} ({total_units:.1f} total units)</b>")

    taxable = float(bill.get("total_taxable_amount", 0.0))
    cgst = float(bill.get("total_cgst", 0.0))
    sgst = float(bill.get("total_sgst", 0.0))
    grand_total = float(bill.get("grand_total", 0.0))

    lines.append(f"Taxable Value :- ₹{taxable:.2f}")
    lines.append(f"CGST :- ₹{cgst:.2f}  |  SGST :- ₹{sgst:.2f}")

    # One empty line before grand total value
    lines.append("")
    lines.append(f"Grand Total :- <b>{format_currency(grand_total)}</b>")
    lines.append("────────────────────────")

    if is_draft:
        lines.append("<i>Say 'finalize' or 'confirm' to complete bill and cut stock.</i>")
        lines.append("<i>Or 'drop [item]' / 'make it [qty]' to edit.</i>")

    return "\n".join(lines)


def format_stock_table(products: List[Dict[str, Any]]) -> str:
    """
    Format product stock query into clean UI without raw asterisks.
    Format: Toor Dal (loose) :- 40.0 kg in stock @ ₹165.00
    """
    if not products:
        return "No matching products found in store catalog."

    lines = [
        "📦 <b>STORE INVENTORY STATUS</b>",
        "────────────────────────"
    ]
    for p in products:
        name = p.get("name")
        qty = float(p.get("stock_quantity", 0))
        unit = p.get("unit", "")
        reorder = float(p.get("reorder_level", 0))
        price = float(p.get("selling_price", 0))

        status_flag = " [LOW STOCK]" if qty <= reorder else ""
        lines.append(f"<b>{name}</b> :- <code>{qty:.1f} {unit}</code> in stock @ <b>₹{price:.2f}</b>{status_flag}")

    lines.append("────────────────────────")
    total_prods = len(products)
    lines.append(f"Total Listed Products :- <b>{total_prods}</b>")
    return "\n".join(lines)


def format_khata_statement(customer: Dict[str, Any], transactions: List[Dict[str, Any]]) -> str:
    """Format Khata balance and recent transaction history."""
    name = customer.get("name")
    balance = float(customer.get("balance", 0.0))

    lines = [
        f"📖 <b>Khata Ledger :- {name}</b>",
        "────────────────────────",
        f"Current Outstanding Balance :- <b>{format_currency(balance)}</b>",
        "────────────────────────"
    ]

    if not transactions:
        lines.append("<i>No recorded transactions.</i>")
    else:
        lines.append("<b>Recent Ledger Activity :-</b>")
        for t in transactions[:5]:
            ttype = t.get("transaction_type")
            amt = float(t.get("amount", 0.0))
            date = str(t.get("created_at", ""))[:10]
            notes = f" ({t['notes']})" if t.get("notes") else ""
            if ttype == "DEBIT":
                lines.append(f"  • +₹{amt:.2f} debt on {date}{notes}")
            else:
                lines.append(f"  • -₹{amt:.2f} payment on {date}{notes}")
        lines.append("────────────────────────")

    return "\n".join(lines)
