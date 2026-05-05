import argparse
import logging
import sys

from .coffee_shop import CoffeeShop
from .agents.customer_agent import CUSTOMER_SCENARIOS
from .trace_processing import TraceProcessor


def parse_scenario(value):
    if value == "all":
        return ("all", None)
    if value == "random":
        return ("random", None)
    try:
        idx = int(value)
        if 0 <= idx < len(CUSTOMER_SCENARIOS):
            return ("fixed", idx)
        print(f"Error: scenario index must be 0-{len(CUSTOMER_SCENARIOS) - 1}")
        sys.exit(1)
    except ValueError:
        print(f"Error: --scenario must be 0-{len(CUSTOMER_SCENARIOS) - 1}, 'all', or 'random'")
        sys.exit(1)


def pick_scenario_index(mode, fixed_index, trace_number):
    if mode == "fixed":
        return fixed_index
    if mode == "all":
        return trace_number % len(CUSTOMER_SCENARIOS)
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Run headless coffee shop simulations to generate traces"
    )
    parser.add_argument(
        "--traces", type=int, default=1,
        help="Number of conversation traces to run (default: 1)",
    )
    parser.add_argument(
        "--scenario", type=str, default="random",
        help="Scenario index (0-3), 'all' (round-robin), or 'random' (default: random)",
    )
    parser.add_argument(
        "--export-logs", action="store_true",
        help="Export event logs after simulation",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Minimal output: only trace numbers, scenarios, and summary",
    )
    parser.add_argument(
        "--log-level", type=str, default="warning",
        choices=["debug", "info", "warning", "error"],
        help="Set the logging level for the coffee_shop logger (default: warning)",
    )
    args = parser.parse_args()

    scenario_mode, scenario_index = parse_scenario(args.scenario)

    logging.getLogger("coffee_shop").setLevel(getattr(logging, args.log_level.upper()))

    print("Initializing coffee shop...")
    shop = CoffeeShop()
    shop.open_shop()
    print(f"Coffee shop is open. Running {args.traces} trace(s).\n")

    all_trace_ids = []
    for i in range(args.traces):
        idx = pick_scenario_index(scenario_mode, scenario_index, i)
        scenario_label = CUSTOMER_SCENARIOS[idx] if idx is not None else "random"
        print(f"--- Trace {i + 1}/{args.traces} | Scenario {idx}: {scenario_label[:60]} ---")

        if args.quiet:
            on_message = None
        else:
            def on_message(role, content):
                prefix = "  [Customer]" if role == "customer" else "  [Agent]   "
                print(f"{prefix} {content[:200]}")

        trace_ids = shop.run_conversation(scenario_index=idx, on_message=on_message)
        all_trace_ids.extend(trace_ids)
        print(f"  Trace IDs: {trace_ids}\n")

    print(f"=== Simulation complete: {len(all_trace_ids)} trace(s) generated ===")

    if args.export_logs:
        print("\nExporting event logs...")
        processor = TraceProcessor()
        processor.process_all_traces()

    return 0


if __name__ == "__main__":
    sys.exit(main())
