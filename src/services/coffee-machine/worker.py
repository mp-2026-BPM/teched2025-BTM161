import time
from state import jobs, get_job

POLL_INTERVAL = 1.0


def run_worker():
    """
    Background OCEL simulation engine.
    Continuously advances job states and triggers event emissions.
    """

    while True:
        # iterate over a copy to avoid mutation issues
        for job_id in list(jobs.keys()):
            try:
                get_job(job_id)  # triggers OCEL transitions
            except Exception as e:
                print(f"[worker] error processing {job_id}: {e}")

        time.sleep(POLL_INTERVAL)