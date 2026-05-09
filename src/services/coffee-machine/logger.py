import csv
import os
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_PATH = LOG_DIR / "coffee_machine.csv"


def log_event(case_id: str, activity: str, timestamp: float, duration: float = None, **attrs):
    file_exists = os.path.isfile(LOG_PATH)

    with open(LOG_PATH, "a", newline="") as f:
        writer = csv.writer(f)

        # Build header dynamically on first write
        if not file_exists:
            header = [
                "case_id",
                "concept:name",
                "ocel_time",
                "duration",
                "org:resource"
            ]

            # include dynamic attributes (OCEL-friendly extension)
            header += list(attrs.keys())

            writer.writerow(header)

        row = [
            case_id,
            activity,
            timestamp,          # KEEP AS FLOAT (IMPORTANT for OCEL pipelines)
            duration,
            "coffee_machine"
        ]

        # append dynamic attributes in same order
        row += list(attrs.values())

        writer.writerow(row)