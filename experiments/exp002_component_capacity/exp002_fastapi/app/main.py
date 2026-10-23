"""EXP-002: PostgreSQL-backed capacity workload."""
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import psycopg

app = FastAPI(title="EXP-002 PostgreSQL workload", version="1.0.0")
DSN = os.getenv("EXP002_DSN", "dbname=exp002 user=exp002_api host=/var/run/postgresql")

class Event(BaseModel):
    payload: str = Field(min_length=1, max_length=256)

def connect():
    return psycopg.connect(DSN, connect_timeout=3)

@app.get("/health")
def health():
    return {"status": "ok", "mode": "postgresql"}

@app.get("/ready")
def ready():
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                return {"status": "ready", "database": cur.fetchone()[0] == 1}
    except psycopg.Error:
        raise HTTPException(status_code=503, detail="database unavailable")

@app.post("/events", status_code=201)
def create_event(event: Event):
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO events (payload) VALUES (%s) RETURNING id", (event.payload,))
                return {"id": cur.fetchone()[0]}
    except psycopg.Error:
        raise HTTPException(status_code=503, detail="database unavailable")

@app.get("/events/{event_id}")
def get_event(event_id: int):
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, payload FROM events WHERE id=%s", (event_id,))
                row = cur.fetchone()
                if row is None:
                    raise HTTPException(status_code=404, detail="not found")
                return {"id": row[0], "payload": row[1]}
    except psycopg.Error:
        raise HTTPException(status_code=503, detail="database unavailable")


@app.put("/events/{event_id}")
def update_event(event_id: int, event: Event):
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE events SET payload=%s WHERE id=%s "
                    "RETURNING id, payload",
                    (event.payload, event_id),
                )
                row = cur.fetchone()
                if row is None:
                    raise HTTPException(status_code=404, detail="not found")
                return {"id": row[0], "payload": row[1]}
    except psycopg.Error:
        raise HTTPException(status_code=503, detail="database unavailable")


@app.patch("/events/{event_id}")
def patch_event(event_id: int, event: Event):
    return update_event(event_id, event)


@app.delete("/events/{event_id}", status_code=204)
def delete_event(event_id: int):
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM events WHERE id=%s RETURNING id",
                    (event_id,),
                )
                if cur.fetchone() is None:
                    raise HTTPException(status_code=404, detail="not found")
    except psycopg.Error:
        raise HTTPException(status_code=503, detail="database unavailable")
