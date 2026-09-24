"""Tool registry: Central capability surface with function schemas and dynamic execution dispatcher."""

import json
from typing import Any, Callable, Dict, List, Optional

from src.skills.inventory_skill import search_inventory, stock_in, add_product, check_low_stock
from src.skills.billing_skill import add_or_update_cart, edit_draft_cart, get_active_bill, clear_active_bill, finalize_bill
from src.skills.khata_skill import get_khata_balance, add_khata_credit, add_credit_entry, record_khata_payment, list_khata_balances
from src.skills.analytics_skill import get_daily_close
from src.skills.preference_skill import set_store_preference, get_store_preferences
from src.skills.document_skill import generate_bill_invoice_pdf, generate_analysis_deck_pptx


# Tool Schemas for LLM Function Calling
TOOL_DEFINITIONS = [
    {
        "name": "search_inventory",
        "description": "Look up products in the store inventory to check available stock, unit price, unit, and GST slab. Always use this before answering stock questions or if a product name is ambiguous.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Product search query, brand, or category (e.g. 'sugar', 'Maggi', 'atta'). Leave empty to list items."
                }
            }
        }
    },
    {
        "name": "stock_in",
        "description": "Receive new incoming stock for an existing product. Increments inventory count and optionally updates cost or selling price.",
        "parameters": {
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "Name of the product (e.g. 'Maggi 70g')"
                },
                "quantity": {
                    "type": "number",
                    "description": "Number of units received (e.g. 50)"
                },
                "cost_price": {
                    "type": "number",
                    "description": "Optional wholesale cost price in ₹ (e.g. 12)"
                },
                "selling_price": {
                    "type": "number",
                    "description": "Optional retail MRP / selling price in ₹ (e.g. 14)"
                }
            },
            "required": ["item_name", "quantity"]
        }
    },
    {
        "name": "add_product",
        "description": "Add a new SKU to the store catalog with tax slab and HSN code.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Full product name (e.g. 'Amul Butter 100g')"},
                "category": {"type": "string", "description": "Category (e.g. 'Dairy', 'Staples')"},
                "unit": {"type": "string", "description": "Unit of measurement ('packet', 'kg', 'litre', 'piece')"},
                "cost_price": {"type": "number", "description": "Cost price in ₹"},
                "selling_price": {"type": "number", "description": "MRP / Retail selling price in ₹"},
                "gst_rate": {"type": "number", "description": "GST rate as decimal: 0.0, 0.05, 0.12, 0.18, or 0.28"},
                "hsn_code": {"type": "string", "description": "Indian HSN code (e.g. '0405', '1902')"},
                "initial_stock": {"type": "number", "description": "Initial stock quantity (default 0)"},
                "is_loose": {"type": "boolean", "description": "True if sold loose by kg/litre"}
            },
            "required": ["name", "cost_price", "selling_price", "gst_rate"]
        }
    },
    {
        "name": "check_low_stock",
        "description": "Get a list of all products currently at or below their reorder threshold.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "add_or_update_cart",
        "description": "Start a new bill or add items to the current draft bill. Performs oversell check at tool layer. Does NOT decrement stock yet.",
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "description": "List of items to add",
                    "items": {
                        "type": "object",
                        "properties": {
                            "item_name": {"type": "string", "description": "Item name (e.g. 'sugar', 'Aashirvaad atta 5kg')"},
                            "quantity": {"type": "number", "description": "Quantity to buy (e.g. 2, 4)"}
                        },
                        "required": ["item_name", "quantity"]
                    }
                },
                "customer_name": {"type": "string", "description": "Optional customer name"},
                "payment_mode": {"type": "string", "description": "Optional payment mode ('UPI', 'CASH', 'CARD', 'KHATA')"}
            },
            "required": ["items"]
        }
    },
    {
        "name": "edit_draft_cart",
        "description": "Edit the active draft bill mid-build (e.g. drop an item, change quantity of an item, change payment mode).",
        "parameters": {
            "type": "object",
            "properties": {
                "remove_items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of item names to remove (e.g. ['butter'])"
                },
                "set_quantities": {
                    "type": "object",
                    "description": "Map of item name to new exact quantity (e.g. {'Maggi': 6})"
                },
                "payment_mode": {
                    "type": "string",
                    "description": "Change payment mode ('UPI', 'CASH', 'CARD', 'KHATA')"
                }
            }
        }
    },
    {
        "name": "get_active_bill",
        "description": "View current active draft bill and tax breakdown.",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "clear_active_bill",
        "description": "Cancel or clear current draft bill without saving or decrementing stock.",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "finalize_bill",
        "description": "Finalize and complete the draft bill. Atomically decrements inventory, records bill in DB, updates Khata if credit, and generates GST invoice PDF.",
        "parameters": {
            "type": "object",
            "properties": {
                "payment_mode": {"type": "string", "description": "Final payment mode ('UPI', 'CASH', 'CARD', 'KHATA')"},
                "customer_name": {"type": "string", "description": "Customer name (mandatory for KHATA)"}
            }
        }
    },
    {
        "name": "get_khata_balance",
        "description": "Check a customer's Khata (credit ledger) balance and recent transaction history.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_name": {"type": "string", "description": "Customer name (e.g. 'Ramesh')"}
            },
            "required": ["customer_name"]
        }
    },
    {
        "name": "add_khata_credit",
        "description": "Put an amount on a customer's credit ledger (increases outstanding balance).",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_name": {"type": "string", "description": "Customer name (e.g. 'Ramesh')"},
                "amount": {"type": "number", "description": "Amount to credit in ₹ (e.g. 500)"},
                "notes": {"type": "string", "description": "Optional notes"}
            },
            "required": ["customer_name", "amount"]
        }
    },
    {
        "name": "record_khata_payment",
        "description": "Record a customer's debt repayment (decreases outstanding balance). Enforces guardrail that customer must exist.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_name": {"type": "string", "description": "Customer name (e.g. 'Ramesh')"},
                "amount": {"type": "number", "description": "Repayment amount in ₹ (e.g. 300)"},
                "notes": {"type": "string", "description": "Optional notes"}
            },
            "required": ["customer_name", "amount"]
        }
    },
    {
        "name": "get_daily_close",
        "description": "Get daily store closing report including total revenue, tax collected, cash vs UPI split, and top items.",
        "parameters": {
            "type": "object",
            "properties": {
                "target_date": {"type": "string", "description": "Optional date 'YYYY-MM-DD'"}
            }
        }
    },
    {
        "name": "generate_bill_invoice_pdf",
        "description": "Produce a clean, GST-correct PDF invoice for a bill. If bill_number is omitted, uses the most recent bill.",
        "parameters": {
            "type": "object",
            "properties": {
                "bill_number_or_id": {"type": "string", "description": "Optional bill number or bill ID"}
            }
        }
    },
    {
        "name": "generate_analysis_deck_pptx",
        "description": "Generate this week's sales analysis PowerPoint presentation (.pptx) with real charts and insights.",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "set_store_preference",
        "description": "Save a persistent store preference that survives across /new chats (e.g. default payment mode, default brand).",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Preference key (e.g. 'default_payment', 'default_atta')"},
                "value": {"type": "string", "description": "Preference value (e.g. 'UPI', 'Aashirvaad Atta 5kg')"}
            },
            "required": ["key", "value"]
        }
    },
    {
        "name": "get_store_preferences",
        "description": "Get all persistent store preferences saved in the database.",
        "parameters": {"type": "object", "properties": {}}
    }
]


def execute_tool(name: str, arguments: Dict[str, Any], session_id: str) -> Dict[str, Any]:
    """Execute a registered skill tool by name with arguments and session context."""
    args = dict(arguments or {})

    try:
        # Route to respective handler
        if name == "search_inventory":
            return search_inventory(query=args.get("query", ""))
        
        elif name == "stock_in":
            return stock_in(
                item_name=args["item_name"],
                quantity=float(args["quantity"]),
                cost_price=float(args["cost_price"]) if "cost_price" in args and args["cost_price"] is not None else None,
                selling_price=float(args["selling_price"]) if "selling_price" in args and args["selling_price"] is not None else None,
            )

        elif name == "add_product":
            return add_product(
                name=args["name"],
                category=args.get("category", "General"),
                unit=args.get("unit", "packet"),
                cost_price=float(args["cost_price"]),
                selling_price=float(args["selling_price"]),
                gst_rate=float(args["gst_rate"]),
                hsn_code=args.get("hsn_code", "0000"),
                initial_stock=float(args.get("initial_stock", 0.0)),
                is_loose=bool(args.get("is_loose", False)),
                reorder_level=float(args.get("reorder_level", 5.0))
            )

        elif name == "check_low_stock":
            return check_low_stock()

        elif name == "add_or_update_cart":
            return add_or_update_cart(
                session_id=session_id,
                items=args.get("items", []),
                customer_name=args.get("customer_name"),
                payment_mode=args.get("payment_mode")
            )

        elif name == "edit_draft_cart":
            return edit_draft_cart(
                session_id=session_id,
                remove_items=args.get("remove_items"),
                set_quantities=args.get("set_quantities"),
                payment_mode=args.get("payment_mode")
            )

        elif name == "get_active_bill":
            return get_active_bill(session_id=session_id)

        elif name == "clear_active_bill":
            return clear_active_bill(session_id=session_id)

        elif name == "finalize_bill":
            return finalize_bill(
                session_id=session_id,
                payment_mode=args.get("payment_mode"),
                customer_name=args.get("customer_name"),
                generate_pdf=True
            )

        elif name == "get_khata_balance":
            return get_khata_balance(customer_name=args["customer_name"])

        elif name == "add_khata_credit":
            return add_khata_credit(
                customer_name=args["customer_name"],
                amount=float(args["amount"]),
                notes=args.get("notes")
            )

        elif name == "record_khata_payment":
            return record_khata_payment(
                customer_name=args["customer_name"],
                amount=float(args["amount"]),
                notes=args.get("notes")
            )

        elif name == "get_daily_close":
            return get_daily_close(target_date=args.get("target_date"))

        elif name == "generate_bill_invoice_pdf":
            return generate_bill_invoice_pdf(bill_number_or_id=args.get("bill_number_or_id"))

        elif name == "generate_analysis_deck_pptx":
            return generate_analysis_deck_pptx()

        elif name == "set_store_preference":
            return set_store_preference(key=args["key"], value=args["value"])

        elif name == "get_store_preferences":
            return get_store_preferences()

        else:
            return {"status": "error", "message": f"Unknown tool: '{name}'"}

    except Exception as e:
        return {"status": "error", "message": f"Tool execution exception in '{name}': {str(e)}"}
