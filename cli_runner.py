"""Interactive CLI test harness simulating the Telegram chat interface for Supermarket Ops Agent."""

import argparse
import sys
import time
from pathlib import Path

from src.agent.loop import AgentLoop
from src.database.seed import seed_database


def run_interactive_cli(session_id: str = "cli_session"):
    """Run an interactive chat session mimicking Telegram."""
    print("=" * 65)
    print("🏪 SUPERMARKET OPS AGENT — INTERACTIVE CHAT SIMULATOR")
    print("=" * 65)
    print("Operating Indian Kirana Store directly from plain text.")
    print("Type '/new' to reset chat context, 'exit' or 'quit' to stop.\n")

    seed_database(reset=False)
    agent = AgentLoop()

    while True:
        try:
            user_input = input("\n[Owner] > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit"):
                print("Exiting simulator. Goodbye!")
                break

            response = agent.run_turn(session_id=session_id, user_message=user_input)

            print("\n[Agent]:")
            print(response.text)

            if response.artifacts:
                print("\n[📎 Artifacts Generated]:")
                for art in response.artifacts:
                    print(f"  ➜ {art}")

        except (KeyboardInterrupt, EOFError):
            print("\nExiting simulator.")
            break


def run_automated_demo(session_id: str = "demo_session"):
    """
    Executes the exact 4-5 minute evaluation scenario specified in Section 6 of the PDF:
    1. Receive stock
    2. Multi-item bill with an edit
    3. Oversell guard refusal
    4. Khata credit cycle
    5. Generate a PDF invoice
    6. Generate the analysis deck (PPTX)
    7. Set a preference, start /new chat, and show it is remembered
    """
    print("=" * 70)
    print("🎬 RUNNING AUTOMATED EVALUATION SCENARIO (Section 6 & 7 Rubric)")
    print("=" * 70)

    seed_database(reset=True)
    agent = AgentLoop()

    scenario_steps = [
        ("Step 1: Receive Stock", "50 packets of Maggi came in, cost ₹12, MRP ₹14"),
        ("Step 2: Add New Product", "new item: Amul Butter 100g, GST 12%, MRP ₹62"),
        ("Step 3: Multi-item Bill (Draft Cart)", "make a bill: 2kg sugar, 1 Aashirvaad atta 5kg, 4 Maggi, 1 Amul butter, UPI"),
        ("Step 4: Mid-Build Edit (Drop & Adjust)", "drop the butter, make it 6 Maggi"),
        ("Step 5: Hard Part 2: Oversell Guard", "bill: 500 packets of Maggi"),
        ("Step 6: Finalize Bill", "finalize"),
        ("Step 7: Hard Part 7 & Khata Cycle (Credit)", "put ₹500 on Ramesh's credit"),
        ("Step 8: Khata Balance Query", "what's Ramesh's balance?"),
        ("Step 9: Khata Partial Payment", "Ramesh paid ₹300"),
        ("Step 10: Settle Non-existent Khata (Guardrail)", "Suresh_Unknown paid ₹500"),
        ("Step 11: Daily Store Close Report", "today's sales? / close the day"),
        ("Step 12: Real Artifact 1: GST Tax Invoice PDF", "send me that bill as a PDF"),
        ("Step 13: Real Artifact 2: Sales Analysis Deck (PPTX)", "make this week's sales analysis deck"),
        ("Step 14: Standing Preference Configuration", "default atta = Aashirvaad 5kg"),
        ("Step 15: Cross-Session Memory Check: Reset with /new", "/new"),
        ("Step 16: Verify Memory Persisted", "make a bill: 1 atta, UPI"),
    ]

    for label, prompt in scenario_steps:
        print("\n" + "─" * 60)
        print(f"▶ {label}")
        print(f"👤 [Owner]: {prompt}")
        time.sleep(0.3)
        res = agent.run_turn(session_id=session_id, user_message=prompt)
        print(f"🤖 [Agent]:\n{res.text}")
        if res.artifacts:
            for art in res.artifacts:
                print(f"   📎 [Created File]: {art}")
        time.sleep(0.2)

    print("\n" + "=" * 70)
    print("✅ All evaluation scenario steps executed successfully!")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Supermarket Ops Agent CLI Harness")
    parser.add_argument("--demo", action="store_true", help="Run automated evaluation scenario demo")
    args = parser.parse_args()

    if args.demo:
        run_automated_demo()
    else:
        run_interactive_cli()
