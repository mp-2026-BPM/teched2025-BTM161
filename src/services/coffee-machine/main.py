from fastapi import FastAPI
from pydantic import BaseModel

from state import create_job, get_job
from worker import run_worker

import threading

app = FastAPI()


# -------- Request schema --------
class BrewRequest(BaseModel):
    drink: str
    correlation_id: str

@app.on_event("startup")
def start_worker():
    thread = threading.Thread(target=run_worker, daemon=True)
    thread.start()
    print("[worker] OCEL background worker started")


# -------- Endpoints --------

@app.post("/brew")
def brew(req: BrewRequest):
    job = create_job(req.drink, req.correlation_id)

    return {
        "job_id": job["job_id"],
        "eta_seconds": job["duration"]
    }


@app.get("/jobs/{job_id}")
def job_status(job_id: str):
    job = get_job(job_id)

    if not job:
        return {"error": "job not found"}

    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "started_at": job["started_at"],
        "finished_at": job["finished_at"]
    }


@app.get("/healthz")
def health():
    return {"status": "ok"}