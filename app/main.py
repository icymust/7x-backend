from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.datasets import router as datasets_router
from app.api.planning import router as planning_router
from app.api.planning_runs import router as planning_runs_router
from app.database import get_db

app = FastAPI(title="7x API")
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
