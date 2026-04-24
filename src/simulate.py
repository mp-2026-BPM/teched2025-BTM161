import argparse
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

from dotenv import load_dotenv

from .agents.customer_agent import CUSTOMER_SCENARIOS


load_dotenv()


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


def _run_single_trace(trace_number, total_traces, scenario_index, quiet):
    """Run one conversation in its own process with fully isolated state."""
    from .coffee_shop import CoffeeShop

    scenario_label = CUSTOMER_SCENARIOS[scenario_index] if scenario_index is not None else "random"
    prefix = f"[Trace {trace_number + 1}/{total_traces}]"

    print(f"{prefix} Starting | Scenario {scenario_index}: {scenario_label[:60]}")

    shop = CoffeeShop()
    shop.open_shop()

    if quiet:
        on_message = None
    else:
        def on_message(role, content):
            tag = "Customer" if role == "customer" else "Agent"
            print(f"{prefix}  [{tag}] {content[:200]}")

    trace_ids = shop.run_conversation(scenario_index=scenario_index, on_message=on_message)

    print(f"{prefix} Done | Trace IDs: {trace_ids}")

    return trace_ids


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
    args = parser.parse_args()

    scenario_mode, scenario_index = parse_scenario(args.scenario)

    parallel = os.getenv("SIMULATION_PARALLEL", "false").lower().strip() == "true"
    max_workers = int(os.getenv("SIMULATION_PARALLEL_WORKERS", "4"))

    all_trace_ids = []

    if parallel and args.traces > 1:
        workers = min(max_workers, args.traces)
        print(f"Initializing parallel simulation ({workers} workers, {args.traces} traces)...\n")

        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {}
            for i in range(args.traces):
                idx = pick_scenario_index(scenario_mode, scenario_index, i)
                future = executor.submit(
                    _run_single_trace, i, args.traces, idx, args.quiet,
                )
                futures[future] = i

            for future in as_completed(futures):
                trace_ids = future.result()
                all_trace_ids.extend(trace_ids)
    else:
        from .coffee_shop import CoffeeShop

        print("Initializing coffee shop...")
        shop = CoffeeShop()
        shop.open_shop()
        print(f"Coffee shop is open. Running {args.traces} trace(s).\n")

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

    print(f"\n=== Simulation complete: {len(all_trace_ids)} trace(s) generated ===")

    if args.export_logs:
        from .trace_processing import TraceProcessor

        print("\nExporting event logs...")
        processor = TraceProcessor()
        processor.process_all_traces()

    return 0


if __name__ == "__main__":
    sys.exit(main())
