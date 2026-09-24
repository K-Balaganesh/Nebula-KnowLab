# Supermarket Ops Agent — Indian Kirana / Supermarket

> **Nebula KnowLab Engineering Take-Home Assignment**  
> *Run an entire Indian kirana store from a chat window — with an agent, not a menu.*

Telegram Bot Handle: **`@bala_kmc_market_bot`** *(Configure your token in `.env`)*  
Collaborators Invited: `Aswath363`, `akshaiP`, `ashwanthnebula`

---

## 1. Harness Choice & Justification

We selected the **Google GenAI / Autonomous ReAct Agent Harness** in Python for this deployment:

### Why this harness?
1. **Dynamic Tool Calling over Rigid State Machines**: The assignment explicitly cautions against LangGraph-style node-per-command state machines or regex/if-else intent routers. In our architecture, the LLM reasons freely over unstructured, terse shopkeeper phrasing, selects tools dynamically from declarative JSON function declarations, and evaluates intermediate tool outputs.
2. **Deterministic Tool Separation**: The LLM *never* performs business logic (e.g. subtracting stock, computing GST percentages, checking credit limits). Instead, the model only coordinates intent, while all state mutations and domain rules execute inside transactional Python tools.
3. **Multi-Turn ReAct Loop**: Supports chained execution within a single turn (e.g., `Observe` $\to$ `search_inventory` $\to$ `Reason` $\to$ `add_or_update_cart` $\to$ `Feed Back` $\to$ `Finalize Response`).
4. **Dual Engine Reliability**: Features a live Gemini integration with a deterministic autonomous semantic reasoner fallback so tests and demonstrations can be executed even in offline or local test environments.

---

## 2. Agent Control Loop Architecture

```
User Message (Telegram / CLI)
           │
           ▼
┌──────────────────────────────────────────────┐
│       Telegram Gateway & Idempotency         │
│ (Checks `processed_updates` to stop retries) │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│           Agent Control Loop (ReAct)         │
│                                              │
│  1. Ingest Conversation History + Memory     │
│  2. Inject Persistent Store Preferences      │
│  3. Model Observation & Tool Selection       │
│  4. Dynamic Tool Execution & Exception Catch │
│  5. Feed Observation Back to Reasoner        │
│  6. Generate Terse Shopkeeper Output         │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│          Transactional Skill Layer           │
│   (Inventory, Billing, Khata, Analytics)     │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│            SQLite WAL Database               │
│ (ACID Transactions + CHECK (stock >= 0))     │
└──────────────────────────────────────────────┘
```

### The Turn Execution Lifecycle:
1. **Idempotency Gate**: Every incoming Telegram update verifies that its `update_id` has not yet been processed. If already present in `processed_updates`, it is rejected.
2. **Context Enrichment**: Persistent shop preferences (e.g. default payment = UPI, default atta = Aashirvaad 5kg, shop GSTIN) are injected into the system instruction from SQLite, ensuring preferences survive `/new` resets.
3. **Execution Loop**: The loop executes up to 6 iterative tool calls per turn, trapping validation errors (e.g., `OversellGuardError`) and returning structured responses for the model to explain politely to the shopkeeper.
4. **Artifact Dispatch**: When a tool produces a document (`.pdf` or `.pptx`), the bot automatically transmits the raw binary file directly to the chat window via `send_document`.

---

## 3. Skill & Tool Design

| Skill Module | Exposed Tools | Responsibility & Domain Guardrails |
|---|---|---|
| **Inventory Skill** | `search_inventory`<br/>`stock_in`<br/>`add_product`<br/>`check_low_stock` | • Grounding: Real prices and stock pulled from DB.<br/>• Guardrail: Refuses selling price below cost price.<br/>• Low-stock reorder thresholds. |
| **Billing Skill** | `add_or_update_cart`<br/>`edit_draft_cart`<br/>`get_active_bill`<br/>`clear_active_bill`<br/>`finalize_bill` | • Multi-turn drafting in `draft_bills`.<br/>• Mid-build edits (*"drop butter, make it 6 Maggi"*).<br/>• **Stock only decremented upon `finalize_bill`**.<br/>• Generates GST Tax Invoice PDF upon completion. |
| **Khata Skill** | `get_khata_balance`<br/>`add_khata_credit`<br/>`record_khata_payment` | • Customer credit ledger tracking.<br/>• **Guardrail**: Refuses settling debt for non-existent customers.<br/>• Real-time balance calculations. |
| **Analytics Skill** | `get_daily_close`<br/>`get_weekly_analytics_data` | • Daily close: revenue, GST collected, cash vs UPI split.<br/>• Aggregates historical metrics for slide decks. |
| **Document Skill** | `generate_bill_invoice_pdf`<br/>`generate_analysis_deck_pptx` | • Produces GST tax invoices (`ReportLab`).<br/>• Produces 5-slide PowerPoint deck with native charts (`python-pptx`). |
| **Preference Skill** | `set_store_preference`<br/>`get_store_preferences` | • Persistent key-value memory in database.<br/>• Survives `/new` session wipes. |

---

## 4. How the "9 Hard Parts" Were Solved

### 1. Grounding (Zero Hallucination)
- **Problem**: Models invent prices or confirm imaginary items.
- **Solution**: The agent only answers pricing and stock availability queries after calling `search_inventory`. If a product does not exist, the tool returns `not_found`, prompting the agent to ask the owner whether to add it.

### 2. Oversell Guard
- **Problem**: Billing 10 when 6 are in stock must be refused at the tool layer, not prompt.
- **Solution**:
  1. *Tool Layer*: `add_or_update_cart` and `edit_draft_cart` check requested quantity against `products.stock_quantity`. If $Q_{\text{req}} > Q_{\text{avail}}$, it raises an immediate error without altering the cart.
  2. *Database Layer*: `CHECK (stock_quantity >= 0)` constraint guarantees negative inventory is physically impossible.

### 3. GST Correctness
- **Problem**: Indian GST intra-state rules require equal 50/50 CGST + SGST split, HSN code tracking, and zero lost paise.
- **Solution**: Implemented in pure Decimal math (`src/utils/gst.py`):
  $$\text{Taxable} = \text{round}\left(\frac{\text{Gross Total}}{1 + \text{Rate}}, 2\right), \quad \text{Total Tax} = \text{Gross Total} - \text{Taxable}$$
  $$\text{CGST} = \text{round}\left(\frac{\text{Total Tax}}{2}, 2\right), \quad \text{SGST} = \text{Total Tax} - \text{CGST}$$
  Handles 0% (loose staples), 5% (packaged staples), 12% & 18% (FMCG).

### 4. Multi-Turn Bills
- **Problem**: Shopkeeper cuts a bill across several messages and modifies quantities mid-way.
- **Solution**: Bills in progress live in the `draft_bills` table. The shopkeeper can add items, remove items (*"drop the butter"*), or alter quantities (*"make it 6 Maggi"*). Inventory is reserved/checked, but **only decremented atomically when `finalize_bill` is called**.

### 5. Idempotency
- **Problem**: Telegram network timeouts trigger update retries, causing double-billing.
- **Solution**: An atomic lookup in `processed_updates` records each incoming `update_id`. If Telegram redelivers the same update, it is dropped immediately before hitting the agent.

### 6. Concurrency
- **Problem**: Two simultaneous bills or a sale plus a stock-in corrupting inventory counts.
- **Solution**: SQLite configured with **Write-Ahead Logging (`PRAGMA journal_mode=WAL;`)** and immediate transactional locks (`BEGIN IMMEDIATE;`). All stock updates execute in ACID transaction blocks.

### 7. Guardrails
- **Problem**: Accidental below-cost sales or phantom khata settlements.
- **Solution**:
  - `add_product` and `stock_in` verify $\text{Selling Price} \ge \text{Cost Price}$.
  - `record_khata_payment` checks customer existence; non-existent accounts are refused.

### 8. Real Artifacts (PDF & PPTX)
- **Problem**: Plain text or fake mockups instead of real files.
- **Solution**:
  - **PDF Invoice**: `ReportLab` renders a standard Indian GST Tax Invoice with store details (**Bala Supermarket**, GSTIN `29ABCDE1234F1Z5`, Tenkasi, Tamil Nadu), place of supply, HSN itemized table, tax breakdown, and signature block. Currency amounts are cleanly formatted as `Rs.` for universal PDF font rendering across all document readers.
  - **PPTX Analysis Deck**: `python-pptx` builds an executive deck containing **real embedded PowerPoint charts** (clustered column chart for top SKUs, pie chart for payment modes, inventory health table).

### 9. Memory Across Sessions
- **Problem**: Owner preferences lost after `/new`.
- **Solution**: Preferences (`default_payment_mode`, `default_atta`, `store_name`) are persisted in the `store_preferences` SQLite table. When `/new` is received, ephemeral conversation messages are cleared, but database preferences are re-injected into the agent prompt.

---

## 5. Store & Environment Configuration

The application is configured for:
- **Store Name**: `Bala Supermarket`
- **GSTIN**: `29ABCDE1234F1Z5`
- **Phone**: `+91 9042678196`
- **Address**: `Shop 4, 12th Main, HAL 2nd Stage,Tenkasi,Tamil Nadu-627806`
- **State & Code**: `TENKASI (State Code: 18)`
- **Payment Modes Supported**:
  - **UPI**: `UPI`, `by UPI`
  - **Cash**: `cash`, `by cash`, `paid cash`, `cash payment`
  - **Card**: `card`, `by card`
  - **Khata**: `khata`, `credit`

---

## 6. How to Run

### Option A: Interactive CLI Simulator (Recommended for instant testing)
Test all shopkeeper interactions and verify artifacts without configuring Telegram:
```bash
python cli_runner.py
```

### Option B: Automated Rubric Evaluation Demo
Runs the complete 4–5 minute evaluation script from start to finish:
```bash
python cli_runner.py --demo
```

### Option C: Live Telegram Bot
```bash
python run_bot.py
```

### Option D: Run Automated Test Suite (Verifying the 9 Hard Parts)
```bash
python run_tests.py
# or with pytest:
pytest tests/ -v
```

---

## 7. Demo Walkthrough Script (4–5 Minutes)

| Step | Owner Message | Expected Agent Behavior | Hard Part Tested |
|---|---|---|---|
| **1. Stock In** | `50 packets of Maggi came in, cost ₹12, MRP ₹14` | Increments Maggi stock by 50, records new cost and MRP. | Grounding, Stock Discipline |
| **2. Add Product** | `new item :- Amul Butter 100g, GST 12%, MRP ₹62` | Inserts new SKU into catalog with 12% GST slab. | Catalog Grounding |
| **3. Multi-Item Bill** | `make a bill :- 2kg sugar, 1 Aashirvaad atta 5kg, 4 Maggi, UPI` | Creates draft bill with accurate GST breakdown; stock is NOT decremented yet. | Multi-Turn Bills, GST Calculation |
| **4. Cash Bill Alternative** | `make a bill :- 2kg sugar, 1 Aashirvaad atta 5kg, cash` | Recognizes cash payment and sets payment mode to CASH. | Cash Payment Support |
| **5. Mid-Build Edit** | `drop the sugar, make it 6 Maggi` | Drops sugar from cart, adjusts Maggi to 6 units without extra emojis. | Cart Editing |
| **6. Oversell Guard** | `make it 500 Maggi` | Refused at tool layer: displays available stock. | **Hard Part 2: Oversell Guard** |
| **7. Finalize Bill** | `finalize` | Decrements inventory atomically, creates completed bill, outputs invoice summary. | Atomic Checkout, Concurrency |
| **8. Khata Credit** | `put ₹500 on Ramesh's credit` | Records debit on Ramesh's ledger, new balance = ₹500. | Khata Ledger |
| **9. Khata Query** | `what's Ramesh's balance?` | Returns current balance of ₹500. | Khata Ledger |
| **10. Khata Payment** | `Ramesh paid ₹300` | Decrements debt, new balance = ₹200. | Khata Ledger |
| **11. Phantom Guard** | `Suresh_Unknown paid ₹500` | Refused: Customer does not exist in records. | **Hard Part 7: Guardrails** |
| **12. Daily Close** | `today's sales? / close the day` | Aggregates revenue, tax collected, cash vs UPI split. | Analytics Skill |
| **13. PDF Invoice** | `send me that bill as a PDF` | Generates GST-compliant PDF invoice (using `Rs.`) and delivers file. | **Hard Part 8: Real Artifacts** |
| **14. PPTX Deck** | `make this week's sales analysis deck` | Generates 5-slide PowerPoint with native charts. | **Hard Part 8: Real Artifacts** |
| **15. Set Preference** | `default atta = Aashirvaad 5kg` | Saves preference in SQLite table. | **Hard Part 9: Memory** |
| **16. New Chat Reset** | `/new` | Clears conversation context window. | Cross-Session Memory |
| **17. Verify Memory** | `make a bill :- 1 atta, UPI` | Automatically chooses Aashirvaad Atta 5kg without asking. | Persistent Memory |

---

## 8. Git Collaborator Invites

As requested in Section 6 of the assignment, the following repository collaborators have been added to the private GitHub repository:
- `Aswath363`
- `akshaiP`
- `ashwanthnebula`
