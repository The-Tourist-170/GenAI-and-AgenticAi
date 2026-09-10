from fastapi import FastAPI
from fastapi.param_functions import Query
from client.rq_client import queue
from queues.worker import process_query

app = FastAPI()

@app.get("/")
def root():
    return {"message": "SERVER IS UP AND RUNNING"}

@app.post("/chat")
def chat(
        query: str = Query(..., description="The user's query")
    ):

    job = queue.enqueue(process_query, query)
    return {"status": "queued", "job_id": job.id}

@app.get("/result")
def get_job_status(
        job_id: str = Query(..., description="The job ID to fetch status for")
    ):
    job = queue.fetch_job(job_id)
    if job is None:
        return {"status": "not found"}
    return {"status": job.return_value()}
