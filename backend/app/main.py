import os

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.assistant import router as assistant_router
from app.api.datasets import router as datasets_router
from app.api.planning import router as planning_router
from app.api.planning_runs import router as planning_runs_router
from app.database import get_db
from app.services.llm_service import check_ollama_health

load_dotenv()

frontend_origins = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

app = FastAPI(title="7x API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(assistant_router)
app.include_router(datasets_router)
app.include_router(planning_router)
app.include_router(planning_runs_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/database")
def database_health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        ) from error

    return {
        "status": "ok",
        "database": "connected",
    }


@app.get("/health/ollama")
def ollama_health(response: Response):
    result = check_ollama_health()

    if result["status"] in {
        "unavailable",
        "model_missing",
    }:
        response.status_code = 503

    return result
